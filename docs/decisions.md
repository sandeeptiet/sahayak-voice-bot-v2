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
