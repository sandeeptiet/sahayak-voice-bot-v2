# Calls-disabled background worker

This slice publishes due transactional outbox requests to the existing SQS standard
queue and consumes them through a deterministic LangGraph entry workflow. It records
an operational preflight receipt. It does not invoke an LLM, change ticket status,
create a call attempt, or connect to LiveKit/Exotel. `ready_calls_disabled` is NOT a
completed ticket or a successful phone call. Only a verified answered-call event may
move a new ticket to in_progress in the later telephony implementation.

## Setup

The portal setup and live employee/engineer checks have passed. The additive worker
migration has not yet been applied to RDS by the coding agent.

```sh
cd /Users/sandeepkapoor/Desktop/prep/sahayak-voice-agent-v2
uv run python -m sahayak.setup_worker --apply
```

Press Enter for the supplied queue, `default` AWS profile, and `sahayak_admin`.
Enter the administrator password privately. Endpoint and certificate path are reused
from private `.env.api`. This applies migration 0003_dispatch and creates the limited
`sahayak_dispatch` login; `.env.worker` is owner-readable only and ignored by Git.
No administrator password is saved. If setup fails, a private staged runtime
configuration is retained for recovery in case a database commit response was lost.
Do not share that file. Existing worker credentials are preserved on
rerun. Missing local credentials for an existing role stop setup rather than rotate
it unexpectedly. The portal login is not broadened. Worker cannot update tickets,
read profiles directly, edit audit, or create call attempts.

**Restart the running API after setup** so it loads compatibility with migration 0003:
stop its terminal with Ctrl-C, then run the usual command:

```sh
uv run uvicorn sahayak.api.main:app --host localhost --port 8000
```

## Bounded test run

In another terminal at the repository root:

```sh
uv run python -m sahayak.dispatch status
uv run python -m sahayak.dispatch run
uv run python -m sahayak.dispatch status
```

`run` publishes at most one due request, then receives at most one message (up to ten
seconds of long polling). A queue receive can return no message; repeat `run` if idle.
A due eligible ticket produces `ready_calls_disabled`. A repeated delivery reports
`duplicate`. Future requests remain in PostgreSQL until due. The receipt is durable,
and the portal still shows New. Do not manually escalate or mark a call answered to
make this test look like a complete agent conversation.

For continuous development processing, explicitly use `run --loop`; stop with Ctrl-C.
`publish` and `consume` run each side independently for diagnostics. No process or
cloud deployment is started automatically. Configuration only accepts preflight
mode and outbound_calls_enabled=false; there is no live-dial implementation to enable.

## Failure recovery

- Publisher claims one due non-test event with FOR UPDATE SKIP LOCKED, a unique lease
  token and 120-second lease. Queue I/O happens outside database transactions.
- Successful send is marked published afterwards. Send timeouts and post-send crashes
  may resend the SAME event ID. A lease token prevents late acknowledgments from
  overwriting a newer claim.
- Failed sends back off, capped at five minutes; eight attempts exhaust automatic
  publication. `status` exposes counts and up to twenty event IDs needing attention.
- Consumer treats the envelope as untrusted, verifies it against the database, locks
  the event and ticket, and checks state, generation, test flags, assignment, due time
  and trusted active employee contact. Queue bodies contain only IDs, generation,
  schema version and preflight mode, never phone numbers or ticket descriptions.
- A receipt is committed BEFORE deleting the SQS message with its latest receipt
  handle. Database errors do not acknowledge it. Delete failure/redelivery reads the
  receipt and does not repeat work. The database primary key is a final duplicate guard.
- Future delivery is deferred without a receipt. Invalid/forged messages are not
  acknowledged; the queue's five-receive redrive policy routes them to the DLQ.
  Five receives are not five calls. This code never counts unanswered attempts.

After fixing a publisher failure, retry only its exhausted event:

```sh
uv run python -m sahayak.dispatch retry --event-id EVENT_UUID
```

After inspecting a lost or dead-lettered published message and fixing the cause,
explicitly republish its original identity (only if no receipt exists):

```sh
uv run python -m sahayak.dispatch replay --event-id EVENT_UUID
```

The status label awaiting_receipt may simply mean normal queued work; it is not by
itself proof of a failure. Replay can duplicate an existing queue message safely.
Neither command deletes a receipt or resets a business ticket. No automatic DLQ
redrive or destructive reset is provided.

Preflight events are consumed and published_at is retained. A future live-calling
release must deliberately create/reconcile authorized new work for tickets already
preflighted. It must not reinterpret these receipts as calls or automatically dial
all existing tickets. Provider uncertainty, allowed phone numbers, dial claims,
verified answer events, Gateway/Policy, AgentCore hosting and retry campaign policy
are future gates; this local graph is not the deployed conversational agent.

## AWS configuration and privileges

Verified default profile account: 346401055256. Main queue:
https://sqs.ap-south-1.amazonaws.com/346401055256/sahayak-dev-call-requests
Verified live read-only: SSE-SQS enabled, DLQ configured with maxReceiveCount 5;
worker SDK successfully reads attributes. No live messages were sent or received
by the coding agent during implementation.

Local boto3 uses the standard AWS credential chain and optional profile. Never put
AWS access keys in browser settings. Required queue permissions: GetQueueAttributes,
SendMessage, ReceiveMessage, DeleteMessage and ChangeMessageVisibility on this main
queue only. The combined local process needs both publisher and consumer permissions;
separate hosted roles can split them later. No queue creation or policy change is
performed. Existing laptop credentials were reused, not replaced or broadened.

## Tests

```sh
uv run pytest tests -q
npm --prefix portal run test:db
npm --prefix portal run test:dispatch-db
```

64 Python tests plus 10 subtests pass; 24 worker SQL checks and the existing 22
portal SQL checks pass. Python checks cover graph eligibility and mocked delivery failures. Embedded
PostgreSQL executes the actual Store SQL and migration for lease expiry, token
fencing, rollback, receipt retention and denied privileges. It is one connection;
true multi-session contention and live RDS worker acceptance remain to be checked.
No local PostgreSQL installation, model request, telephone call or paid deployment
is part of these tests.
