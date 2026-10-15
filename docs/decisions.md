# Decision log

- 2026-10-11: User authorized development directly in the Desktop application
  repository. This resolves the repository/location authorization item in the
  handoff for local implementation; it does not authorize paid deployment/calls.
- Start with provider-independent intake rules using the standard library.
  Preserve the existing starter and dependency lockfile during this slice.
- Preserve English substring priority behavior exactly, including broad matches
  such as 'down' in 'download'. Hindi/Hinglish urgency and more precise matching
  remain evaluation work, not silently changed behavior.
- Reject naive callback datetimes. Natural-language callback interpretation is
  separate and must confirm ambiguity in Asia/Kolkata before validation.
- Python 3.14 is retained provisionally after the installed SDK import check.
  Validate the full voice/AWS stack before finalizing production runtime support.

- 2026-10-12: User authorized portal development in this repository, starting
  with login before ticket features. React + TypeScript selected for this slice.
- Use oidc-client-ts for code/PKCE/state/nonce and jose for explicit ID-token
  signature validation. Cognito groups in the browser are presentation only;
  backend verification and database role enforcement remain mandatory.
- Login preview keeps tokens in memory, disables automatic renewal and requires
  sign-in after reload/expiry. No browser client secret. Session persistence may
  be revisited with an explicit backend/session design.
- User-provided pool/client IDs configured locally; public metadata confirmed.
  Dependencies pinned and locked; Node 25.9.0 build/browser checks passed.
- Existing user setup overrides old planning assumptions: two users with a
  combined engineer/admin profile, and public RDS restricted to the laptop IP
  for the POC. No management EC2 or NAT gateway provisioned.

- 2026-10-13: Latest user correction restores employee own-ticket scope and
  dedicated limited database login. Engineers see all tickets and claim only
  unassigned human escalations; assigned engineers record outcomes. One portal.
- Enforce identity/group/profile intersection in the API, not browser claims.
  Check Cognito userInfo on every authenticated request to reject revoked sessions.
- Adopt compatible existing schema without recreating user profiles. Migrations
  and runtime grants require local administrator entry; never collect passwords
  in chat or expose database credentials in frontend configuration.
- Embedded PostgreSQL tests supplement mocked API/browser checks; live RDS and
  concurrency verification must be reported separately.

- 2026-10-13: User authorized background worker development with calls disabled.
  Use the supplied standard SQS queue and verified default AWS profile. No new
  cloud resources, IAM policies or credentials provisioned.
- Initial worker executes a deterministic local LangGraph preflight and records
  an operational receipt, not an answered call or fake business-state transition.
  Exact lifecycle is retained. Conversational/AgentCore/telephony integration remains
  separate; no live-call enable switch exists in this release.
- Poll due outbox rows for this small local slice; no EventBridge provisioning.
  Unique per-claim fencing token, bounded publish retries, receipt-before-delete
  and explicit retry/replay preserve at-least-once recovery. Preflighted tickets
  will require deliberate authorized re-dispatch in a later live-calling release.

- 2026-10-15: User authorized implementation of the next Sahayak Agent increment.
  Preserve the three component names. Local synthetic LangGraph RAG and Bulbul
  REST synthesis added; no employee endpoint, ticket mutations or calls enabled.
- Titan Text Embeddings V2 / S3 Vectors are the working RAG pilot after the Cohere
  agreement payment failure. See rag-pilot-2026-10-15.md for resource IDs.
- Bulbul v3, shubh and 24 kHz WAV are provisional live-test settings. Streaming
  and final voice selection remain open. HTTP adapter uses documented language_code.
- DeepEval 3.8.9 added as an optional pinned eval group. Explicit bounded Sarvam
  judge, local reports, no platform upload; scores advisory pending calibration.

### 15 October 2026 — recorded speech development increment
- User authorized adding Saaras speech recognition to Sahayak Agent.
- Pin saaras:v3 with transcribe mode provisionally; official REST API still
  supports v3. Do not silently migrate to the newer default v4.
- Start with explicit synthetic WAV inputs and single-turn replies. REST is a
  compatibility step; selected streaming architecture remains required.
- No microphone recording, telephony, ticket writes or production enablement.

### 15 October 2026 — microphone development command
- User authorized microphone input. Add optional pinned sounddevice 0.5.5 group.
- Explicit Enter-to-start, 12-second default / 25-second maximum, one turn only.
- Do not retain raw microphone audio; existing synthetic report retention applies.
- Automatic local macOS playback occurs only after capture closes and reply saves.
- No microphone was opened during automated implementation checks.
