"""Add calls-disabled worker receipts and a minimal locked context reader."""
from pathlib import Path
from alembic import op
from sahayak.db_scripts import execute_script
revision = "0003_dispatch"
down_revision = "0002_portal"
branch_labels = depends_on = None

def upgrade():
    execute_script(op.get_bind(), (Path(__file__).parents[1] / "sql/0003_dispatch.sql").read_text())

def downgrade():
    raise RuntimeError("Preserve dispatch receipts; review a forward recovery migration")
