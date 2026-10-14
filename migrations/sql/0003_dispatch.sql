-- Operational receipts only; no change to ticket lifecycle or portal grants.
CREATE TABLE sahayak.dispatch_preflights (
    event_id uuid PRIMARY KEY REFERENCES sahayak.outbox_events(id),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    schedule_generation integer NOT NULL CHECK (schedule_generation > 0),
    result text NOT NULL CHECK (result IN ('ready_calls_disabled','skipped_state',
        'skipped_generation','skipped_test','skipped_contact','skipped_assignment')),
    workflow_version text NOT NULL CHECK (workflow_version = 'preflight-v1'),
    processed_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON sahayak.dispatch_preflights FROM PUBLIC;
CREATE TRIGGER dispatch_receipts_append_only BEFORE UPDATE OR DELETE
  ON sahayak.dispatch_preflights FOR EACH ROW
  EXECUTE FUNCTION sahayak.block_prerequisite_mutation();

-- Lock the ticket without granting worker UPDATE on business tables or exposing PII.
-- Caller locks outbox first. Ticket mutators serialize on this same ticket lock.
CREATE FUNCTION sahayak.dispatch_context(event_uuid uuid)
RETURNS TABLE(ticket_id uuid, event_generation integer, current_generation integer,
    status text, assigned boolean, is_test boolean, contact_ready boolean,
    available_at timestamptz, callback_at timestamptz, database_now timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, sahayak AS $$
DECLARE event sahayak.outbox_events%ROWTYPE; item sahayak.tickets%ROWTYPE;
BEGIN
  SELECT * INTO event FROM sahayak.outbox_events WHERE id=event_uuid;
  IF NOT FOUND OR event.event_type <> 'ai.call.requested' THEN RETURN; END IF;
  SELECT * INTO item FROM sahayak.tickets WHERE id=event.ticket_id FOR UPDATE;
  RETURN QUERY SELECT item.id,event.schedule_generation,item.schedule_generation,
    item.status,item.assigned_engineer_id IS NOT NULL,item.is_test OR event.is_test,
    EXISTS(SELECT 1 FROM sahayak.profiles p JOIN sahayak.profile_roles r ON r.profile_id=p.id
      WHERE p.id=item.employee_id AND p.active AND NOT p.is_test AND r.role='employee'
        AND p.phone_e164 IS NOT NULL AND p.phone_trusted_at IS NOT NULL),
    event.available_at,item.callback_at,clock_timestamp();
END;
$$;
REVOKE ALL ON FUNCTION sahayak.dispatch_context(uuid) FROM PUBLIC;
