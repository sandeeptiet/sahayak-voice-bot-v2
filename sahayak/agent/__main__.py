"""Explicitly invoked local pilot commands; never invoked by dispatch."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
import boto3
import httpx
from botocore.config import Config
from .config import AgentSettings, ROOT
from .fixtures import CASES, SPEECH_SAMPLE
from .providers import BedrockRetriever, Sarvam, ProviderError
from .workflow import build_workflow
from .speech import read_recording, run_spoken_turn
from .microphone import record_microphone
from .conversation_cli import run_conversation


def main():
    parser = argparse.ArgumentParser(description="Sahayak Agent synthetic pilot (usage-billed)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("speech-demo", help="Synthesize one fixed, reviewed Hindi sample")
    rag = sub.add_parser("demo", help="Run one fixed synthetic RAG case; managed guardrails not connected")
    rag.add_argument("--case", choices=CASES, default="outlook-hi")
    rag.add_argument("--speak", action="store_true", help="Also synthesize unreviewed synthetic output locally")
    voice = sub.add_parser("voice-demo", help="One synthetic WAV question to spoken reply; uploads audio to Sarvam")
    voice.add_argument("recording", type=Path)
    voice.add_argument("--language", choices=("en", "hi", "hinglish"), required=True)
    mic = sub.add_parser("microphone-demo", help="Record one test question, send to Sarvam and play the answer")
    mic.add_argument("--language", choices=("en", "hi", "hinglish"), default="hi")
    mic.add_argument("--seconds", type=int, choices=range(1, 26), default=12, metavar="1-25")
    mic.add_argument("--device", type=int, help="Optional PortAudio input device index")
    conversation = sub.add_parser("conversation-demo", help="Up to six microphone turns with session context")
    conversation.add_argument("--language", choices=("en", "hi", "hinglish"), default="hi")
    conversation.add_argument("--seconds", type=int, choices=range(1, 26), default=12, metavar="1-25")
    conversation.add_argument("--device", type=int)
    conversation.add_argument("--turns", type=int, choices=range(1, 7), default=6)
    args = parser.parse_args()
    try:
        recording = read_recording(args.recording) if args.command == "voice-demo" else None
        settings = AgentSettings()
        settings.key()
        if args.command == "microphone-demo":
            print("Use a synthetic IT question, without private information. Audio is sent to Sarvam; the transcript and reply are saved locally.")
            input("Press Enter when ready to record (Ctrl+C cancels): ")
            recording = record_microphone(args.seconds, args.device)
        with httpx.Client(follow_redirects=False) as http:
            sarvam = Sarvam(settings, http)
            report = {"mode": "synthetic_pilot", "managed_guardrails": False}
            audio = None
            if args.command == "speech-demo":
                audio = sarvam.synthesize(SPEECH_SAMPLE, "hi")
                report.update({"speech_model": settings.tts_model, "speaker": settings.speaker,
                               "spoken_text": SPEECH_SAMPLE})
            else:
                if args.command in ("voice-demo", "microphone-demo", "conversation-demo"):
                    language = args.language
                else:
                    language, question, expected = CASES[args.case]
                client = boto3.Session(profile_name=settings.aws_profile).client(
                    "bedrock-agent-runtime", region_name=settings.aws_region,
                    config=Config(connect_timeout=10, read_timeout=settings.timeout_seconds,
                                  retries={"total_max_attempts": 1}),
                )
                try:
                    workflow = build_workflow(BedrockRetriever(client, settings), sarvam)
                    if args.command == "conversation-demo":
                        return run_conversation(args, sarvam, workflow)
                    if args.command in ("voice-demo", "microphone-demo"):
                        state, audio = run_spoken_turn(recording, language, sarvam, workflow)
                    else:
                        state = workflow.invoke({"question": question, "language": language})
                finally:
                    client.close()
                report.update(state)
                if args.command == "demo":
                    report.update({"case": args.case, "expected_source": expected})
                else:
                    report.update({"case": "recorded-synthetic", "speech_model": settings.tts_model})
                if args.command == "demo" and args.speak and state["status"] == "generated_unreviewed":
                    audio = sarvam.synthesize(state["spoken_text"], language)
            output = ROOT / "output" / "agent"
            output.mkdir(parents=True, exist_ok=True)
            stem = output / str(uuid4())
            if audio:
                wav_path = stem.with_suffix(".wav")
                with wav_path.open("xb") as handle:
                    handle.write(audio)
                report["audio_path"] = str(wav_path)
                print("Audio:", wav_path)
            if args.command == "microphone-demo":
                report["input_mode"] = "microphone"
            report_path = stem.with_suffix(".json")
            with report_path.open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
            print("Report:", report_path)
            print(report.get("answer", report.get("spoken_text", report.get("status"))))
            if args.command == "microphone-demo" and audio and sys.platform == "darwin":
                print("Playing Sahayak Agent's reply...", flush=True)
                try:
                    subprocess.run(["/usr/bin/afplay", str(wav_path)], check=True, timeout=120)
                except (OSError, subprocess.SubprocessError):
                    print("Playback failed; the reply is saved at:", wav_path)
    except (KeyboardInterrupt, EOFError):
        print("\nStopped. No automatic retry.")
        return 130
    except (ProviderError, ValueError) as exc:
        print("Sahayak Agent stopped:", str(exc))
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
