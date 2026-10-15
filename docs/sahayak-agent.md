# Sahayak Agent development — 15 October 2026

## Implemented in this increment
The application still has exactly three components: Sahayak Portal, Sahayak Agent,
and Sahayak Voice Connect. This module is part of Sahayak Agent.

A local synthetic pilot now runs a LangGraph retrieve -> generate -> validate
workflow using the existing Bedrock Knowledge Base and Sarvam chat API. A Bulbul
v3 adapter produces a WAV file. This is REST audio-file synthesis, not streaming
telephone integration. Existing scripts and private .env files are unchanged.

Run from the repository root:

```sh
uv run python -m sahayak.agent speech-demo
uv run python -m sahayak.agent demo --case outlook-hi --speak
```

Each invocation is usage-billed. speech-demo sends one fixed Hindi sentence to
Bulbul. demo runs one named synthetic case (see fixtures.py); --speak explicitly
adds synthesis of the unreviewed generated reply. It is not an employee-facing
entry point. Reports/audio are written to ignored output/agent/ with unique names.
No telephone calls, ticket writes, agent tools or cloud provisioning occur.

## Configuration
Existing SARVAM_API_KEY is read from the repository .env or environment, never
printed. Optional SAHAYAK_AGENT_ settings: AWS_PROFILE, AWS_REGION,
KNOWLEDGE_BASE_ID, SOURCE_PREFIX, CHAT_MODEL, SPEAKER, SAMPLE_RATE,
TIMEOUT_SECONDS, MAX_OUTPUT_TOKENS. Defaults match the verified pilot resources.
Bulbul v3 + shubh + 24 kHz WAV is a provisional compatibility-test selection,
not the final voice. Speech API uses language_code per current REST reference.

Sarvam requests have bounded timeouts and no automatic retries. Bad HTTP/JSON,
incomplete answers, unknown citation IDs, missing Hindi script, out-of-prefix
retrieval and malformed WAV data stop the command. Citations remain in the report
but are removed from spoken text. These are structural checks, not grounding or
prompt-injection guarantees. TTS failure does not trigger another model or redial.

## Evaluation

```sh
uv sync --group eval
uv run --group eval python -m sahayak.agent.evaluation output/agent/REPORT.json
```

DeepEval 3.8.9 is pinned in the optional eval group and uv.lock. It measures two
G-Eval metrics on one saved synthetic report: grounding and employee response.
The Sarvam custom judge is explicit; no default OpenAI judge is invoked. The
runner disables telemetry and uses standalone metrics, without Confident uploads.
It allows at most four judge calls, each capped at 1500 output tokens, with no
adapter retries. Schema failures produce no passing result. Scores are advisory:
no release threshold is approved, and same-provider judge bias remains. This is
not an independent safety validator. Optional --judge-model selects another
Sarvam model only after its access and suitability have been checked.

Offline regression tests: uv run python -m pytest tests -q.
These mock providers and do not prove live service quality.

## Remaining required integration
- Trusted authenticated employee/ticket context and domain authority reload.
- AgentCore Runtime, Gateway/Policy search wrapper and authorized tool handlers.
- Bedrock Guardrails before inference and speech; fail closed on errors.
- Employee confirmation evidence and persisted outcomes; no model-only completion.
- Durable workflow memory/checkpoints, recovery and independently provided fallback.
- Saaras, Bulbul streaming, cancellation/barge-in and LiveKit integration.
- Expanded multilingual dataset and calibrated DeepEval/human review gates.
- Usage ceilings, retention, hosted cost plan and production access controls.

The local pilot uses direct Retrieve only for its synthetic fixtures; it is not
the final Gateway/Policy retrieval path. Prefix checking is defense in depth,
not an employee authorization mechanism. Do not expose this CLI as a service or
connect it to the worker before those boundaries exist. Calls remain disabled.

## References checked
- https://docs.sarvam.ai/api-reference/text-to-speech/convert
- https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/bulbul-v3-best-practices
- https://deepeval.com/guides/guides-using-custom-llms
- https://deepeval.com/docs/metrics-llm-evals


## Sahayak Agent increment — 15 October 2026

