-- Trigger functions run as the schema owner, with fixed resolution paths.
-- The runtime login cannot insert audit/outbox records or edit profiles directly.
CREATE OR REPLACE FUNCTION sahayak.ticket_created()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, sahayak AS $$
DECLARE actor uuid; kind text; reason text;
BEGIN
  actor := nullif(current_setting('sahayak.actor_id', true), '')::uuid;
  kind := nullif(current_setting('sahayak.actor_kind', true), '');
  reason := nullif(btrim(current_setting('sahayak.reason', true)), '');
  IF actor IS NULL OR kind IS NULL OR reason IS NULL OR NEW.employee_id IS DISTINCT FROM actor THEN
    RAISE EXCEPTION 'Trusted actor context required';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM sahayak.profiles p JOIN sahayak.profile_roles r ON r.profile_id=p.id
      WHERE p.id=actor AND p.active AND NOT p.is_test AND r.role='employee'
        AND p.phone_e164 IS NOT NULL AND p.phone_trusted_at IS NOT NULL) THEN
    RAISE EXCEPTION 'Active employee with trusted phone required';
  END IF;
  IF NEW.status <> 'new' OR NEW.version <> 1 OR NEW.schedule_generation <> 1
     OR NEW.assigned_engineer_id IS NOT NULL OR NEW.resolution_summary IS NOT NULL
     OR NEW.resolved_by_kind IS NOT NULL OR NEW.resolved_by_profile_id IS NOT NULL
     OR NEW.completion_evidence_id IS NOT NULL OR NEW.is_test THEN
    RAISE EXCEPTION 'Invalid initial ticket fields';
  END IF;
  INSERT INTO sahayak.ticket_events(ticket_id,event_type,new_status,actor_kind,actor_id,note)
    VALUES (NEW.id,'ticket.created','new',kind,actor::text,reason);
  IF NEW.callback_at IS NOT NULL THEN
    INSERT INTO sahayak.callback_requests(ticket_id,due_at,handling_team,schedule_generation,requested_by,reason)
      VALUES (NEW.id,NEW.callback_at,'ai',NEW.schedule_generation,actor::text,reason);
  END IF;
  INSERT INTO sahayak.outbox_events(ticket_id,event_type,schedule_generation,payload,available_at,is_test)
    VALUES (NEW.id,'ai.call.requested',NEW.schedule_generation,
      jsonb_build_object('ticket_id',NEW.id,'schedule_generation',NEW.schedule_generation),
      coalesce(NEW.callback_at,now()),NEW.is_test);
  RETURN NEW;
END;
$$;

CREATE FUNCTION sahayak.portal_ticket_update()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, sahayak AS $$
DECLARE actor uuid; reason text; event text;
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Ticket deletion is disabled'; END IF;
  actor := nullif(current_setting('sahayak.actor_id', true), '')::uuid;
  reason := nullif(btrim(current_setting('sahayak.reason', true)), '');
  IF actor IS NULL OR reason IS NULL OR current_setting('sahayak.actor_kind',true) IS DISTINCT FROM 'engineer'
    OR NOT EXISTS (SELECT 1 FROM sahayak.profiles p JOIN sahayak.profile_roles r ON r.profile_id=p.id
      WHERE p.id=actor AND p.active AND NOT p.is_test AND r.role='engineer') THEN
    RAISE EXCEPTION 'Active engineer context required';
  END IF;
  IF OLD.status <> 'transferred_to_human' OR OLD.is_test THEN
    RAISE EXCEPTION 'Only escalated tickets can be changed by the portal';
  END IF;
  -- Immutable fields include identity, request key, schedule, evidence and priority.
  IF (to_jsonb(NEW) - ARRAY['assigned_engineer_id','status','resolution_summary','resolved_by_kind','resolved_by_profile_id'])
    IS DISTINCT FROM
     (to_jsonb(OLD) - ARRAY['assigned_engineer_id','status','resolution_summary','resolved_by_kind','resolved_by_profile_id']) THEN
    RAISE EXCEPTION 'Unsupported ticket field change';
  END IF;
  IF OLD.assigned_engineer_id IS NULL AND NEW.assigned_engineer_id = actor
     AND NEW.status = OLD.status
     AND NEW.resolution_summary IS NOT DISTINCT FROM OLD.resolution_summary
     AND NEW.resolved_by_kind IS NOT DISTINCT FROM OLD.resolved_by_kind
     AND NEW.resolved_by_profile_id IS NOT DISTINCT FROM OLD.resolved_by_profile_id THEN
    event := 'ticket.assigned';
  ELSIF OLD.assigned_engineer_id = actor AND NEW.assigned_engineer_id = actor
     AND NEW.status IN ('completed','failed')
     AND NEW.resolved_by_kind = 'engineer' AND NEW.resolved_by_profile_id = actor
     AND nullif(btrim(NEW.resolution_summary),'') IS NOT NULL
     AND length(NEW.resolution_summary) <= 5000 THEN
    event := 'ticket.' || NEW.status;
  ELSE
    RAISE EXCEPTION 'Invalid self-assignment or human outcome';
  END IF;
  NEW.version := OLD.version + 1;
  NEW.updated_at := now();
  INSERT INTO sahayak.ticket_events(ticket_id,event_type,previous_status,new_status,actor_kind,actor_id,note,details)
    VALUES (NEW.id,event,OLD.status,NEW.status,'engineer',actor::text,reason,
      jsonb_build_object('assigned_engineer_id',NEW.assigned_engineer_id,'version',NEW.version));
  RETURN NEW;
END;
$$;
DROP TRIGGER tickets_preparation_only ON sahayak.tickets;
CREATE TRIGGER tickets_portal_guard BEFORE UPDATE OR DELETE ON sahayak.tickets
  FOR EACH ROW EXECUTE FUNCTION sahayak.portal_ticket_update();
REVOKE ALL ON FUNCTION sahayak.portal_ticket_update() FROM PUBLIC;
REVOKE ALL ON FUNCTION sahayak.ticket_created() FROM PUBLIC;
CREATE INDEX IF NOT EXISTS tickets_employee_history ON sahayak.tickets(employee_id, ticket_number DESC);
CREATE INDEX IF NOT EXISTS tickets_human_queue ON sahayak.tickets(status, ticket_number DESC);
CREATE INDEX IF NOT EXISTS tickets_assignee ON sahayak.tickets(assigned_engineer_id, status);
CREATE INDEX IF NOT EXISTS ticket_events_timeline ON sahayak.ticket_events(ticket_id, id);
