-- Run as the setup administrator after migration. No password in this file.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sahayak_portal') THEN
    CREATE ROLE sahayak_portal LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='sahayak_portal'
       AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
     OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='sahayak_portal')) THEN
    RAISE EXCEPTION 'Existing runtime role has unexpected privileges; review it first';
  END IF;
END $$;
GRANT CONNECT ON DATABASE sahayak TO sahayak_portal;
GRANT USAGE ON SCHEMA sahayak TO sahayak_portal;
REVOKE ALL ON ALL TABLES IN SCHEMA sahayak FROM sahayak_portal;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA sahayak FROM sahayak_portal;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA sahayak FROM sahayak_portal;
GRANT SELECT ON sahayak.profiles, sahayak.profile_roles, sahayak.tickets, public.alembic_version TO sahayak_portal;
GRANT INSERT (employee_id,request_key,category,description,asset_tag,priority,callback_at)
  ON sahayak.tickets TO sahayak_portal;
GRANT UPDATE (assigned_engineer_id,status,resolution_summary,resolved_by_kind,resolved_by_profile_id)
  ON sahayak.tickets TO sahayak_portal;
GRANT USAGE ON SEQUENCE sahayak.tickets_ticket_number_seq TO sahayak_portal;
GRANT EXECUTE ON FUNCTION sahayak.initial_ticket_rules(), sahayak.ticket_created(), sahayak.portal_ticket_update()
  TO sahayak_portal;
