"""Enable only audited engineer self-assignment and human outcomes."""
from pathlib import Path
from alembic import op
from sahayak.db_scripts import execute_script
revision = "0002_portal"
down_revision = "0001_baseline"
branch_labels = depends_on = None


def upgrade():
    execute_script(op.get_bind(), (Path(__file__).parents[1] / "sql" / "0002_portal.sql").read_text())


def downgrade():
    raise RuntimeError("Stop the API and review a rollback migration; do not remove audit history")
