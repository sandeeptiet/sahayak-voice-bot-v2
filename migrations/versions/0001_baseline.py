"""Adopt the manually provisioned schema, or create a clean baseline."""
from pathlib import Path
from alembic import op
from sahayak.db_scripts import execute_script
from sqlalchemy import inspect, text

revision = "0001_baseline"
down_revision = None
branch_labels = depends_on = None
SQL = Path(__file__).parents[1] / "sql" / "0001_baseline.sql"


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_schema("sahayak"):
        execute_script(bind, SQL.read_text())
        return
    required = {"profiles", "profile_roles", "tickets", "ticket_events", "ticket_notes",
                "call_attempts", "conversation_turns", "resolution_evidence",
                "troubleshooting_steps", "callback_requests", "outbox_events", "action_receipts"}
    if not required.issubset(inspector.get_table_names(schema="sahayak")):
        raise RuntimeError("Existing sahayak schema is incomplete; inspect it before migrating")
    # Verify the API's mapped columns and their PostgreSQL type families.
    from sahayak.api.models import Base
    for table in Base.metadata.sorted_tables:
        columns = {c["name"]: c for c in inspector.get_columns(table.name, schema="sahayak")}
        for column in table.columns:
            actual = columns.get(column.name)
            if actual is None or actual["type"]._type_affinity is not column.type._type_affinity:
                raise RuntimeError(f"Incompatible baseline column: {table.name}.{column.name}")
    unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints("tickets", schema="sahayak")}
    if ("employee_id", "request_key") not in unique:
        raise RuntimeError("Ticket idempotency constraint is missing")
    fk = inspector.get_foreign_keys("tickets", schema="sahayak")
    if not any(f["constrained_columns"] == ["assigned_engineer_id"] and f["referred_table"] == "profiles" for f in fk):
        raise RuntimeError("Ticket assignment foreign key is missing")
    triggers = set(bind.execute(text("""
        SELECT t.tgname FROM pg_trigger t
        JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='sahayak' AND NOT t.tgisinternal AND t.tgenabled='O'
    """)).scalars())
    if not {"ticket_initial_rules", "ticket_created_outbox", "tickets_preparation_only", "audit_append_only"}.issubset(triggers):
        raise RuntimeError("Expected baseline safeguards are missing; inspect before migrating")


def downgrade():
    raise RuntimeError("Baseline downgrade would remove user data; restore from a reviewed backup instead")