Implemented a synthetic local LangGraph retrieval/generation workflow, bounded
Sarvam adapters, Bulbul v3 WAV synthesis and an optional DeepEval custom Sarvam
judge. This remains part of Sahayak Agent, not an additional component.

Verified live: fixed Hindi speech and an Outlook Hindi Retrieve -> Sarvam -> Bulbul
run both produced structurally valid WAV files. Audio has not been subjectively
reviewed. The generated reply correctly preserved the unresolved Outlook issue,
but used unnecessary English jargon. DeepEval completed two judge requests on
that saved response, returning grounding 0.9 and employee response 0.9. These
same-provider advisory scores are not release approval; the judge missed jargon
and made an inconsistent suggestion about an already-present confirmation question.

Regression: 98 tests and 10 subtests pass with optional eval dependencies installed.
The optional pytest rerunfailures plugin binds a local socket; in restricted
sandboxes use `-p no:rerunfailures -p no:cacheprovider` for these offline tests.
One initial judge adapter property mismatch was corrected and covered by tests.
DeepEval dependencies emit Python 3.14 SyntaxWarnings; these did not block checks.

Managed guardrails, authenticated context/tools, durable conversation memory,
Saaras input, streaming/barge-in and Sahayak Voice Connect remain pending.
No ticket changes, telephone calls or new AWS resources were made by this increment.
See sahayak-agent.md for runnable commands and configuration. Existing user pilot
files and private environment files were preserved. Changes are uncommitted.

## Recorded speech — 15 October 2026

Saaras v3 now accepts a short synthetic WAV question and feeds its transcript to
Sahayak Agent's existing graph. Bulbul produces the response WAV. This is one
recorded turn, not microphone capture, streaming, or a continuous conversation.

```sh
uv run python -m sahayak.agent voice-demo output/agent/stt-outlook-hi-question.wav --language hi
```

The command uploads the supplied recording to Sarvam. Use only synthetic IT
questions without private data during this pilot. It accepts mono PCM16 WAV,
under 30 seconds and 3 MB, at 16/22.05/24/44.1/48 kHz. Choose en, hi or hinglish
for the reply language. Invalid/truncated audio is rejected locally. Unsupported
or empty transcripts block reasoning and speech. No automatic provider retry.
The input recording is not copied; the transcript, sources and response are saved
in ignored output/agent alongside the generated WAV. These development artifacts
remain until manually removed; production retention policy is still open.

Verified live with a generated Hindi Outlook question: Saaras -> Bedrock Retrieve
-> Sarvam chat -> Bulbul completed and saved a valid WAV. Synthetic voice does not
validate real accents, noise or recognition accuracy. The response preserved the
unresolved Outlook problem but still included operator-style handoff wording.
117 tests and 10 subtests pass; no live calls or ticket mutations occurred.
Microphone input, streaming, barge-in and managed guardrails remain pending.
API contract: https://docs.sarvam.ai/api-reference/speech-to-text/transcribe

## Microphone input — 15 October 2026

From the repository root:

```sh
uv run --group voice python -m sahayak.agent microphone-demo --language hi
```

Press Enter when ready, then speak after the recording message. Default capture
is 12 seconds; --seconds accepts 1-25. --language supports en/hi/hinglish.
macOS may ask permission for your terminal to use the microphone. If blocked,
check System Settings > Privacy & Security > Microphone. --device accepts an
optional PortAudio input index. The system default input is otherwise used.

Recording stops before upload and playback. Ctrl+C cancels without retry.
Use a synthetic IT question: audio is uploaded to Sarvam; transcript/reply are
saved in ignored output/agent. Raw microphone audio is held in memory, not saved.
The command automatically plays the saved reply on macOS using afplay. This is
one turn, with no continuous listening, interruption handling or conversation memory.

Optional voice dependency: sounddevice==0.5.5. PortAudio library import verified
on this Mac/Python 3.14. Capture uses the device's native supported rate with mono
PCM16 and blocks upload on overflow, incomplete audio or exact digital silence.
Silence checking is not a speech detector. Tests mock microphone hardware; actual
microphone permission, user voice and speaker playback require the user's test.

Reference: https://python-sounddevice.readthedocs.io/en/0.5.5/installation.html
