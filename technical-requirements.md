# Sahayak voice agent — technical requirements and coding handoff

Version: 1.0 • Consolidated: 10 October 2026

## 1. How the coding agent must use this document

This is a self-contained handoff for a new implementation of Sahayak, an internal employee IT helpdesk voice agent. Read this entire file before designing or coding. Do not assume access to the originating ChatGPT/Codex conversation.

This document consolidates the latest user decisions and supersedes conflicting older architecture proposals. Explicit subsequent user instructions take precedence. Do not silently turn a proposed component into a finalized decision. Maintain a decision log and update this document as choices are resolved.

Status meanings:
- **Selected:** retain the technology or behavior unless the user changes it. Account access, versions, regional availability and costs still need verification.
- **Proposed baseline:** use as the starting design, but validate compatibility and cost before committing the deployment.
- **Open:** do not invent a final answer. Continue independent work and resolve the decision before implementing dependent behavior.

This handoff authorizes planning context, not provisioning paid resources or calling employees by itself. Obtain the user's execution scope when starting the implementation. No cloud deployment, live credentials, new application code or verified end-to-end integration is supplied by this document.

## 2. Purpose and scope

Build a portfolio POC that demonstrates production-oriented engineering. Employees submit IT tickets, receive automated phone support, confirm successful fixes, or receive human follow-up. Reuse the old business analysis, lifecycle and reviewed knowledge documents; write the new application code.

The target is **30% autonomous Tier 1 ticket resolution**, not an achieved result or a guaranteed 30% reduction in engineer time. The old README mentions 30–40%; use the user's 30% POC target. Measure quality, human handoffs, response time and cost per case, then validate savings against actual results.

Scope includes hardware, VPN, Microsoft 365, network, software, account access and other IT issues. Hardware upgrades may require human approval/fulfilment rather than a spoken fix. HR and company-policy PDFs do not automatically expand the bot into an HR agent.

Initial language scope: **English, Hindi and Hinglish**, proposed and explicitly retained in the business slide. Implement evaluation coverage for all three; do not claim validated language quality before testing.

Planning constraints:
- Indian employee mobile numbers and Asia/Kolkata callback interpretation.
- Approximately 4–5 POC users. Suggested fixture: 3 employees, 1 engineer and 1 application administrator.
- INR 2,000/month planning ceiling, not a validated all-in quote. Paid telephony minimums and always-on cloud infrastructure may exceed it.
- The user's AWS account is 4–5 years old. Do not assume new-account RDS free-tier eligibility.
- The user prefers managed services and does not want to install PostgreSQL locally.

Out of scope unless explicitly added: public marketing calls, autonomous remote desktop access, remote-access-code relay, irreversible account actions by the AI, synchronous live AI-to-engineer transfer, public web search, browser automation, and arbitrary code execution by the support agent.

## 3. Technology decisions

| Component | Technology | Status / constraint |
|---|---|---|
| Backend language and API | Python, FastAPI | Selected. Pin supported versions after compatibility checks. |
| Frontend | React + TypeScript | Proposed baseline for employee and engineer role views. |
| Workflow | LangGraph; selective LangChain adapters | Selected. One authoritative workflow, not two autonomous agent loops. |
| Primary inference provider | Sarvam AI direct API | Selected. Exact primary chat model pending evaluation. |
| Chat model candidates | sarvam-105b and sarvam-105b-conversations | Candidates, not frozen defaults. Verify actual account access and tool behavior. |
| Speech recognition | Sarvam Saaras streaming | Selected family. Exact model/API/plugin versions pending. |
| Speech synthesis | Sarvam Bulbul streaming | Selected family. Prior proposal mentioned v3; verify and pin rather than assuming. |
| Real-time media | LiveKit + LiveKit Agents Python + SIP integration | Selected. Managed LiveKit service proposed; worker hosting open. |
| Indian telephony | Exotel SIP trunk/PSTN connectivity | Selected, **only telephone provider requested**. No Twilio/secondary carrier fallback in the new scope. SIP plan, number and access pending. |
| Employee identity provider | Amazon Cognito User Pool, managed login | Selected. Essentials tier is the planning choice; verify pricing/features before provisioning. |
| Agent hosting | Amazon Bedrock AgentCore Runtime | Selected for the LangGraph service; not a host for every application component. |
| Agent tools | AgentCore Gateway | Required. Tool access layer, not the LLM router or SIP gateway. |
| Tool authorization | AgentCore Policy / Cedar | Required. Availability and supported target behavior must be validated. |
| Memory | AgentCore Memory for short-term/checkpoint integration and long-term memory | Required. Integration details below. |
| Content safety | Bedrock Guardrails ApplyGuardrail plus deterministic backend checks | Selected direction. Applicable independently of the conversational model provider. |
| Knowledge retrieval | Amazon Bedrock Knowledge Bases | Selected replacement for Qdrant. |
| Document originals | Amazon S3 | Selected. Explicit ingestion/sync required. |
| Knowledge vector backend | Amazon S3 Vectors | Proposed baseline, conditional on region, quality, latency and price. |
| Embeddings | A supported Bedrock embedding model | Open. Evaluate multilingual retrieval and exact IT error codes. |
| Business database | Amazon RDS for PostgreSQL | Selected initial managed host. Preserve PostgreSQL-provider portability. |
| Database access | SQLAlchemy ORM + psycopg driver + Alembic migrations | Selected design. No cloud-specific SQL/data API in business logic. |
| Database Service | AWS RDS | Selected |
| Dispatch | Transactional outbox + Amazon SQS | Proposed reliability baseline. Duplicates are expected and handled. |
| Scheduling | Amazon EventBridge Scheduler | Proposed baseline for due callbacks/retries. |
| Public HTTP entry | Amazon API Gateway + FastAPI | Proposed. Lambda adapter for request/response API is provisional; benchmark DB connectivity/pooling and costs. |
| Tool handlers | Authenticated API or Lambda targets behind AgentCore Gateway | Proposed implementation. Share domain validation with the human-facing API. |
| Telemetry | OpenTelemetry, AgentCore Observability, CloudWatch | Core implementation requirement. |
| Workload credentials | IAM, Secrets Manager; AgentCore Identity where supported/useful | Selected direction. Employee login and workload identity are separate. |
| Evaluation | DeepEval + deterministic tests, with pytest proposed | Required evaluation program. Sampled AgentCore Evaluations is a follow-on demonstration. |
| Packaging and delivery | Docker, AWS CDK in Python, GitHub Actions | Proposed baseline. Exact repository/build layout is not frozen. |

