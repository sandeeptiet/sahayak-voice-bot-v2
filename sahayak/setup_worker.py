"""Install the additive worker schema/login, with administrator input kept local."""
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
from sahayak.api.config import Settings
from sahayak.dispatch.config import WorkerSettings
from sahayak.dispatch.store import Store

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description='Set up restricted calls-disabled background worker')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if not args.apply:
        print('Review docs/background-worker.md then run with --apply. No changes made.'); return
    api=Settings(_env_file=ROOT/'.env.api')
    if not api.db_host or not Path(api.db_ca_file).is_file():
        raise SystemExit('Complete portal database configuration first.')
    path=ROOT/'.env.worker'
    existing=WorkerSettings(_env_file=path) if path.exists() else None
    if existing and (existing.db_host!=api.db_host or existing.db_user!='sahayak_dispatch'):
        raise SystemExit('Existing worker configuration is for a different database/login; review it first.')
    queue=input('Main queue URL [configured Sahayak queue]: ').strip() or 'https://sqs.ap-south-1.amazonaws.com/346401055256/sahayak-dev-call-requests'
    profile=input('AWS CLI profile [default]: ').strip() or 'default'
    user=input('Setup administrator [sahayak_admin]: ').strip() or 'sahayak_admin'
    password=getpass('Administrator database password (hidden): ')
    if not password: raise SystemExit('Password is required. Nothing changed.')
    runtime_password=existing.db_password.get_secret_value() if existing else secrets.token_urlsafe(32)
    if not runtime_password: raise SystemExit('Existing worker password is empty; review configuration.')
    values={'db_host':api.db_host,'db_port':api.db_port,'db_name':api.db_name,
        'db_user':'sahayak_dispatch','db_password':runtime_password,'db_ca_file':api.db_ca_file,
        'queue_url':queue,'aws_profile':profile,'aws_region':'ap-south-1',
        'worker_mode':'preflight','outbound_calls_enabled':False}
    worker=WorkerSettings(_env_file=None,**values)
    admin=Settings(_env_file=None,db_host=api.db_host,db_port=api.db_port,db_name=api.db_name,
        db_ca_file=api.db_ca_file,db_user=user,db_password=password)
    engine=admin.engine()
    temp=None; committed=False; stage="configuration"
    try:
        # Stage the private file before committing a role password. Preserve on a
        # post-commit rename failure so the newly generated credential is recoverable.
        fd,temp=tempfile.mkstemp(prefix='.portal-config-worker-',dir=ROOT)
        with os.fdopen(fd,'w') as stream:
            stream.write('# Private worker settings. Never share or commit.\n')
            for key,value in values.items():
                rendered=str(value).lower() if isinstance(value,bool) else str(value)
                stream.write(f'SAHAYAK_{key.upper()}={json.dumps(rendered)}\n')
        stage="database connection"
        with engine.begin() as c:
            if c.scalar(text('SELECT current_database()'))!='sahayak': raise RuntimeError('Wrong database')
            role_exists=c.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sahayak_dispatch')"))
            if role_exists and not existing: raise RuntimeError('Existing role has no local config; deliberate credential recovery required')
            cfg=Config(str(ROOT/'alembic.ini')); cfg.attributes['connection']=c
            stage='migration'
            command.upgrade(cfg,'head')
            stage='worker grants'
            execute_script(c, (ROOT/'migrations/sql/worker_grants.sql').read_text())
            with c.connection.driver_connection.cursor() as cur:
                cur.execute(sql.SQL('ALTER ROLE sahayak_dispatch PASSWORD {}').format(sql.Literal(runtime_password)))
        committed=True
        stage='private configuration save'
        os.replace(temp,path); temp=None
        stage='runtime verification'
        runtime=worker.engine()
        try:
            Store(runtime).check()
            with runtime.connect() as c:
                assert not c.scalar(text("SELECT has_table_privilege(current_user,'sahayak.tickets','UPDATE')"))
                assert not c.scalar(text("SELECT has_table_privilege(current_user,'sahayak.profiles','SELECT')"))
                assert c.scalar(text("SELECT has_function_privilege(current_user,'sahayak.dispatch_context(uuid)','EXECUTE')"))
        finally: runtime.dispose()
        print('PASS: worker migration, restricted login and grants. .env.worker saved privately.')
        print('No queue messages consumed and no phone calls. Next: uv run python -m sahayak.dispatch status')
    except Exception as error:
        original=getattr(error,'orig',error)
        code=getattr(original,'sqlstate',None)
        print(f'Worker setup failed during {stage} ({type(original).__name__}, SQLSTATE {code or "n/a"}). No secrets printed.')
        print('Migration committed; private configuration retained.' if committed else
              'Database transaction failed; verify the migration state before retrying after a connection loss.')
        if temp: print('Private recovery file retained at:',temp)
        raise SystemExit(1) from None
    finally:
        # Keep staged runtime credentials after failure: a lost commit response
        # must not destroy the only copy of an already-applied role password.
        engine.dispose()

if __name__=='__main__': main()
