# Implementation status

## Foundation slice — 11 October 2026

Application repository confirmed by the user as Desktop/prep/Sahayak-voice-agent-v2
(the filesystem resolves the directory name to sahayak-voice-agent-v2).

Implemented and locally tested:
- Pure category/priority rules from technical-requirements.md section 4.2.
- Future callback validation requiring timezone-aware inputs and returning UTC.
- Deterministic tests including urgency escalation and Asia/Kolkata conversion.

Compatibility check: existing Python 3.14.3 environment successfully imports
sarvamai 0.1.36, langgraph 1.2.14 and langchain-sarvam 0.1.2. Installed package
Python requirements include this runtime. This is an import smoke check only;
LiveKit, AWS adapters and actual model/tool/streaming behavior remain unverified.
The existing main.py remains a separate exploratory starter.

No paid API requests, cloud provisioning, phone calls or database changes made.
The old GitHub reference could not be fetched during this slice; rules are based
on the local handoff, not a new verification of the old source.

## Earlier next-slice plan (superseded below)

Implement portable PostgreSQL persistence and migrations, then the ticket domain
service with atomic audit, trusted actor scope, concurrency and action receipts.
Completion evidence must refer to a persisted employee turn; never accept a
model-generated confirmation flag as proof. Do not expose intake as an API until
authentication/profile trust and persistence are implemented.

Remaining: typed service configuration, provider interfaces, authenticated API,
workflow, tools/policy, guardrails, memory, retrieval, durable dispatch, voice,
frontend, evaluations and infrastructure. No end-to-end integration is claimed.
Open decisions remain authoritative in technical-requirements.md section 17.

## Portal login slice — 12 October 2026

Implemented directly in the Desktop repository at the user's instruction:
- React/TypeScript portal in portal/, responsive login and signed-in preview.
- Existing Cognito public app client: authorization code + S256 PKCE, state,
  nonce, ID-token signature/issuer/audience/expiry/token-use validation.
- In-memory tokens, callback URL cleanup, expiry handling, refresh-token
  revocation attempt and Cognito logout. No persistent token storage.
- Public configuration stored in ignored portal/.env.local; placeholder example
  and exact dependency lockfile supplied.

Verified locally: production build; 15 Playwright tests using simulated Cognito
responses with signed synthetic tokens; desktop/mobile screenshots inspected;
existing six Python tests pass. npm install audit reported zero vulnerabilities.
Public Cognito discovery metadata was fetched and matches the provided domain
and issuer. Real password/MFA sign-in and app-client acceptance are NOT yet
verified through the portal. No backend, RDS writes, queue publishing, calls or
cloud deployments were performed during this slice.

User-reported prerequisite state: two Cognito users (employee and combined
engineer/admin), RDS PostgreSQL 17 with the sahayak schema created manually,
rollback verification passed, profiles and authorized phone mapped, two SQS
queues configured. These were guided setup confirmations, not a fresh automated
cloud inventory. RDS public accessibility restricted to the user's /32 is an
explicit POC exception to the original private-network plan.

Next: live login/logout verification with the user's two accounts. Then build
FastAPI access-token validation, active profile/role authorization and scoped
ticket intake/history with SQLAlchemy/psycopg. Adopt the existing schema through
verified Alembic baselining, not blind recreation. Runtime restricted DB grants
and disabled-user/revocation handling must be implemented before exposing data.
The prerequisite ticket UPDATE/DELETE blocking trigger is still in place;
replace it only as audited lifecycle operations are implemented and tested.

## Role-scoped portal and backend — 13 October 2026

Latest user clarification: employees create/view only their tickets; engineers see
all tickets and self-assign unassigned human escalations. Assigned engineers record
completed/failed outcomes with notes. Dedicated runtime database login retained.

Implemented FastAPI access-token verification plus online Cognito session check,
active profile/role intersection, scoped reads, idempotent intake, versioned claims
and outcomes, SQLAlchemy/psycopg persistence, Alembic schema adoption, restricted
grants and audited lifecycle triggers. Frontend has matching role-scoped screens.
Interactive setup stores only the limited runtime credential in private `.env.api`.