No exact SDK versions, region, speech voice, embedding model, LLM fallback model, frontend host or voice-worker host has been finalized. Do not present them as selected.

## 4. Business invariants

### 4.1 Employee experience

1. Sign in and derive the employee identity from verified authentication.
2. Obtain the registered phone from a trusted profile. Do not ask for it again on every ticket or trust a browser-supplied replacement.
3. Capture category, problem description, optional asset tag and preferred callback time; populate department/name from trusted profile where available.
4. Create a unique ticket reference. Let the employee view their own tickets and status.
5. Derive priority automatically; employees do not directly select it.
6. Call promptly unless a future callback was selected. Never call before the due time.
7. Introduce Sahayak, reference the reported issue and ask whether now is convenient.
8. Give concise, interruptible spoken guidance based on relevant approved knowledge.
9. If relevant guidance is unavailable, explain the limitation and offer escalation. Never invent a fix.
10. Complete an AI-handled ticket only after explicit employee confirmation that the fix worked; silence is not confirmation.
11. Save attempted steps, outcomes and the resolution/escalation reason.
12. Honor callback requests in normal language. Clarify ambiguous times and confirm the intended future time.

### 4.2 Priority rules inherited from the repository

- High: account_access, network.
- Medium: vpn, microsoft_365, hardware, other.
- Low: software.
- Levels: low, medium, high, critical.
- Raise one level, capped at critical, if the description contains an existing urgency phrase: `cannot work`, `can't work`, `locked out`, `urgent`, `critical`, `down`, `not working at all`, `completely stuck`.

Keep the rules explicit and testable. These English substring rules are the old baseline, not proof of good triage. Document any approved refinement and evaluate Hindi/Hinglish urgency handling. Priority assignment does not imply an unagreed priority-based dialing SLA.

### 4.3 Human follow-up

- Escalation creates a durable queue item, ends the AI call cleanly and tells the employee a human will follow up.
- Show employee/ticket context, priority, original issue, tried steps and outcomes.
- Engineers self-assign with exclusive ownership, initiate click-to-call or work offline, and record completed/failed with an outcome note.
- Human calls are ordinary two-party conversations without an AI agent joining automatically.
- Support pending and outcome-history views, including failed outcomes.
- Human callback scheduling keeps the ticket in human support. Show it as due at the scheduled time. Do not automatically redial it through the AI pipeline.

### 4.4 Exact ticket lifecycle

| From | Event | To |
|---|---|---|
| No ticket | Employee submits | new |
| new | Employee answers AI call | in_progress |
| new | Employee withdraws before dialing | cancelled |
| new | Three unanswered automated attempts exhausted | failed |
| in_progress | Employee explicitly confirms fix worked | completed |
| in_progress | AI cannot resolve | transferred_to_human |
| in_progress | Employee requests later callback | new |
| transferred_to_human | Engineer resolves | completed |
| transferred_to_human | Engineer marks unsuccessful | failed |
| transferred_to_human | Engineer schedules own callback | transferred_to_human |

