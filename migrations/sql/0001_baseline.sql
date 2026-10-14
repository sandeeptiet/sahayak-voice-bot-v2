-- Sahayak Portal prerequisite schema v0.1; PostgreSQL 17 baseline.
-- Run ONCE in an EMPTY sahayak database as the setup administrator.
-- This creates preparation tables/triggers, NOT a production-authorized API.
-- Application roles/grants, lifecycle actions and migrations come during build.
-- No network calls, AWS extensions, phone calls or secrets in this script.
CREATE SCHEMA sahayak;
REVOKE ALL ON SCHEMA sahayak FROM PUBLIC;

CREATE TABLE sahayak.profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_issuer text NOT NULL,
    identity_subject text NOT NULL,
    employee_code text NOT NULL UNIQUE,
    display_name text NOT NULL,
    email text NOT NULL,
    department text,
    phone_e164 text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
    phone_trusted_at timestamptz,
    phone_trusted_by text,
    phone_trust_method text,
    active boolean NOT NULL DEFAULT true,
    is_test boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (identity_issuer, identity_subject),
    CHECK (phone_trusted_at IS NULL OR
      (phone_e164 IS NOT NULL AND phone_trusted_by IS NOT NULL AND phone_trust_method IS NOT NULL))
);
-- This is an admin-maintained directory mirror, never user-editable authority.
-- API authorization must check verified Cognito groups and active directory scope.
CREATE TABLE sahayak.profile_roles (
    profile_id uuid NOT NULL REFERENCES sahayak.profiles(id),
    role text NOT NULL CHECK (role IN ('employee','engineer','portal_admin')),
    PRIMARY KEY (profile_id, role)
);

CREATE TABLE sahayak.tickets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    employee_id uuid NOT NULL REFERENCES sahayak.profiles(id),
    request_key uuid NOT NULL,
    category text NOT NULL CHECK (category IN
      ('account_access','network','vpn','microsoft_365','hardware','other','software')),
    description text NOT NULL CHECK (length(btrim(description)) BETWEEN 1 AND 10000),
    asset_tag text,
    priority text NOT NULL CHECK (priority IN ('low','medium','high','critical')),
    status text NOT NULL DEFAULT 'new' CHECK (status IN
      ('new','in_progress','transferred_to_human','completed','failed','cancelled')),
    assigned_engineer_id uuid REFERENCES sahayak.profiles(id),
    callback_at timestamptz,
    schedule_generation integer NOT NULL DEFAULT 1 CHECK (schedule_generation > 0),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    resolution_summary text,
    resolved_by_kind text CHECK (resolved_by_kind IN ('agent','engineer')),
    resolved_by_profile_id uuid REFERENCES sahayak.profiles(id),
    is_test boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, request_key)
);
CREATE INDEX tickets_employee_history ON sahayak.tickets(employee_id, created_at DESC);
CREATE INDEX tickets_human_queue ON sahayak.tickets(priority, callback_at, created_at)
  WHERE status = 'transferred_to_human';
CREATE INDEX tickets_assignee ON sahayak.tickets(assigned_engineer_id, status);

CREATE TABLE sahayak.ticket_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    event_type text NOT NULL,
    previous_status text,
    new_status text NOT NULL,
    actor_kind text NOT NULL,
    actor_id text NOT NULL,
    note text NOT NULL,
    details jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ticket_events_timeline ON sahayak.ticket_events(ticket_id, id);

CREATE TABLE sahayak.ticket_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    author_profile_id uuid NOT NULL REFERENCES sahayak.profiles(id),
    visibility text NOT NULL CHECK (visibility IN ('employee','internal')),
    body text NOT NULL CHECK (length(btrim(body)) > 0),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sahayak.call_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    campaign_id uuid NOT NULL,
    schedule_generation integer NOT NULL CHECK (schedule_generation > 0),
    call_kind text NOT NULL CHECK (call_kind IN ('ai','human')),
    dial_action_id uuid NOT NULL UNIQUE,
    livekit_room text,
    livekit_call_id text UNIQUE,
    exotel_call_id text UNIQUE,
    operational_state text NOT NULL DEFAULT 'claimed',
    result text, -- classification/retry policy deliberately not finalized
    qualifies_as_unanswered boolean, -- NULL means not yet classified
    claimed_at timestamptz NOT NULL DEFAULT now(),
    answered_at timestamptz,
    ended_at timestamptz,
    UNIQUE (ticket_id, attempt_number),
    UNIQUE (id, ticket_id)
);
CREATE TABLE sahayak.conversation_turns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    call_id uuid,
    turn_number integer NOT NULL CHECK (turn_number > 0),
    speaker text NOT NULL CHECK (speaker IN ('employee','agent','engineer')),
    language text,
    redacted_text text NOT NULL,
    delivery_state text NOT NULL CHECK (delivery_state IN
      ('received','generated','approved','spoken','interrupted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (call_id, ticket_id) REFERENCES sahayak.call_attempts(id, ticket_id),
    UNIQUE (ticket_id, turn_number),
    UNIQUE (id, ticket_id)
);
CREATE TABLE sahayak.resolution_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    employee_turn_id uuid NOT NULL,
    validated_by text NOT NULL,
    validation_note text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (employee_turn_id, ticket_id) REFERENCES sahayak.conversation_turns(id, ticket_id),
    UNIQUE (id, ticket_id)
);
ALTER TABLE sahayak.tickets ADD COLUMN completion_evidence_id uuid;
ALTER TABLE sahayak.tickets ADD CONSTRAINT completion_same_ticket
  FOREIGN KEY (completion_evidence_id, id) REFERENCES sahayak.resolution_evidence(id, ticket_id);

