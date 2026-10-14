# Sahayak Portal — prerequisite setup guide

Prepared 11 October 2026. Scope: manual infrastructure/database preparation only.
No portal implementation, AWS provisioning or paid API/call execution is part of this package.
All names and sizing below are proposed POC settings. Console labels can move;
match the setting, not just the menu position.

## 1. Component names and boundaries

| Component | Suggested name | Responsibility |
|---|---|---|
| Employee and technical-team portal | **Sahayak Portal** | Cognito login, ticket intake, employee timeline, engineer workbench, assignments, outcomes, audit and durable call requests |
| Calling and media | **Sahayak Voice Connect** | LiveKit rooms/media, Exotel SIP/PSTN, dial control, answered/disconnected events, ordinary human follow-up calls |
| Intelligent assistance | **Sahayak Agent** | Sarvam Saaras STT, Sarvam chat model, LangGraph workflow, approved knowledge/tools, Sarvam Bulbul TTS, safety and memory |

STT/TTS adapters may physically run inside the LiveKit worker for latency, while
the agent workflow stays in AgentCore. These are responsibility boundaries, not
a requirement to deploy exactly three processes. The provider is **Sarvam AI**.

Your latest requirement allows engineers to assign escalated work to themselves
or another active engineer. This expands the earlier self-assignment-only plan.
Every assignment/reassignment needs an audit entry, authorization and concurrency protection.
The portal admin is an application role, not an AWS account administrator.

The current handoff specifies asynchronous human follow-up, not a live transfer
of an active AI call to an engineer. This guide preserves that. If by “transfer”
you intend a live warm transfer, that needs a separate calling design later.

## 2. What to prepare now

Required now:
1. AWS account access with permission to manage Cognito, RDS/VPC and SQS.
2. One AWS Region and a budget estimate.
3. Cognito user pool, public web app client, managed login domain and test users.
4. A private RDS PostgreSQL database and a working secure connection from your computer.
5. The supplied preparation schema and synthetic verification SQL.
6. A standard SQS call-request queue and its dead-letter queue, with no consumer enabled yet.
7. A completed non-secret configuration worksheet.

Build later: React/FastAPI, Cognito token verification, scoped database access,
Alembic migrations, outbox publisher, scheduling, call controller and operational
alarms. Creating a queue and trigger alone does not create a working dispatcher.

Not prerequisites for building the portal: Exotel credentials, LiveKit project,
Sarvam API keys, AgentCore deployment or knowledge ingestion. These are required
before live agent/phone integration, not for login and ticket screens.

## 3. Gather your input values

Use one environment, `dev`, initially. Proposed naming:

| Item | Proposed value / input needed |
|---|---|
| Project tag | `Project=Sahayak`, `Environment=dev` |
| Region | `ap-south-1` (Mumbai), proposed; confirm before creation |
| Cognito pool | `sahayak-dev-users` |
| Web app client | `sahayak-dev-web` |
| Cognito domain prefix | `sahayak-dev-<unique-suffix>`; use your own unique suffix |
| Local portal origin | `http://localhost:5173` |
| Login callback | `http://localhost:5173/auth/callback` |
| Logout return | `http://localhost:5173/` |
| Future local API origin | `http://localhost:8000` |
| RDS identifier | `sahayak-dev-postgres` |
| Initial database | `sahayak` |
| DB setup administrator | `sahayak_setup_admin` |
| Application schema | `sahayak` |
| Main SQS queue | `sahayak-dev-call-requests` |
| Dead-letter queue | `sahayak-dev-call-requests-dlq` |

Mumbai is a reasonable proposed starting point for Indian users. AWS currently
lists Runtime, Memory, Gateway and Policy there. That does not independently
verify every later model, Knowledge Base, S3 Vectors or account entitlement.
Check the [AgentCore region matrix](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)
before committing the overall deployment location.

Prepare a private roster: employee code, name, email you control, department,
role(s), authorized test phone and how you verified the phone. Start with three
employees, one engineer and one portal administrator. You can give the administrator
the engineer role as well to test assignment between two eligible engineers.
Do not use arbitrary real phone numbers as examples.