Completed, failed and cancelled are terminal. Do not add `closed`, `reopened` or other business states. Assignment is a field, not a status. Maintain call-attempt and operational recovery state separately from business ticket status.

Every transition, including creation and human rescheduling, must have an atomic audit record containing previous/new state, trusted actor, timestamp and note/reason as applicable. The database/domain layer validates transitions; a model's requested enum alone is insufficient.

Unanswered retry reset rules across callback campaigns, busy/rejected/provider-failure classification, and unrecoverable mid-call failure behavior are **open decisions**. Keep total dial count separate from unanswered retry count. Do not silently add `in_progress → failed` or reset retry budgets indefinitely.

## 5. Component boundaries and end-to-end flow

Recommended separation:
- Employee/engineer frontend and authenticated FastAPI application.
- Ticket domain service and portable PostgreSQL persistence.
- Outbox publisher, scheduler and dial controller.
- LiveKit media worker integrating Sarvam speech.
- LangGraph service hosted in AgentCore Runtime.
- Application LLM router and provider adapters inside the reasoning service boundary.
- AgentCore Gateway/Policy and tool handlers.
- Knowledge ingestion/retrieval, memory, evaluation and telemetry modules.

Normal path:
1. Portal request passes authentication, ownership checks and validation.
2. Transaction commits ticket, initial audit record and dispatch outbox entry.
3. Dispatch publishes durable work, respecting preferred callback time.
4. Controller checks state/version, claims the dial attempt and requests a LiveKit SIP participant via the Exotel trunk.
5. Exotel connects through telephone networks to the employee's Jio/Airtel/other operator.
6. A verified answered-call event advances the ticket to in_progress.
7. LiveKit carries audio; Sarvam transcribes it. The voice adapter sends authenticated text turns to the LangGraph service.
8. Input safety checks, workflow, memory/retrieval and LLM routing determine a response or tool proposal.
9. AgentCore Gateway and Policy authorize tool calls. Handlers enforce domain rules and persist results.
10. Output safety checks precede speech. Sarvam TTS audio returns through LiveKit, Exotel and the phone network.
11. Persist the confirmed outcome or callback, audit it, and close the call cleanly.

The LiveKit-to-AgentCore adapter is a **validation milestone**, not a proven drop-in integration. It must propagate correlation IDs, streaming responses, cancellation, deadlines and authentication. Only LangGraph decides workflow outcomes; the media worker must not run a competing autonomous LLM/tool loop.

Do not send live audio through a short-lived Lambda HTTP request path. Worker hosting and latency must be proven with a small vertical prototype before broad implementation.

## 6. Identity and authorization

- Cognito User Pool with managed login; planned browser flow is authorization code + PKCE, without a browser client secret.
- Start with admin-created POC users and employee/engineer/application-admin role groups.
- Use verified stable subject identifiers, not email or employee IDs typed into requests, as identity anchors.
- Validate token signature, issuer, intended audience/client, expiry and token use using the correct rules for the selected token type. Do not interchange ID and access tokens without a documented validation design.
- Fetch/store phone in a trusted profile flow. A phone claim is not necessarily proof of verified ownership; establish profile trust/verification before calling.
- Derive authorized ticket scope server-side. Employees access only their own tickets. Engineer and admin scopes must be explicit.
- Propagate authenticated workload identity and trusted actor/ticket context to Runtime and tools. Never accept arbitrary identity or ticket authority from model arguments.
- Apply least privilege to AWS roles. Runtime must not have a parallel direct ticket-mutation path bypassing Gateway/Policy.
- Cognito authenticates people. AgentCore Identity manages supported outbound workload credentials. Neither replaces domain authorization.

## 7. PostgreSQL and provider portability

Initial host: RDS PostgreSQL. Future supported targets may include Azure Database for PostgreSQL and DigitalOcean managed PostgreSQL.

Requirement: switch between compatible PostgreSQL hosts using configuration/secret/deployment changes, without changing business code. Keep PostgreSQL dialect unchanged. Use SQLAlchemy + psycopg and Alembic. Avoid embedding AWS SDK calls, RDS Data API assumptions, provider hostnames or IAM-token logic in repositories/domain functions.

Configuration includes host, port, database, username, secret reference/password, TLS verification mode/CA bundle, pool size and timeouts. Build connection URLs safely rather than concatenating unescaped credentials. Use verified TLS. Cloud-specific token authentication needs an isolated credential adapter if chosen later.

A hosting switch still requires data/schema migration, supported version/extension checks, connectivity/firewall configuration, TLS certificates, permissions, backup/restore and cutover validation. An ORM does not migrate data automatically. Do not claim the whole AWS application becomes cloud-portable because its PostgreSQL connection is portable.

