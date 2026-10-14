DO $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sahayak_dispatch') THEN
   CREATE ROLE sahayak_dispatch LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='sahayak_dispatch'
   AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
   OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='sahayak_dispatch')) THEN
   RAISE EXCEPTION 'Existing worker role has unexpected privileges';
 END IF;
END $$;
GRANT CONNECT ON DATABASE sahayak TO sahayak_dispatch;
GRANT USAGE ON SCHEMA sahayak TO sahayak_dispatch;
REVOKE ALL ON ALL TABLES IN SCHEMA sahayak FROM sahayak_dispatch;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA sahayak FROM sahayak_dispatch;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA sahayak FROM sahayak_dispatch;
GRANT SELECT ON public.alembic_version TO sahayak_dispatch;
GRANT SELECT ON sahayak.outbox_events, sahayak.dispatch_preflights TO sahayak_dispatch;
GRANT UPDATE(published_at,lease_owner,lease_until,publish_attempts,last_error_code)
 ON sahayak.outbox_events TO sahayak_dispatch;
GRANT INSERT(event_id,ticket_id,schedule_generation,result,workflow_version)
 ON sahayak.dispatch_preflights TO sahayak_dispatch;
GRANT EXECUTE ON FUNCTION sahayak.dispatch_context(uuid) TO sahayak_dispatch;
