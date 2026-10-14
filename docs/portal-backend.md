# Local portal backend setup

## Access rules

Employees create tickets and see only their own tickets. Engineers see all tickets,
self-assign unassigned tickets in `transferred_to_human`, and record completed or
failed outcomes with a note only for tickets assigned to themselves. A combined
employee/engineer account has both capabilities. Admin membership alone does not
grant ticket access. API roles require both Cognito group and active database role.

The backend uses `sahayak_portal`, a restricted database login. The administrator
account is used only for setup. Database credentials never enter the browser.

## One-time setup on this laptop

Start RDS and ensure its security group permits port 5432 from your current IP.
Have the exact RDS endpoint and full path to `global-bundle.pem` ready.

```sh
cd /Users/sandeepkapoor/Desktop/prep/sahayak-voice-agent-v2
uv run python -m sahayak.setup_portal --apply
```

The script prompts locally for the endpoint, certificate path and administrator
password (hidden). Do not paste the password into chat. TLS verifies the hostname
and AWS certificate. The administrator password is never saved.

Review `migrations/sql/0002_portal.sql` and `runtime_grants.sql` for the database
changes: adoption of the existing schema, audited ticket creation, guarded engineer
updates, and restricted runtime grants. Existing profiles and tickets are retained.
Schema compatibility is checked; setup stops on incompatibility. Downgrades that
could discard data are intentionally unavailable.

Setup generates a runtime password and saves ignored `.env.api` with owner-only
permissions. Keep that file private. Do not delete it and rerun setup to rotate an
existing role; missing configuration requires deliberate recovery.

After applying the migration, setup runs rollback-only ticket/audit/outbox/claim/
outcome/grant checks and tests the runtime login. Expect a `PASS` message. If
verification fails after “Migration applied”, the migration is committed, but test
rows roll back. Share only the error message, never the private configuration.

## Start both local services

From the repository root:

```sh
uv run uvicorn sahayak.api.main:app --host localhost --port 8000
```

In a second terminal:

```sh
cd /Users/sandeepkapoor/Desktop/prep/sahayak-voice-agent-v2/portal
npm run dev
```

Open http://localhost:5173 and sign in. Public Cognito configuration already lives
in ignored `portal/.env.local`. The API defaults to http://localhost:8000; override
only with public `VITE_API_ORIGIN` when needed.

Verify each real account: employee creation and own-ticket listing; engineer all-
ticket listing. Claim/outcome controls appear only for eligible escalated tickets.
No manual escalation control is supplied. Automated calling and queue consumers
are not active yet; ticket creation records an outbox request but does not call.

## Verification and limits

```sh
uv run pytest tests -q
cd portal
npm run build
npm test
npm run test:db
```

Current checks: 34 Python tests, 20 browser tests, 22 embedded PostgreSQL checks.
Browser tests mock cloud responses. PGlite executes actual migration SQL and grants
in an ephemeral database, but cannot prove RDS connectivity or concurrent locking.
Live migration and real portal-to-RDS acceptance are still pending.

Read isolation is enforced by backend queries; the shared runtime login is not a
per-employee database account and must never be distributed to employees. Revoked
sessions are checked through Cognito userInfo on each request and fail closed on
provider outage. Expired sessions require sign-in again.

For connection errors check RDS availability, current laptop IP, endpoint, and CA
path. A schema-not-ready response requires successful setup. An access-denied
response requires an active directory profile and matching Cognito/database roles.
This local development configuration is not a production hosting deployment.