Suggested schema responsibilities, to finalize through migrations:
- tickets: employee/profile reference, category, description, asset, priority, callback time, status, assignment, timestamps, outcome summary and concurrency version.
- ticket_status_history: append-only transition evidence and trusted actor.
- call_attempts: distinct call/provider IDs, timestamps, answered/unanswered/provider-failure result, retry campaign, counters and reason.
- troubleshooting_steps / ticket evidence: what was suggested, what the employee tried, outcomes, source passages and explicit confirmation reference.
- outbox and processed-event/action receipts: durable dispatch and deduplication.
- callback records/scheduler references and generation/version tokens.
- usage/cost ledger with provider attribution.

Enforce atomic assignment and status transitions using locking or optimistic concurrency. Make the ownership/race strategy explicit. Use migrations from a clean database and validate rollback/recovery for important schema changes. Budget connections carefully, especially with serverless API scaling.

No local PostgreSQL installation is required for the user. Tests should support mocks plus a dedicated managed test database/schema. A disposable container test database is optional if the user later accepts it, not a prerequisite.

## 8. Dispatch, callbacks and telephony safety

- Preserve the business dial flow: controller → LiveKit SIP bridge → Exotel trunk → public telephone interconnection → employee operator → phone.
- SIP handles call signaling; audio flows over the media connection. Do not reverse the chosen initiation flow by accidentally implementing Exotel-first API calling.
- Validate Exotel SIP entitlement, caller number, credentials, approved destinations and provider onboarding requirements before live tests. Use the user's authorized test numbers only.
- Handle duplicate/out-of-order delivery and webhook events. Verify provider callbacks using the provider's supported authentication mechanism.
- Persist a dial claim before initiating an external call. Reconcile uncertain outcomes using provider/call identifiers; never blindly redial after a timeout.
- Re-read ticket state, schedule generation and due time immediately before dialing. Coordinate cancellation with the dial claim so a cancelled ticket is not called.
- Store UTC-aware timestamps; display and interpret user callback times in Asia/Kolkata. Never use naive server-local time as authority.
- Invalidate stale scheduled work after cancellation, reschedule or terminal resolution.
- Missed dispatch work must recover without relying only on transient database notifications.
- Use bounded retries, dead-letter handling and an operational recovery record. Scheduler delivery is not an exactly-once guarantee.
- A no-answer cap is not a provider-error classification policy. Resolve open retry semantics before implementing them.

## 9. LLM routing and fallback — required

Rebuild the configurable `llm_gateway.py` concept as an application-owned router. It is distinct from AgentCore Gateway and the LiveKit SIP gateway.

The old file chooses a configured model key, sequentially tests its routes and pins one provider for the whole call. Despite wording about a race, it does not race routes. It neither switches between registered models automatically nor fails over during an active conversation. Do not reproduce these limitations as requirements.

New requirements:
- Registry of logical model aliases, provider adapter, endpoint, provider model ID, secret reference, enabled state, context window and evaluated capabilities.
- Task policy selecting primary alias and ordered fallback aliases. Voice is the initial task; later summaries/evaluators can have separate policies when actually needed.
- Sarvam direct API as primary provider. No dependency on Sarvam being listed in OpenRouter or Bedrock.
- Another Sarvam model may help a model-specific failure but shares provider outage/quota risk. Select an independent-provider fallback for that resilience requirement; exact provider/model is open.
- Config-only primary/fallback changes for supported adapters. A different API protocol may need an adapter once. Test any new model before enabling it.
- Eligible transport errors, timeouts, rate limits and server errors can trigger fallback. Respect Retry-After within the voice deadline and bound total retries/fallback depth/cost.
- Detect time-to-first-token and stalled-stream degradation. Tune thresholds using measured voice performance. Circuit breakers temporarily skip unhealthy routes and probe recovery without constant model switching.
- Permit controlled switching during a call at safe generation boundaries, preserving instructions, relevant history, retrieved evidence, language, ticket state and completed tool results.
- Normalize provider message/tool formats and fit context to the chosen model. Never assume matching API shapes imply matching tool behavior.
- Cancel the prior generation and discard late results. Employee interruption is cancellation, not a reason to fail over.
- Never splice a fresh model response onto partial spoken output. Track what the employee actually heard and recover coherently.
- Persist idempotent tool receipts. A timed-out tool might already have succeeded; reconcile before retrying. Never duplicate a ticket mutation, callback or phone call.
- Distinguish availability/latency from quality. Invalid schemas/tool arguments can trigger bounded repair. Assess broader relevance and language quality with evaluations, not a model's self-reported confidence.
- Missing knowledge leads to the established human handoff. Safety refusals must not trigger model shopping to bypass policy.
- If every model fails, use a predefined safe message if speech works, record a durable recovery item and avoid false completion. Final lifecycle handling for an unrecoverable mid-call outage remains open.
- Log model, route, reason, attempts, latency, tokens, validation result and estimated cost without leaking private content.

