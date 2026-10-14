# Sahayak voice agent v2

Internal employee IT helpdesk voice-agent POC. The authoritative implementation
handoff is [technical-requirements.md](technical-requirements.md).

## Local verification

Using the existing environment, run the deterministic foundation tests without
network calls or credentials:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

`sahayak/intake.py` implements category-based priority and future callback-time
validation. The authenticated backend now uses these rules for ticket creation.

`main.py` is the original experimental Sarvam/LangGraph starter. Running it sends
a model request and requires SARVAM_API_KEY. It is not the production workflow.

See [implementation status](docs/implementation-status.md) for verified scope and
next work, and [decision log](docs/decisions.md) for provisional choices.
Keep credentials out of source control and preserve RAG-docs originals.

## Employee and engineer portal

The React portal lives in [portal/](portal/README.md). Run `npm ci` and
`npm run dev` from that directory, then open http://localhost:5173.
Cognito login and role-scoped ticket screens are implemented. Employees create
and view their own tickets; engineers view all tickets and claim human escalations.
See [backend setup](docs/portal-backend.md) to configure the limited RDS login and
start the API. User verified RDS setup, employee creation and engineer listing.
See [background worker](docs/background-worker.md) for the new calls-disabled
queue workflow; its RDS migration and live processing acceptance are pending.
