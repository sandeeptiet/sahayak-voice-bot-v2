"""Bounded provider adapters. Never log provider response bodies or secrets."""
import base64
import binascii
import io
import json
import wave
import httpx
from botocore.exceptions import BotoCoreError, ClientError

class ProviderError(RuntimeError):
    pass

class BedrockRetriever:
    def __init__(self, client, settings):
        self.client, self.settings = client, settings

    def retrieve(self, question):
        try:
            result = self.client.retrieve(
                knowledgeBaseId=self.settings.knowledge_base_id,
                retrievalQuery={"text": question},
                retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 3}},
            )
        except (BotoCoreError, ClientError):
            raise ProviderError("Knowledge retrieval failed") from None
        passages = []
        for item in result.get("retrievalResults", []):
            uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            text = item.get("content", {}).get("text", "")
            # Defense in depth for this isolated pilot, not employee authorization.
            if not uri.startswith(self.settings.source_prefix):
                raise ProviderError("Retrieved source is outside the configured pilot scope")
            if not isinstance(text, str) or not text.strip() or len(text) > 12000:
                raise ProviderError("Invalid retrieved passage")
            passages.append({"id": f"S{len(passages)+1}", "uri": uri,
                             "text": text, "score": item.get("score")})
        return passages

class Sarvam:
    def __init__(self, settings, client):
        self.settings, self.client = settings, client

    def post(self, path, payload=None, *, data=None, files=None):
        try:
            response = self.client.post(
                "https://api.sarvam.ai" + path,
                headers={"api-subscription-key": self.settings.key()},
                **({"json": payload} if files is None else {"data": data, "files": files}),
                timeout=self.settings.timeout_seconds,
            )
        except httpx.RequestError:
            raise ProviderError("Sarvam connection failed; request was not retried") from None
        if not response.is_success:
            raise ProviderError(f"Sarvam returned HTTP {response.status_code}; request was not retried")
        try:
            return response.json()
        except ValueError:
            raise ProviderError("Sarvam returned invalid JSON") from None

    def chat(self, instructions, question, sources, history=None):
        result = self.post("/v1/chat/completions", {
            "model": self.settings.chat_model,
            "messages": [{"role": "system", "content": instructions},
                         {"role": "user", "content": json.dumps({
                             "question": question, "retrieved_passages": sources,
                             "conversation_history": history or []}, ensure_ascii=False)}],
            "max_tokens": self.settings.max_output_tokens,
            "reasoning_effort": None, "stream": False,
        })
        try:
            choice = result["choices"][0]
            answer = choice["message"]["content"]
            if choice.get("finish_reason") != "stop" or not isinstance(answer, str) or not answer.strip():
                raise ValueError()
            if len(answer) > 2500:
                raise ValueError()
            return {"answer": answer.strip(), "usage": result.get("usage", {})}
        except (KeyError, IndexError, TypeError, ValueError):
            raise ProviderError("Incomplete or invalid chat output; speech is blocked") from None

    def transcribe(self, audio, language):
        # Validate before uploading anything. This pilot accepts bounded PCM WAV only.
        from .speech import validate_recording
        validate_recording(audio)
        if language not in ("en", "hi", "hinglish"):
            raise ValueError("Unsupported speech language")
        result = self.post("/speech-to-text", data={
            "model": self.settings.stt_model, "mode": "transcribe",
            "language_code": "en-IN" if language == "en" else "hi-IN",
        }, files={"file": ("utterance.wav", audio, "audio/wav")})
        if not isinstance(result, dict):
            raise ProviderError("Invalid transcription response; downstream processing blocked")
        text = result.get("transcript")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ProviderError("Empty or invalid transcript; downstream processing blocked")
        detected = result.get("language_code")
        if detected not in ("en-IN", "hi-IN"):
            raise ProviderError("Unsupported or undetected speech language; downstream processing blocked")
        return {"transcript": text.strip(), "detected_language": detected,
                "stt_model": self.settings.stt_model}

    def synthesize(self, text, language):
        if language not in ("en", "hi", "hinglish") or not text.strip() or len(text) > 2500:
            raise ValueError("Speech requires a supported language and 1-2500 characters")
        result = self.post("/text-to-speech", {
            "text": text, "language_code": "en-IN" if language == "en" else "hi-IN",
            "model": self.settings.tts_model, "speaker": self.settings.speaker,
            "speech_sample_rate": self.settings.sample_rate, "output_audio_codec": "wav",
            "pace": 1.0,
        })
        try:
            audios = result["audios"]
            if not isinstance(audios, list) or len(audios) != 1 or not isinstance(audios[0], str):
                raise ValueError()
            if len(audios[0]) > 16000000:
                raise ValueError()
            data = base64.b64decode(audios[0], validate=True)
            with wave.open(io.BytesIO(data), "rb") as wav:
                if wav.getframerate() != self.settings.sample_rate or wav.getnchannels() != 1:
                    raise ValueError()
                if wav.getsampwidth() != 2 or wav.getnframes() == 0:
                    raise ValueError()
                frames = wav.readframes(wav.getnframes())
                if len(frames) != wav.getnframes() * 2:
                    raise ValueError()
            return data
        except (KeyError, TypeError, ValueError, binascii.Error, wave.Error, EOFError):
            raise ProviderError("Invalid or unsupported WAV response; no audio saved") from None