This specifies LLM fallback only. STT/TTS resilience is a separate open decision. It does not authorize another telephone provider.

## 10. Knowledge base and document handling

Selected ingestion path: reviewed source PDFs → versioned S3 originals → explicit Bedrock Knowledge Bases ingestion/sync → supported embedding model → configured vector backend (S3 Vectors proposed).

Selected response path: LangGraph → Gateway/Policy → search_kb handler → Bedrock **Retrieve** → passages with metadata → Sarvam answer → output guardrails → TTS.

- Do not restore Qdrant or require the user to manually insert vectors.
- Uploading an S3 file alone does not guarantee it is indexed. Run/monitor explicit sync jobs and handle failures, updates and deletions.
- Review parser/chunking results before accepting a document. Start with text parsing for the existing text PDFs; paid advanced parsing/reranking needs a justified test.
- Preserve document identity, version, topic and page/source references. Record evidence associations with the ticket.
- Enforce knowledge access/topic filters server-side. A model may suggest a query, not its authorization scope.
- Treat retrieved text as untrusted data, never as instructions to change tool permissions or reveal secrets.
- Use Retrieve, not RetrieveAndGenerate, for the planned Sarvam-generated answer path.
- Knowledge Bases handles document/query embedding with its selected model. Do not assume Sarvam supplies supported embeddings.
- Validate Hindi/Hinglish questions against existing English documents and exact codes such as VPN errors. Prior design noted semantic-only search for the proposed S3 Vectors integration; recheck current capabilities and measure exact-code retrieval before finalizing it.
- Knowledge content does not belong in employee long-term memory. Employee memory does not become approved company policy.

Ten old PDF volumes were inventoried: VPN/remote access; password/account management; Microsoft 365; laptop/hardware; network/Wi-Fi; software installation/licensing; email/Outlook; IT security policies; HR employee FAQ; general company policies. Their contents have not been audited in this redesign. Inspect actual paths in the repository because some filenames contain literal encoded characters.

## 11. State, checkpoints and memory

Use three distinct authorities:
1. PostgreSQL: business ticket truth, ownership, schedule, action receipts and audit.
2. Workflow state/checkpoints: conversational progress and safe resumption.
3. Knowledge Base: approved troubleshooting instructions.

AgentCore Memory is required for useful short-term and long-term demonstrations. Proposed official LangGraph integration classes are `AgentCoreMemorySaver` and `AgentCoreMemoryStore`; verify their current package imports, SDK support and semantics before coding.

Identity mapping:
- actor_id: trusted, stable employee identifier, tenant-scoped if tenancy is introduced.
- thread_id: one ticket workflow, reused across its callbacks.
- call_id: a new physical phone connection.
- turn_id and action_id: identify generation and side effects.
- Runtime session identity: separate from ticket/call identity; follow actual runtime lifecycle constraints.

Checkpoint completed troubleshooting steps, pending questions/reboot, confirmed language and tool results at useful boundaries. On resume, reload current ticket authority and current source versions. Do not repeat completed steps automatically.

Long-term memory may store language/speaking-pace preferences and limited prior-case summaries with source/date. Extract selectively and asynchronously; do not depend on long-term extraction for immediate state. Managed extraction does not imply it uses Sarvam; a Sarvam-only extraction requirement would need a separate supported design.

Checkpoint replay must not replay external actions. Persist receipts and distinguish generated, approved, spoken and interrupted text. A checkpoint does not keep a phone connection alive or itself authorize redialing.

Use scoped retrieval, retention/deletion rules and redaction. Never store passwords, MFA codes or unnecessary sensitive profile data in model memory. Exact retention periods are open. Namespacing alone is not an access-control mechanism.

## 12. Tools, policy and guardrails

Initial logical tool contracts:
- search_kb(query, optional confirmed category): authorized passages and provenance.
- get_ticket(): context of the server-bound authorized ticket.
- update_ticket(outcome, summary, evidence reference, expected version): validate source state, permission and outcome evidence.
- reschedule_call(future timestamp, reason, expected version): validate employee intent and the future callback.

Exact request schemas remain an implementation task. Ticket identity and authorization must be server-bound, not freely chosen by the LLM. `completed` needs reference to genuine employee confirmation, not only a generated `confirmed=true` field. Persist the supporting turn and validate the workflow's confirmation state; ambiguous speech must lead to clarification.