CREATE TABLE sahayak.troubleshooting_steps (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    instruction text NOT NULL,
    outcome text,
    source_document text,
    source_version text,
    source_page text,
    employee_visible boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE sahayak.callback_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    due_at timestamptz NOT NULL,
    handling_team text NOT NULL CHECK (handling_team IN ('ai','human')),
    schedule_generation integer NOT NULL CHECK (schedule_generation > 0),
    requested_by text NOT NULL,
    reason text NOT NULL,
    scheduler_reference text,
    superseded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ticket_id, schedule_generation)
);

CREATE TABLE sahayak.outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    event_type text NOT NULL,
    schedule_generation integer NOT NULL CHECK (schedule_generation > 0),
    payload jsonb NOT NULL,
    available_at timestamptz NOT NULL,
    is_test boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    lease_owner text,
    lease_until timestamptz,
    publish_attempts integer NOT NULL DEFAULT 0 CHECK (publish_attempts >= 0),
    last_error_code text,
    UNIQUE (ticket_id, event_type, schedule_generation)
);
CREATE INDEX outbox_ready ON sahayak.outbox_events(available_at, created_at)
  WHERE published_at IS NULL AND is_test = false;
CREATE TABLE sahayak.action_receipts (
    consumer text NOT NULL,
    action_id uuid NOT NULL,
    ticket_id uuid NOT NULL REFERENCES sahayak.tickets(id),
    state text NOT NULL CHECK (state IN ('pending','succeeded','uncertain','failed')),
    result_reference text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, action_id)
);

-- Preserve documented priority. Broad English substring matches are intentional.
CREATE FUNCTION sahayak.initial_ticket_rules() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE lvl integer;
BEGIN
    IF NEW.status <> 'new' OR NEW.version <> 1 OR NEW.schedule_generation <> 1 THEN
        RAISE EXCEPTION 'New tickets must start new, version 1, generation 1';
    END IF;
    IF NEW.callback_at IS NOT NULL AND NEW.callback_at <= now() THEN
        RAISE EXCEPTION 'Callback must be in the future';
    END IF;
    lvl := CASE WHEN NEW.category IN ('account_access','network') THEN 3
                WHEN NEW.category = 'software' THEN 1 ELSE 2 END;
    IF lower(NEW.description) LIKE ANY(ARRAY['%cannot work%','%can''t work%',
       '%locked out%','%urgent%','%critical%','%down%',
       '%not working at all%','%completely stuck%']) THEN
        lvl := least(lvl + 1, 4);
    END IF;
    NEW.priority := (ARRAY['low','medium','high','critical'])[lvl];
    RETURN NEW;
END;
$$;
CREATE TRIGGER ticket_initial_rules BEFORE INSERT ON sahayak.tickets
  FOR EACH ROW EXECUTE FUNCTION sahayak.initial_ticket_rules();

-- Same transaction as ticket insertion: no network side effect.
CREATE FUNCTION sahayak.ticket_created() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor text; kind text; reason text;
BEGIN
    actor := nullif(current_setting('sahayak.actor_id', true), '');
    kind := nullif(current_setting('sahayak.actor_kind', true), '');
    reason := nullif(current_setting('sahayak.reason', true), '');
    IF actor IS NULL OR kind IS NULL OR reason IS NULL THEN
        RAISE EXCEPTION 'Set transaction-local trusted actor_id, actor_kind and reason';
    END IF;
    INSERT INTO sahayak.ticket_events(ticket_id,event_type,new_status,actor_kind,actor_id,note)
      VALUES (NEW.id,'ticket.created','new',kind,actor,reason);
    IF NEW.callback_at IS NOT NULL THEN
      INSERT INTO sahayak.callback_requests(ticket_id,due_at,handling_team,
        schedule_generation,requested_by,reason)
        VALUES (NEW.id,NEW.callback_at,'ai',NEW.schedule_generation,actor,reason);
    END IF;
    INSERT INTO sahayak.outbox_events(ticket_id,event_type,schedule_generation,
      payload,available_at,is_test)
      VALUES (NEW.id,'ai.call.requested',NEW.schedule_generation,
        jsonb_build_object('ticket_id',NEW.id,'schedule_generation',NEW.schedule_generation),
        coalesce(NEW.callback_at,now()),NEW.is_test);
    RETURN NEW;
END;
$$;
CREATE TRIGGER ticket_created_outbox AFTER INSERT ON sahayak.tickets
  FOR EACH ROW EXECUTE FUNCTION sahayak.ticket_created();

-- Fail closed during preparation. Full audited lifecycle updates are implemented
-- later via migrations plus the authenticated domain service. No direct UPDATEs.
CREATE FUNCTION sahayak.block_prerequisite_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Prerequisite schema: lifecycle mutation is not enabled; build and verify domain service first';
END;
$$;
CREATE TRIGGER tickets_preparation_only BEFORE UPDATE OR DELETE ON sahayak.tickets
  FOR EACH ROW EXECUTE FUNCTION sahayak.block_prerequisite_mutation();
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON sahayak.ticket_events
  FOR EACH ROW EXECUTE FUNCTION sahayak.block_prerequisite_mutation();

REVOKE ALL ON ALL TABLES IN SCHEMA sahayak FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA sahayak FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA sahayak FROM PUBLIC;
