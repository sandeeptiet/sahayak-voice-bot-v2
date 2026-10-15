"""One recorded synthetic turn; no microphone, telephony or ticket authority."""
import io
import wave
from pathlib import Path

MAX_AUDIO_BYTES = 3_000_000


def validate_recording(audio):
    if not isinstance(audio, bytes) or not 44 <= len(audio) <= MAX_AUDIO_BYTES:
        raise ValueError("Recording must be a PCM WAV file below 3 MB")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            frames, rate = wav.getnframes(), wav.getframerate()
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2
                    or rate not in (16000, 22050, 24000, 44100, 48000)
                    or not 0 < frames / rate < 30):
                raise ValueError()
            if len(wav.readframes(frames)) != frames * 2:
                raise ValueError()
    except (wave.Error, EOFError, ValueError):
        raise ValueError("Use complete mono PCM16 WAV audio shorter than 30 seconds at a supported rate") from None


def read_recording(path):
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(MAX_AUDIO_BYTES + 1)
    except OSError:
        raise ValueError("Cannot read the supplied recording") from None
    validate_recording(data)
    return data


def run_spoken_turn(audio, language, provider, workflow):
    transcription = provider.transcribe(audio, language)
    # Transcript is untrusted question text, never confirmation or tool authority.
    state = workflow.invoke({"question": transcription["transcript"], "language": language})
    reply = None
    if state["status"] == "generated_unreviewed":
        reply = provider.synthesize(state["spoken_text"], language)
    return {**state, "transcription": transcription}, reply