AgentCore Policy/Cedar authorizes tool invocations. Backend domain code enforces ownership, transitions, confirmation, concurrency and idempotency. Human API actions use the same domain rules. Policy alone cannot prove what the employee meant.

Apply content checks before model inference and before releasing speech. Buffer coherent output units for validation and measure added latency. Test each safeguard's coverage in English/Hindi/Hinglish. Do not bypass guardrails silently when their service fails; return a predefined safe response and record recovery.

Protect against prompt injection in user speech, retrieved documents and memory. Do not expose credentials or broaden permissions due to a model instruction. No remote control or irreversible account changes by the AI.

## 13. Observability, evaluation and success measurements

Correlate ticket_id, call_id, turn_id, workflow/session, trace and action IDs across API, dispatch, telephony, STT, Runtime, models, tools, retrieval and TTS. Collect timings and errors, with redacted content and bounded retention. Instrument external providers explicitly; AWS telemetry alone does not capture every Sarvam/LiveKit step.

Build a versioned golden dataset before choosing final model defaults. Cover categories, accents, English/Hindi/Hinglish, ambiguous requests, absent knowledge, injection, interruption, callback and handoff cases.

Evaluation layers:
- Deterministic tests for state transitions, ownership, time validation, schemas and repeated events.
- Retrieval tests for relevant passages, exact codes, access filters and source provenance.
- DeepEval quality/grounding evaluations with sampled human review. Judge models are not unquestionable truth and incur cost.
- Voice tests for transcription errors, spoken clarity, barge-in and end-to-end latency.
- Tool-use tests for valid arguments, correct outcomes and false-completion prevention.
- Failure-injection tests for model failover, guardrail outages, provider timeouts and interrupted tools.
- Offline comparisons before configuration changes; sampled AgentCore Evaluations later if budget and service availability permit.

Suggested metric definitions to approve and label in reports:
- Autonomous resolution: eligible evaluated tickets completed by AI with employee confirmation / eligible evaluated tickets. Publish denominator and exclusions.
- Human handoff: transferred tickets / eligible tickets in the same cohort.
- Quality: correct/relevant supported guidance and confirmed outcomes, with an explicit false-completion rate.
- First-contact time: ticket creation or scheduled due time to first attempted contact; separately report time to answered contact.
- Response time: end of employee utterance to first audible response, with stage breakdown and p50/p95.
- Cost per case: all attributed variable costs / handled cases; separately show allocated fixed hosting cost and evaluation cost.
- Savings: measured baseline human cost/time minus AI costs plus residual human effort for a comparable cohort. Never infer savings solely from containment percentage.

Numerical latency/quality release thresholds are open. Propose them from the baseline tests and record them before presenting pass/fail claims.

## 14. Cost and deployment controls

Select a region only after verifying Runtime, Memory, Gateway, Policy, Knowledge Bases, vector backend and required model/guardrail capabilities. The screenshot's N. Virginia region was not a final architecture selection. Indian telephone routing does not guarantee Indian processing/data residency for AI services.

Produce a priced deployment plan covering Exotel setup/rental/minutes, LiveKit media/worker, Sarvam STT/TTS/LLM, fallback inference, AgentCore services, Guardrails, document/query embeddings, S3/vector operations, RDS/storage/backups, API/compute, queue/scheduler, logging, secrets and network/NAT/egress costs. Do not enable expensive default managed infrastructure merely because a template does so.

Use daily usage ceilings, concurrency/call-duration limits, queue controls and a kill switch. Billing alerts are useful but are not a hard spending cap. Exact limits are open and must be configured before unattended calls.

RDS operating assumptions from prior verified discussion: a free-tier preset is not entitlement; an old account should budget paid usage. Stopping an eligible RDS instance stops instance compute charges but storage/chargeable backups remain, and it automatically restarts after 7 days. Recheck current service rules before deployment. The earlier screenshot showed USD 0.019/hour, not 0.19; it was not an all-inclusive cost estimate.

Propose a small Single-AZ POC database and secure connectivity, subject to current prices. Do not expose it broadly to the internet. Provide start/stop/teardown instructions and explain retained data/snapshot charges. Infrastructure changes must be reviewable and distinguish data deletion from stopping compute.

## 15. Coding and repository practices