## 4. Create Cognito authentication

You do not create a separate “Cognito account.” Use your existing AWS account and
create a **Cognito User Pool** inside it. An Identity Pool is unnecessary for this
design: the browser calls our API; it does not directly access RDS, SQS or AWS APIs.

### 4.1 User pool and first application

Open AWS Console → select Region → Amazon Cognito → User pools → Create user pool
(some console versions start with “Create application”). Use:

| Setting | Enter/select |
|---|---|
| Application type | Single-page application (SPA) |
| Application name | `sahayak-dev-web` |
| User pool name | `sahayak-dev-users` |
| Feature plan | Essentials, as selected in the handoff |
| Sign-in identifier | Email |
| Self-registration | Disabled; only administrator-created POC users |
| Required profile attribute | Email; keep department/employee code/trusted phone in the application database |
| Sign-in method | Password |
| Password policy | Proposed: minimum 12 characters, uppercase/lowercase/number/symbol |
| MFA | Proposed: required authenticator-app/TOTP; avoid needing SMS setup for portal prerequisites |
| Recovery | Verified email |
| Email delivery | Cognito default email sender for the small POC, if available within its sending limits; SES is a later delivery configuration |
| Return URL | `http://localhost:5173/auth/callback` |

Configure the pool first if the wizard does not expose every setting. Do not add
custom Cognito attributes for roles: use groups. Do not require a Cognito phone
attribute when trusted phone management belongs in the application profile.
Review required attributes before creation because some schema/sign-in choices
are difficult or impossible to change afterward. See [Cognito attributes](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-attributes.html).

TOTP enrollment occurs through managed login; keep each user's authenticator
secret private. See [AWS TOTP setup](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa-totp.html).

### 4.2 Domain and app-client settings

In the pool, open Domain and configure a Cognito prefix domain with your unique
prefix. Choose **Managed login** branding. No custom domain/certificate is needed
for this local POC. Copy the full domain AWS displays; do not reconstruct it by guessing.

Open App clients → `sahayak-dev-web` → login/managed-login settings:

| Setting | Value |
|---|---|
| Client kind | Public client; **no client secret** |
| Identity provider | Cognito user pool |
| OAuth grant | Authorization code only |
| PKCE | The portal will send S256 code challenge/verifier; this is application behavior, not always a console toggle |
| Allowed callback | `http://localhost:5173/auth/callback` |
| Allowed sign-out URL | `http://localhost:5173/` |
| OpenID scopes | `openid`, `email`, `profile` |
| Access token validity | Proposed: 15 minutes |
| ID token validity | Proposed: 15 minutes |
| Refresh token validity | Proposed: 1 day |
| Token revocation | Enabled |

Leave implicit and client-credentials grants off for this browser application.
Do not put a client secret in React. If you accidentally created a confidential
client, create a new public SPA client. See [app-client settings](https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-client-apps.html).

Use exact URLs, including port/path/trailing slash. Add deployed HTTPS URLs later;
do not register a speculative production URL now. Managed login configuration
and its “View login pages” test are documented [here](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managed-login.html).

### 4.3 Groups and five users

User pool → Groups → Create group. Create exactly:
- `employee`
- `engineer`
- `portal_admin`

No IAM role ARN or group precedence is needed for our application-role design.
Group membership appears in tokens, but backend code must enforce its meaning.
[AWS group documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-user-groups.html)
describes creation and claims.

User pool → Users → Create user, repeat for your roster:
1. Enter a real email you control and a temporary password/invitation option.
2. Use email invitation when configured. Complete password change on first login.
3. Mark email verified only if the address has actually been verified through
   your controlled onboarding procedure; do not assert verification for strangers.
4. Add the user to the appropriate group(s).
5. Save the stable Cognito **sub** from user attributes. The database maps by
   issuer + sub, never by an employee-typed ID or email alone.
6. Enroll TOTP and test login using “View login pages.”

