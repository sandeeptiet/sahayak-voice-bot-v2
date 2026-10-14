"""Interactive one-time RDS setup. Passwords never enter command arguments/logs."""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import tempfile
from alembic import command
from sahayak.db_scripts import execute_script
from alembic.config import Config
from psycopg import sql
from sqlalchemy import text
from .api.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description="Migrate the Sahayak database and configure its limited API login")
    parser.add_argument("--apply",action="store_true",help="Apply reviewed migrations and grants to the chosen database")
    args=parser.parse_args()
    if not args.apply:
        print("Review migrations/sql and docs/portal-backend.md, then run with --apply.")
        return
    print("This preserves your existing profiles and tickets, enables audited engineer updates,\n"
          "and creates the limited sahayak_portal database login. No calls are placed.")
    host=input("RDS endpoint (hostname only): ").strip()
    ca=Path(input("Full path to global-bundle.pem: ").strip().strip("\"'")).expanduser()
    username=input("Setup administrator [sahayak_admin]: ").strip() or "sahayak_admin"
    password=getpass("Administrator database password (hidden): ")
    if not host or any(c in host for c in "/:@ ") or not ca.is_file() or not password:
        raise SystemExit("Check the endpoint, certificate path and password; nothing was changed.")
    settings=Settings(_env_file=None,db_host=host,db_user=username,db_password=password,db_ca_file=str(ca))
    config_path=ROOT/".env.api"
    existing=Settings(_env_file=config_path) if config_path.exists() else None
    if existing and (existing.db_host!=host or existing.db_user!="sahayak_portal"):
        raise SystemExit("Existing .env.api points to a different setup. Review it before continuing.")
    runtime_password=existing.db_password.get_secret_value() if existing else secrets.token_urlsafe(32)
    if not runtime_password: runtime_password=secrets.token_urlsafe(32)
    engine=settings.engine()
    try:
        with engine.begin() as connection:
            if connection.scalar(text("SELECT current_database()"))!="sahayak":
                raise RuntimeError("Wrong database")
            role_exists=connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sahayak_portal')"))
            if role_exists and existing is None:
                raise RuntimeError("Runtime role already exists but its private local configuration is missing; review before rotating its password")
            cfg=Config(str(ROOT/"alembic.ini")); cfg.attributes["connection"]=connection
            command.upgrade(cfg,"head")
            execute_script(connection, (ROOT/"migrations/sql/runtime_grants.sql").read_text())
            with connection.connection.driver_connection.cursor() as cursor:
                cursor.execute(sql.SQL("ALTER ROLE sahayak_portal PASSWORD {}").format(sql.Literal(runtime_password)))
        values={"SAHAYAK_DB_HOST":host,"SAHAYAK_DB_PORT":"5432","SAHAYAK_DB_NAME":"sahayak",
                "SAHAYAK_DB_USER":"sahayak_portal","SAHAYAK_DB_PASSWORD":runtime_password,
                "SAHAYAK_DB_CA_FILE":str(ca),"SAHAYAK_COGNITO_POOL_ID":settings.cognito_pool_id,
                "SAHAYAK_COGNITO_CLIENT_ID":settings.cognito_client_id,
                "SAHAYAK_COGNITO_DOMAIN":settings.cognito_domain,"SAHAYAK_PORTAL_ORIGIN":settings.portal_origin}
        fd,temp=tempfile.mkstemp(prefix=".portal-config-",dir=ROOT)
        try:
            with os.fdopen(fd,"w") as stream:
                stream.write("# Private API configuration; never share or commit.\n")
                for key,value in values.items(): stream.write(f"{key}={json.dumps(value)}\n")
            os.replace(temp,config_path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
        print("Migration applied. Private .env.api saved with owner-only permissions.")
        from .verify_portal_db import verify
        with engine.connect() as connection: verify(connection)
        runtime=Settings(_env_file=config_path).engine()
        try:
            with runtime.connect() as connection:
                assert connection.scalar(text("SELECT current_user"))=="sahayak_portal"
                assert connection.scalar(text("SELECT version_num FROM public.alembic_version")) in {"0002_portal", "0003_dispatch"}
        finally: runtime.dispose()
        print("PASS: runtime login, ticket creation, audit/outbox, claim/outcome and restricted grants. Test data rolled back.")
        print("Start API: uv run uvicorn sahayak.api.main:app --host localhost --port 8000")
    except Exception:
        # Don't echo driver exceptions: connection strings/SQL may contain secrets.
        print("Setup or verification failed. No password has been printed. Check RDS access, credentials and schema.")
        print("If a 'Migration applied' message appeared, that migration is committed; test rows still roll back.")
        raise SystemExit(1) from None
    finally:
        engine.dispose()


if __name__=="__main__": main()