- Keep core domain logic independent of cloud SDKs and model clients. Provider adapters implement explicit interfaces.
- Centralize typed configuration; fail fast for missing required settings. Commit an example configuration containing placeholders only.
- Store secrets outside source control and browser bundles. Redact tokens, phone details and sensitive prompts from logs/errors.
- Pin dependencies and commit lockfiles. Verify APIs against current official documentation rather than copying obsolete snippets.
- Use async I/O appropriately, bounded timeouts and cancellation. Do not block audio work on slow nonessential analysis.
- Keep prompts, tool schemas, policy and evaluation datasets versioned.
- Keep all external side effects idempotent/reconcilable. Exactly-once delivery must not be assumed.
- Favor a modular POC over unnecessary microservices; preserve required deployment boundaries without multiplying services for presentation value.
- Supply meaningful tests for business invariants and integrations, not tests that simply mirror implementation.
- Separate local mocks, integration tests and live paid tests. Label mocks clearly and never describe mocked flows as verified live integrations.
- Keep a README, decision log, setup/teardown guide and implementation-status file so another coding session can resume without this chat.
- In the new code repository, add a short AGENTS.md pointing to this file if the coding tool supports it. Do not overwrite unrelated instructions.
- The current ChatGPT project directory is a reference workspace, not the new code repository. Files under its sources/ are read-only synced material. Confirm the new repository location before scaffolding application code.

## 16. Implementation sequence and acceptance gates

1. **Foundation:** review this handoff and old sources; create the new repository structure, typed config, interfaces, fixtures and decision log. Resolve only blockers for the next slice.
2. **Business core:** migrations, authenticated intake, scoped lookup, priority, state-machine/audit, assignment and human outcomes. Test invalid transitions and cross-user access.
3. **Critical integration spike:** prove a Sarvam speech/LLM turn through LiveKit and the AgentCore-hosted workflow with cancellation and guardrails. Validate tool calling and total latency before expanding.
4. **Knowledge and tools:** review/import PDFs, sync Knowledge Bases, implement Gateway/Policy wrappers, authorized retrieval and confirmation-gated outcomes.
5. **Durable calling:** outbox/queue/scheduling, Exotel SIP, verified answer/failure events, deduplication and cancellation races. Finalize retry policy first.
6. **Memory and fallback:** checkpoint callback resumption, scoped preferences, configured model failover, streamed-output recovery and side-effect safety.
7. **Engineer workflow:** exclusive assignment, due callback queue, direct human call and history.
8. **Evaluation and delivery:** comparative model tests, multilingual golden path, failure injection, cost report, selected AWS deployment, CI and teardown/runbook.

Minimum acceptance scenarios:
- Employee sees only their own tickets; engineer cannot act outside authorized scope.
- Registered profile phone is used, with no repeated ticket-entry requirement.
- Priority follows the documented rules.
- Ticket creation and status changes always have audit evidence.
- Future callback never dials early; cancelled or terminal tickets never dial.
- Duplicate messages/callbacks do not cause duplicate phone calls or updates.
- Answer transitions to in_progress; three qualifying unanswered attempts fail according to the agreed campaign policy.
- AI completion requires explicit employee confirmation; silence/ambiguous text cannot complete it.
- Missing/irrelevant knowledge produces human follow-up rather than invented instructions.
- Engineer rescheduling stays transferred_to_human and never re-enters AI dialing.
- Two engineers cannot successfully claim the same unassigned ticket simultaneously.
- Callback resumes prior steps without replaying completed actions.
- Memory/knowledge retrieval cannot cross employee authorization boundaries.
- Primary-model timeout/429/server failure triggers the configured fallback within the chosen deadline.
- Partial output, employee interruption and uncertain tool completion do not duplicate speech/actions.
- Guardrail rejection remains enforced across models. All-models-down behavior is safe and durable.
- PostgreSQL connection points to another compatible test host using configuration only, after schema/data preparation.
- English/Hindi/Hinglish scenarios meet recorded evaluation thresholds.
- A real authorized end-to-end phone test passes before declaring telephony complete.
- Cost and teardown instructions match deployed resources, not a hypothetical free tier.

## 17. Open decisions the coding agent must track

| Decision | Resolve before |
|---|---|
| New repository path/name and implementation authorization | Scaffolding/deploying |
| AWS region and actual service availability | Cloud provisioning |
| Exact Sarvam speech/chat versions, TTS voice and SDK versions | Live integration |
| Primary chat model and independent fallback model/provider | Enabling fallback |
| Voice worker/frontend/API hosting and network path | Deployment plan |
| Exotel SIP plan, caller number, account approval and prices | Calling |
| LiveKit-to-Runtime transport, streaming/cancellation support | Full voice implementation |
| Embedding model/vector backend/parser and multilingual quality | KB production of demo answers |
| Retry campaign reset, total dial cap and no-answer classification | Scheduler/retry implementation |
| Dropped-call/all-model-outage lifecycle handling | Recovery implementation |
| Timeouts, circuit breakers, call limits and acceptance thresholds | Unattended demo |
| Memory/log/audio retention and whether to record calls | Storing conversation data |
| Speech-provider failure handling | Claiming end-to-end resilience |
| Total hosted POC cost within budget, or revised operating schedule | Paid deployment |

