"""Explicit press-to-talk session for synthetic local testing."""
import json
import subprocess
import sys
from .config import ROOT
from .conversation import Conversation
from .microphone import record_microphone
from .providers import ProviderError


def run_conversation(args, provider, workflow):
    if sys.platform != "darwin":
        raise ValueError("This local playback command currently supports macOS")
    session = Conversation(workflow, args.language, args.turns)
    print("Sahayak Agent session: Enter records one question; q exits. Ctrl+C stops.")
    print("Use synthetic IT questions. Audio goes to Sarvam; transcripts and replies are saved locally.")
    print("Context lasts only for this session. No ticket actions are available.")
    try:
        while session.turns < session.max_turns:
            choice = input(f"Turn {session.turns + 1}/{session.max_turns} — Enter to record, q to quit: ").strip().lower()
            if choice == "q":
                break
            if choice:
                print("Press Enter to record or type q to quit.")
                continue
            audio = record_microphone(args.seconds, args.device)
            transcription = provider.transcribe(audio, args.language)
            print("You:", transcription["transcript"])
            state = session.respond(transcription["transcript"])
            report = {**state, "mode": "synthetic_pilot", "managed_guardrails": False,
                      "transcription": transcription, "delivery": "not_played"}
            output = ROOT / "output" / "agent"
            output.mkdir(parents=True, exist_ok=True)
            stem = output / f"{session.session_id}-turn-{session.turns + 1}"
            report_path = stem.with_suffix(".json")
            try:
                if state["status"] != "generated_unreviewed":
                    print("No supporting knowledge found. Session stopped.")
                    break
                reply = provider.synthesize(state["spoken_text"], args.language)
                path = stem.with_suffix(".wav")
                with path.open("xb") as handle:
                    handle.write(reply)
                report["audio_path"] = str(path)
                print("Sahayak Agent:", state["answer"])
                report["delivery"] = "playback_started"
                try:
                    subprocess.run(["/usr/bin/afplay", str(path)], check=True, timeout=120)
                except (OSError, subprocess.SubprocessError):
                    report["delivery"] = "playback_failed_or_incomplete"
                    raise ProviderError("Playback failed; session stopped without retry. Reply saved locally.") from None
                except KeyboardInterrupt:
                    report["delivery"] = "interrupted"
                    raise
                report["delivery"] = "playback_completed_unconfirmed"
                session.delivered()
            finally:
                with report_path.open("x", encoding="utf-8") as handle:
                    json.dump(report, handle, ensure_ascii=False, indent=2)
                print("Report:", report_path)
        print("Session ended. In-memory context cleared.")
    finally:
        session.close()
    return 0
