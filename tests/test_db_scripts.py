"""Regression for psycopg parsing literal PostgreSQL % tokens as parameters."""
from unittest.mock import MagicMock
from pathlib import Path
from sahayak.db_scripts import execute_script

def test_repository_ddl_omits_parameter_mapping_and_preserves_transaction():
    connection=MagicMock()
    cursor=connection.connection.driver_connection.cursor.return_value.__enter__.return_value
    script=Path('migrations/sql/0003_dispatch.sql').read_text()
    assert '%ROWTYPE' in script
    execute_script(connection,script)
    cursor.execute.assert_called_once_with(script)
    connection.commit.assert_not_called()
    connection.connection.driver_connection.commit.assert_not_called()

def test_percent_literals_are_not_rewritten():
    connection=MagicMock()
    script="SELECT 'urgent issue' LIKE '%urgent%'"
    execute_script(connection,script)
    connection.connection.driver_connection.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(script)