Do not stop all work because this table is nonempty. Build independent parts, isolate uncertain integrations, and ask focused questions when a decision actually blocks the next step. Do not silently claim these are finalized.

## 18. Old repository evidence and pitfalls

Reference repository: https://github.com/sandeeptiet/sahayak-voice-bot
Reviewed business snapshot: 6ef9ceff9379f1d5008f5f7f09455cc1e5d70338.
Reviewed LLM gateway blob: 580bcc2d8f7aaec6139140201df40d34d87c0904.

Relevant paths:
- README.md: goals, lifecycle, architecture and superseded remote-transfer approach.
- services/ticket-portal/src/ticket_portal/{models.py,schemas.py,priority.py,routers/tickets.py}.
- services/voice-agent-core/src/voice_agent_core/{agent.py,tools.py,db.py,trigger_listener.py,llm_gateway.py}.
- services/supervisor-dashboard/src/supervisor_dashboard/{main.py,db.py} and static/index.html.
- RAG-docs/: the 10 reusable PDF candidates.

Do not preserve old implementation bugs:
- No real authentication/profile lookup in the old portal.
- assigned_engineer_id exists but no implemented self-assignment action was found.
- The dial counter increments answered calls too and survives rescheduling; it can incorrectly exhaust a later callback.
- Supervisor reschedule route has a stale comment claiming status returns to new; actual db.py and the agreed lifecycle keep transferred_to_human.
- The AI tool permits failed even though the agreed lifecycle does not define in_progress → failed.
- Cancellation checks only new status, leaving a possible race with a ringing call.
- Status updater does not independently enforce all transitions/confirmation evidence.
- Brief resolution_summary is not proof of a detailed step-by-step handoff transcript.
- Audit history alone does not prevent concurrent duplicate work.
- README-referenced architecture/Project Bible DOCX files were absent from the inspected tree and have not been reviewed.

Old technologies (Deepgram, ElevenLabs, Groq/OpenRouter defaults, Twilio, Qdrant, handwritten direct SQL and transient pg_notify dispatch) are reference implementation details, not requirements for the new stack. An independent LLM fallback may use another provider if selected later; that does not restore the entire old stack.

## 19. Official references for implementation-time verification

These are starting references, not a guarantee that account/region/version compatibility has already been tested.

- Sarvam chat: https://docs.sarvam.ai/api-reference/chat/chat-completions-v1
- LiveKit Sarvam STT: https://docs.livekit.io/agents/models/stt/sarvam/
- LiveKit Sarvam TTS: https://docs.livekit.io/agents/models/tts/sarvam/
- LiveKit agent deployment: https://docs.livekit.io/deploy/agents/
- Exotel/LiveKit integration: https://support.exotel.com/support/solutions/articles/3000134145-livekit-and-exotel-sip-trunking-integration-guide
- AgentCore LangGraph memory: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-integrate-lang.html
- AgentCore policy: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-core-concepts.html
- AgentCore regions: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html
- Independent Guardrails API: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html
- KB ingestion: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html
- KB retrieval: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve.html
- S3 Vectors/KB: https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-bedrock-kb.html
- SQLAlchemy PostgreSQL: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- Alembic: https://alembic.sqlalchemy.org/en/latest/
- Twelve-Factor backing services: https://12factor.net/backing-services
- RDS stop behavior: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html

## 20. Starting prompt for a fresh coding session

> Read technical-requirements.md completely as the Sahayak implementation handoff. Inspect the reference repository for business evidence, but build with the selected new stack. Preserve the exact ticket lifecycle, PostgreSQL portability, authorized tool execution and configurable LLM fallback. Distinguish selected decisions from proposed/open choices. First inspect the local repository, summarize the next implementable slice and identify only its blocking decisions. Then proceed with the work I authorize, maintaining tests, a decision log and implementation status. Do not assume access to my earlier ChatGPT conversations or claim an integration works without validating it.

Using the same underlying model in another app does not itself transfer this conversation, files, credentials or tool access. Place this file in the new repository and explicitly ask the agent to read it. A configured sharing/import integration may provide additional context, but none is established by this handoff. The label “GPT-6x” and its availability inside Antigravity have not been verified here; model selection in the coding tool is separate from Sarvam models used by the Sahayak application.

## Authoritative portal clarification — 13 October 2026

The user's latest correction supersedes the temporary shared employee listing:
employees create tickets and view only their own tickets. Engineers view all tickets
and self-assign unassigned tickets escalated to humans. Only the assigned engineer
records completed/failed outcomes with a note. One portal presents these capabilities
according to server-verified roles. Retain a dedicated limited backend database
login; do not use the administrator credential for everyday portal requests.