Verified: 34 Python tests (plus 10 subtests), 20 mocked browser tests, 22 ephemeral
PostgreSQL checks, production frontend build and inspected responsive screenshots.
User confirmed real Cognito login/logout. No RDS migration or real backend database
connection has been performed yet: administrator password must be entered locally.
No queue consumer, telephone call or cloud deployment was started.
Next: follow portal-backend.md setup, then live employee/engineer acceptance.

## Background dispatch — implementation, 13 October 2026

User confirmed live portal setup PASS, employee ticket creation and engineer all-
ticket listing. Those acceptance checks are now complete (supersede earlier pending).

Added leased outbox publisher, SQS adapter, calls-disabled LangGraph entry workflow,
append-only preflight receipts, limited worker login setup and explicit retry/replay.
Duplicate delivery, due-time/generation checks and queue/database failure recovery
are implemented without ticket lifecycle transitions or telephone/model calls.

Verified default AWS profile belongs to 346401055256; read-only queue check found
SSE-SQS and configured DLQ after five receives. Actual boto3 adapter check passed.
No live sends/receives. Worker migration/login must still be applied locally with
administrator password; live worker processing is not yet verified. Restart the API
after applying the additive migration to load schema-version compatibility.
See background-worker.md for setup, bounded tests, recovery and remaining gates.

Background slice checks: 64 Python tests plus 10 subtests, 24 worker PostgreSQL
checks and the existing 22 portal PostgreSQL checks pass. No live worker database
mutation, send/receive, or multi-session race verification is claimed.

Worker setup fix: RDS remained at 0002_portal with no sahayak_dispatch role after
the failed attempt. Reproduced psycopg ProgrammingError from SQLAlchemy passing an
empty parameter mapping to DDL containing %ROWTYPE. Trusted repository scripts now
execute without a parameter argument in the existing transaction. Verified the
fixed executor on RDS with harmless PL/pgSQL/LIKE statements inside a read-only
transaction. 66 Python tests plus 10 subtests pass. Full worker migration still
requires the user's local administrator-password entry. Recovery file retained.

## Worker configuration verification — 14 October 2026

Fixed dotenv's string "false" conversion for the calls-disabled Literal setting;
all enabled/ambiguous values still fail closed. Added generated-dotenv regression
coverage and field-only configuration errors. 75 tests plus 10 subtests pass.
Live status succeeds: zero due, one future request, no exhausted/published events.
One live calls-disabled cycle returned publisher idle / consumer idle. No model
requests or calls; due-event processing remains unverified until a request is due.

## User-confirmed live dispatch acceptance — 14 October 2026

User ran the migrated worker: publisher published, consumer ready_calls_disabled.
Status confirmed one published event and one durable preflight receipt, one future
request, zero due/exhausted events and no attention items. Calls remain disabled.
Core portal POC and queue preflight acceptance are complete. Conversational Agent,
Voice Connect, real human handoff and full integration/reliability gates remain.
See handover-2026-10-14.md for the next-session summary.


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

## Saaras recorded turn — 15 October 2026

Added bounded multipart Saaras v3 recognition, WAV validation and voice-demo CLI.
Verified one live synthetic Hindi question through STT, retrieval, chat and TTS.
Result: output/agent/6cf9cf82-ba02-43e0-8f2c-a280d4523ce8.json and .wav.
117 tests + 10 subtests pass, including malformed audio, invalid transcripts,
redacted provider failures and prevention of downstream work after STT failure.
Human speech/noise, microphone capture and continuous streaming are unverified.
Remaining safety/tool/memory/hosting gates from the prior increment still apply.

## Microphone command — 15 October 2026

Added microphone-demo with explicit start, bounded capture, safe errors, Ctrl+C
handling and macOS reply playback. Optional sounddevice/PortAudio import verified.
128 tests and 10 subtests pass. Microphone capture is mocked in tests: permission,
real voice and physical speaker output remain for user acceptance. No recording
or extra model request was made during this increment. Continuous conversations,
streaming and previously documented production gates remain pending.