An administrator is not automatically an engineer; assign both groups if needed.
The employee role shows own tickets. Engineers will see support queues and agent
outcomes, assign escalated tickets and record work. Portal administrators manage
directory/role-related functions; sensitive user administration stays in AWS for
the first POC unless explicitly implemented. See [admin-created users](https://docs.aws.amazon.com/cognito/latest/developerguide/how-to-create-user-accounts.html).

Because the portal is not built, the browser may reach localhost and report
connection refused after successful authentication. That proves only the login
redirect, not a completed PKCE exchange or API authorization. We will verify those
after implementation; do not paste authorization codes or tokens into chat.

### 4.4 Values to record

Save Region, pool ID, app-client ID, full login domain and:

```text
Issuer: https://cognito-idp.<region>.amazonaws.com/<user-pool-id>
JWKS:   https://cognito-idp.<region>.amazonaws.com/<user-pool-id>/.well-known/jwks.json
```

The API design will accept access tokens and check signature/JWKS, issuer,
expiry, `token_use=access`, matching `client_id`, and role/scope. ID-token `aud`
rules are different. If resource binding is later enabled, validate its audience
too. See [access token claims](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html).
Client ID is configuration, not a password. AWS keys/passwords/token contents are
not required in the worksheet.

## 5. Prepare RDS networking before database creation

Recommended path: **private RDS**, accessed from your laptop through an AWS
Systems Manager (SSM) port-forwarding host. You do not need a local PostgreSQL server.
You do need a client such as `psql` or a PostgreSQL-capable GUI.

If you already have a suitable VPC and SSM-managed instance, reuse them after
checking their access rules. Otherwise the small POC network is:

| Resource | Proposed setting |
|---|---|
| VPC | `sahayak-dev-vpc`, IPv4 `10.20.0.0/16`; DNS support/hostnames enabled |
| Public management subnet | `10.20.0.0/24`, AZ A |
| Private DB subnet A | `10.20.10.0/24`, AZ A |
| Private DB subnet B | `10.20.11.0/24`, different AZ B |
| Internet gateway | Attached to VPC; public subnet route `0.0.0.0/0` to it |
| DB subnet route table | Local VPC route only; no internet route needed for RDS |
| DB subnet group | `sahayak-dev-db-subnets`, both private DB subnets |
| Management security group | `sahayak-dev-management-sg`, no inbound rules |
| DB security group | `sahayak-dev-db-sg`, TCP 5432 inbound only from management SG and later API SG |

RDS subnet groups require coverage across at least two AZs even for this proposed
Single-AZ instance. See [RDS VPC setup](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html).

For the management host: launch a small supported Amazon Linux EC2 instance in
the public subnet with a public IPv4 address, no inbound SSH rule and an instance
role with `AmazonSSMManagedInstanceCore`. Allow outbound HTTPS to Systems Manager
services (and outbound database traffic to the DB SG). Ensure SSM Agent is installed,
running and online. The public-IP route is a POC alternative to paying for NAT or
multiple private interface endpoints; it does not make the private RDS public.
Public IPv4 and EC2 have charges; stop the host when unused. Budget this before launch.

If company policy requires private management hosts, use approved VPN or SSM VPC
endpoints instead and price them. Do not open RDS to `0.0.0.0/0` or `::/0`.

Install AWS CLI v2 and Session Manager plugin on your laptop, then authenticate
with your AWS profile/SSO. The human operator needs scoped SSM start/terminate
session permissions. [SSM prerequisites](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-prerequisites.html)
cover client, agent and IAM setup. The remote forwarding document requires a
recent supported SSM Agent (AWS documents at least 3.1.1374.0).

## 6. Create the RDS instance

RDS → Databases → Create database → Standard create:

| Field | Proposed POC value |
|---|---|
| Engine | PostgreSQL, standard RDS (not Aurora) |
| Version | PostgreSQL 17, latest supported 17.x minor offered in your chosen Region; record exact version |
| Template | Dev/Test; review all defaults |
| Deployment | Single-AZ DB instance |
| Identifier | `sahayak-dev-postgres` |
| Master username | `sahayak_setup_admin` |
| Credentials | RDS-managed master secret in Secrets Manager, or a generated password in your password manager |
| Instance | `db.t4g.micro` if offered for your engine/Region; review console estimate |
| Storage | General Purpose SSD gp3, 20 GiB if offered; no provisioned IOPS add-on |
| Storage autoscaling | Off for a bounded test footprint; monitor free storage and expand deliberately |
| VPC/subnet group | Prepared VPC and private DB subnet group |
| Public access | **No** |
| Security group | `sahayak-dev-db-sg` |
| Port | 5432 |
| Initial database name, under Additional configuration | `sahayak` |
| Storage encryption | Enabled, default AWS-managed key acceptable for POC |
| Automated backups | Proposed 1 day for disposable POC; raise for meaningful retained data |
| Deletion protection | Enabled; turn off explicitly only for intentional teardown |
| Monitoring | Review defaults; avoid paid advanced monitoring tiers unless budgeted |
| Maintenance | Auto minor version upgrade enabled; record maintenance window |
| RDS Proxy / Multi-AZ cluster / read replicas | Not required for initial preparation |

This is a proposed starting size, not a performance or cost guarantee. Use the
console's current estimate, including storage, backups, Secrets Manager and
management connectivity. An older AWS account must not assume free-tier eligibility.
The INR 2,000/month planning ceiling has not been validated. Do not click Create
if the estimate exceeds your intended operating budget without deciding how to
reduce scope or run time. [AWS creation guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html).

Create a custom PostgreSQL 17 parameter group if needed and explicitly ensure
`rds.force_ssl=1`. Apply it and reboot only if AWS shows pending-reboot. Download
the RDS CA bundle linked in [AWS SSL documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.SSL.html).
Use `verify-full`, not only encrypted-but-unverified TLS. [PostgreSQL SSL on RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html).

Record endpoint (hostname only), port, database, exact PostgreSQL version, VPC,
subnet group, SG IDs and secret ARN/name. Keep the master secret out of source code.
The future API uses a separate least-privilege database login; do not configure it
with the master username. We will establish runtime grants with domain migrations.

## 7. Connect securely from your computer

First verify the management EC2 instance is Online in Systems Manager and can
resolve/reach the RDS endpoint through its SG. In one terminal, replace placeholders:

```sh
aws ssm start-session \
  --region ap-south-1 \
  --target <management-ec2-instance-id> \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters '{"host":["<your-rds-endpoint>"],"portNumber":["5432"],"localPortNumber":["15432"]}'
```

Keep the tunnel running. In another terminal use a local PostgreSQL client:

```sh
psql "host=<your-rds-endpoint> hostaddr=127.0.0.1 port=15432 dbname=sahayak user=sahayak_setup_admin sslmode=verify-full sslrootcert=/absolute/path/to/global-bundle.pem" -W
```

`hostaddr` directs the connection through the tunnel, while `host` retains the
real RDS hostname for certificate verification. Enter the password at the prompt,
not in the command. A GUI must likewise support verifying the real server hostname
through the tunnel; do not turn off certificate verification to fix a mismatch.
See [SSM remote-host port forwarding](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html).

Run:

```sql
SELECT current_database(), current_user, version();
SELECT ssl, version, cipher FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SHOW rds.force_ssl;
```

Expected: database `sahayak`, SSL true, forced SSL enabled. Do not mistake an RDS
status of Available for successful network/authentication/TLS validation.

## 8. Create tables and verify the trigger

The accompanying SQL is a **preparation baseline**, not a production lifecycle
service. It creates 12 tables, insert rules and a transactional creation trigger.
It intentionally blocks ticket UPDATE/DELETE until we implement authenticated,
audited lifecycle actions. This prevents setup SQL from pretending to enforce
employee confirmation, engineer authorization or call retry rules that need application logic.

| Table | What it stores |
|---|---|
| `profiles` | Cognito issuer/sub mapping, employee identity and trusted contact |
| `profile_roles` | Admin-maintained directory roles, checked against verified login scope |
| `tickets` | Category, issue, priority, status, owner, assignment, callback, version and outcome |
| `ticket_events` | Append-only creation/status/assignment/schedule audit timeline |
| `ticket_notes` | Employee-visible updates and internal engineer notes |
| `call_attempts` | Individual AI/human calls, provider IDs and separate operational outcomes |
| `conversation_turns` | Redacted text and received/generated/spoken/interrupted state |
| `resolution_evidence` | Reference to the employee turn supporting a confirmed fix |
| `troubleshooting_steps` | Instructions, outcomes and source/version/page evidence |
| `callback_requests` | Due times, AI/human responsibility and schedule generation |
| `outbox_events` | Durable requests waiting to be dispatched |
| `action_receipts` | Idempotency and uncertain-action reconciliation |

Call counts are derived from call-attempt rows; unanswered classification remains
open rather than equating every call with an unanswered retry. Usage/cost ledger,
recovery records, retention jobs and detailed integration fields come in later migrations.

Run the files with a PostgreSQL client using stop-on-error. In an existing `psql`
session (replace the path with where you saved this package):

```text
\set ON_ERROR_STOP on
\i /absolute/path/to/01_schema.sql
\i /absolute/path/to/02_sample_and_verify.sql
```

Alternatively, a GUI can execute each whole SQL file in order. Script 1 is a
single transaction and is intentionally not rerunnable against an existing
schema. Do not drop an existing schema to overcome errors; inspect first.
Script 2 inserts synthetic profiles/tickets/notes, checks the trigger and rolls
everything back. All test phones are NULL and events are flagged `is_test`.

Expected verification output:
- VPN ticket priority `medium`; account-access urgency ticket priority `critical`.
- Two creation audit rows and two outbox rows inside the test transaction.
- Future callback outbox due time equals the ticket's callback time.
- A passing notice, followed by rollback and zero synthetic tickets remaining.
- Ticket-number gaps after rollback are normal PostgreSQL sequence behavior.

No PostgreSQL server or RDS connection was available when this package was
authored. SQL has been reviewed, but **has not been executed against PostgreSQL**.
The included verification must pass on your empty dev database before accepting
the schema. During portal development we will adopt this baseline into Alembic;
we must not blindly rerun a schema-creation migration over the same tables.

### 8.1 Register actual Cognito profiles

After Cognito users exist, run an administrator-only insert like this, replacing
every example with your real verified roster values. Do not use the synthetic
`urn:sahayak:test` identities for real accounts.

```sql
BEGIN;
INSERT INTO sahayak.profiles
  (identity_issuer, identity_subject, employee_code, display_name, email, department)
VALUES
  ('https://cognito-idp.ap-south-1.amazonaws.com/REPLACE_POOL_ID',
   'REPLACE_COGNITO_SUB', 'EMP001', 'REPLACE_NAME', 'REPLACE_EMAIL', 'Finance');

INSERT INTO sahayak.profile_roles(profile_id, role)
SELECT id, 'employee' FROM sahayak.profiles
WHERE identity_issuer='https://cognito-idp.ap-south-1.amazonaws.com/REPLACE_POOL_ID'
  AND identity_subject='REPLACE_COGNITO_SUB';
COMMIT;
```

Repeat for engineers/admins with their corresponding role, not employee by
default. If multiple roles are required, add separate `profile_roles` rows and
the matching Cognito groups. Do not store passwords or Cognito tokens in RDS.

Initially leave phone NULL. Once you independently confirm an authorized test
number with its owner, update that profile with E.164 `+91` plus the ten-digit
Indian mobile number and record `phone_trusted_at`, `phone_trusted_by` and
`phone_trust_method` in the same transaction. Changing the number later must
clear and re-establish its trust. Do not set trust merely because an input looks
like a phone number or the user typed it in a ticket.

Administrator-only example, after real verification (replace all placeholders):

```sql
BEGIN;
UPDATE sahayak.profiles
SET phone_e164 = 'REPLACE_WITH_AUTHORIZED_E164_NUMBER',
    phone_trusted_at = now(),
    phone_trusted_by = 'REPLACE_ONBOARDING_ADMIN_ID',
    phone_trust_method = 'Owner confirmed number during controlled POC onboarding'
WHERE identity_issuer = 'https://cognito-idp.ap-south-1.amazonaws.com/REPLACE_POOL_ID'
  AND identity_subject = 'REPLACE_COGNITO_SUB';
-- Confirm exactly one row was updated before committing.
COMMIT;
```

Record profile edits in the controlled onboarding record during setup. The portal
build must add audited profile-management operations before allowing such edits
through application screens. Phone verification alone does not authorize a live
test call; the later test must use your explicitly approved destination list.

You may inspect profiles with SELECT. Do not create non-test tickets until the
dispatcher and call safeguards are verified; older queued events could otherwise
be delivered when a worker is enabled later. Use the rollback sample for setup.

### 8.2 Conversation history versus employee-visible history

Employees see their own status, safe troubleshooting steps and employee-visible
notes. Engineers see assigned/escalated work and relevant agent evidence, with
broader technical-team read scope defined in the API. Internal notes, tokens,
hidden model reasoning and other employees' details must not appear in an employee response.

The schema supports redacted transcripts, not audio recording. Decide retention
and visibility before storing real conversations. RDS business history is not a
replacement for the later AgentCore workflow checkpoints/memory.

## 9. Create the reliable call-request queue

The trigger works like this:

```text
Authenticated ticket submission (future API)
  → one PostgreSQL transaction
      → tickets row
      → ticket_events creation audit
      → outbox_events call request with due time
  → COMMIT
  → outbox dispatcher (built later)
  → SQS call-request queue
  → Voice Connect controller (built later)
  → verify current ticket, phone trust, due time and dial claim
  → LiveKit SIP → Exotel → employee phone
```

The SQL trigger never invokes an AWS SDK or an HTTP call. If any insert fails,
the entire transaction rolls back. If the dispatcher is down, committed requests
remain in the database. The [AWS transactional outbox pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
addresses this database/message dual-write problem.

### 9.1 SQS console values

SQS → Create queue. Create the DLQ first, then the main queue, in the chosen Region.

| Setting | Main queue | Dead-letter queue |
|---|---|---|
| Name | `sahayak-dev-call-requests` | `sahayak-dev-call-requests-dlq` |
| Type | Standard | Standard |
| Server-side encryption | SQS-managed key (SSE-SQS) | Same |
| Retention | 4 days | 14 days |
| Visibility timeout | Proposed 120 seconds; tune for controller claim time later | Default acceptable initially |
| Receive wait time | 20 seconds | 20 seconds |
| Delivery delay | 0 seconds | 0 seconds |
| Access policy | Account-private; no public access | Account-private |
| Redrive | Select the DLQ; proposed maxReceiveCount 5 | Allow redrive from this main queue only |

These are initial settings, not evidence that retry handling has been implemented.
**Five message receives is not five phone calls.** It is a queue delivery-retry
limit; the business no-answer limit remains three qualifying unanswered attempts
under a campaign policy still to be finalized.
[Queue parameters](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-configure-queue-parameters.html)
and [dead-letter configuration](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html).

Save both queue URLs and ARNs. Do not attach a Lambda event-source mapping or
start a call consumer yet. SQS does not know what a ticket or employee is.

### 9.2 Scheduling and dispatcher behavior to build later

For the initial small POC, proposed dispatcher behavior is to poll due outbox
rows every 10–30 seconds. This interval is an unbenchmarked development default.
Rows with future `available_at` remain in PostgreSQL until due. EventBridge
Scheduler is an optional later wake-up mechanism, not required for this setup.
SQS delay is limited to 15 minutes, so it cannot alone schedule tomorrow's callback.
[AWS delay-queue limits](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-delay-queues.html).

Required implementation contracts:
1. Claim due, non-test rows using a bounded lease and row locking; recover expired leases.
2. Publish an event ID, ticket ID and schedule generation, not raw conversation/phone data.
3. Mark published only after successful SQS acknowledgment. A crash can still produce a duplicate.
4. Consumer persists action receipts/dial claims and checks stale generations, status,
   due time, test flag, trusted contact, kill switch and allowed test numbers.
5. Reconcile uncertain provider outcomes instead of redialing after an ambiguous timeout.
6. Coordinate cancellation/rescheduling with the dial claim atomically.
7. Human callbacks stay in human support; never turn them into AI call requests.
8. Replacement/retry events and their audit records are written transactionally by
   the future lifecycle service. The supplied trigger covers initial creation only.

LISTEN/NOTIFY alone is not durable dispatch. SQS Standard delivery is not an
exactly-once guarantee; changing to FIFO would not remove external-call reconciliation.

### 9.3 IAM and secrets when the workers are built

Prepare names now, create runtime roles once hosting is selected:
- Portal API: only its required profile/admin operations, runtime DB secret and logs.
- Outbox dispatcher: its DB credentials, `sqs:SendMessage` on the main queue, logs.
- Call consumer: `sqs:ReceiveMessage`, `sqs:DeleteMessage`,
  `sqs:ChangeMessageVisibility`, `sqs:GetQueueAttributes` on that queue and only
  its required DB/provider-secret access.
- Deployment operator: separate from runtime roles; schema migrations use separate privileges.

No AWS keys, database credentials or SQS permissions belong in browser code.
No application user receives direct database access. Restricted table/function
grants, ownership validation and authenticated transaction actor context will be
implemented before exposing the API. The SQL `SET LOCAL sahayak.actor_id` value is
an audit input from a trusted backend, not proof of authentication by itself.

## 10. Verification before portal development

There are two gates. Prerequisites can be ready before the application exists;
end-to-end behavior cannot be certified until the application is built.

**Gate A — verify now:**
- Correct Region/resource names and reviewed budget.
- Cognito pool, public client without secret, managed login/domain, exact URLs,
  five users, TOTP and group memberships.
- Saved issuer/sub mappings and trustworthy roster.
- RDS private, restricted SG, correct DB/version, encrypted storage/backups.
- Successful client connection with full TLS verification.
- Schema creation and rollback SQL test pass; no accidental live ticket events.
- Main SQS and DLQ private, encrypted, configured; no active consumers.
- No credentials stored in repository or shared in chat.

**Gate B — implement and verify later:**
- PKCE token exchange, JWT validation, cross-user denial, revoked/disabled users.
- Trusted phone lookup, intake idempotency and exact lifecycle with atomic audit.
- Assignment race protection; permitted assignment to other active engineers.
- Explicit employee-confirmation evidence before AI completion.
- Durable outbox publishing/recovery, duplicate handling and stale callback rejection.
- Employee/internal visibility, safe agent history and engineer outcome views.
- Runtime database permissions, API deployment/networking, monitoring and retention.
- Authorized test call only after Voice Connect and Sahayak Agent are integrated.

Fill `configuration-worksheet.md` and provide its non-secret values plus the SQL
test result. We can inspect and verify those resources read-only, report any
gaps, and wait for your instruction before starting portal implementation.

## 11. Cost and stopping the POC

Track RDS compute/storage/backups, management EC2/public IPv4, Cognito, SQS,
Secrets Manager and later API hosting/logging. Do not rely on a free-tier label.
Set a budget alert for your chosen amount, remembering it does not cap spending.

For an unused POC, stop the RDS instance if eligible and stop the management EC2
instance. RDS storage/backups continue to cost money; RDS automatically restarts
after seven days. A stopped database also makes the portal unavailable.
[RDS stop behavior](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_StopInstance.html).
Deletion and snapshot retention are separate decisions: inspect retained-data
needs before deleting anything. Do not provision a NAT gateway or always-on
extras merely because a wizard suggests them.
