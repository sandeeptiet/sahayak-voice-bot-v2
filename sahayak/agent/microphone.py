"""Explicit, bounded local capture. No background listener or raw-audio retention."""
import io
import wave
from .speech import validate_recording


def record_microphone(seconds=12, device=None, backend=None):
    if not isinstance(seconds, int) or not 1 <= seconds <= 25:
        raise ValueError("Recording duration must be 1-25 seconds")
    if backend is None:
        try:
            import sounddevice as backend
        except (ImportError, OSError):
            raise ValueError("Install microphone support with: uv sync --group voice") from None
    try:
        rate = int(backend.query_devices(device, "input")["default_samplerate"])
        if rate not in (16000, 22050, 24000, 44100, 48000):
            raise ValueError("Unsupported microphone sample rate")
        chunks = []
        with backend.RawInputStream(samplerate=rate, channels=1, dtype="int16", device=device) as stream:
            print(f"Recording now for {seconds} seconds. Speak your test question. Ctrl+C cancels.", flush=True)
            remaining = seconds * rate
            while remaining:
                count = min(remaining, 1024)
                data, overflowed = stream.read(count)
                if overflowed:
                    raise ValueError("Microphone audio was interrupted; recording discarded. Please try again.")
                chunks.append(bytes(data))
                remaining -= count
    except backend.PortAudioError:
        raise ValueError("Microphone unavailable. Check macOS microphone permission for your terminal and its input device.") from None
    frames = b"".join(chunks)
    if len(frames) != seconds * rate * 2:
        raise ValueError("Incomplete recording; audio discarded")
    # Exact digital silence cannot contain a question. This is not voice detection.
    if not any(frames):
        raise ValueError("No audio captured. Check the microphone; nothing was uploaded.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes(frames)
    audio = output.getvalue()
    validate_recording(audio)
    print("Recording stopped. Sending this test question to Sarvam.", flush=True)
    return audio
