"""PostgreSQL coordination. All transactions end before queue network operations."""
from uuid import uuid4
from sqlalchemy import text
from .workflow import workflow

class Store:
    def __init__(self, engine): self.engine=engine

    def check(self):
        with self.engine.connect() as c:
            if c.scalar(text('SELECT version_num FROM public.alembic_version'))!='0003_dispatch':
                raise ValueError('Apply the worker database setup first')
            if c.scalar(text('SELECT current_user'))!='sahayak_dispatch':
                raise ValueError('Worker must use its dedicated database login')

    def claim(self, max_attempts, lease_seconds):
        # Fresh UUID is a fencing token; a late sender cannot finish another lease.
        token=str(uuid4())
        with self.engine.begin() as c:
            row=c.execute(text("""WITH candidate AS (
              SELECT id FROM sahayak.outbox_events
              WHERE published_at IS NULL AND NOT is_test AND event_type='ai.call.requested'
                AND available_at<=now() AND (lease_until IS NULL OR lease_until<=now())
                AND publish_attempts < :limit
              ORDER BY available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1)
              UPDATE sahayak.outbox_events o SET lease_owner=:token,
                lease_until=now()+make_interval(secs=>:seconds),publish_attempts=publish_attempts+1
              FROM candidate WHERE o.id=candidate.id
              RETURNING o.id,o.ticket_id,o.schedule_generation"""),
              {'limit':max_attempts,'token':token,'seconds':lease_seconds}).mappings().first()
            return dict(row,lease=token) if row else None

    def published(self, event):
        with self.engine.begin() as c:
            return c.execute(text("""UPDATE sahayak.outbox_events SET published_at=now(),
              lease_owner=NULL,lease_until=NULL,last_error_code=NULL
              WHERE id=:id AND lease_owner=:lease AND published_at IS NULL"""),event).rowcount==1

    def failed(self, event):
        # Error text can contain secrets; persist a fixed code, with bounded backoff.
        with self.engine.begin() as c:
            c.execute(text("""UPDATE sahayak.outbox_events SET last_error_code='queue_send_failed',
              lease_until=now()+make_interval(secs=>least(300,5*publish_attempts))
              WHERE id=:id AND lease_owner=:lease AND published_at IS NULL"""),event)

    def consume(self, envelope):
        with self.engine.begin() as c:
            event=c.execute(text('SELECT * FROM sahayak.outbox_events WHERE id=:id FOR UPDATE'),
                            {'id':str(envelope.event_id)}).mappings().first()
            if not event or event['event_type']!='ai.call.requested' or str(event['ticket_id'])!=str(envelope.ticket_id) or event['schedule_generation']!=envelope.schedule_generation:
                return 'invalid'  # No deletion: bounded queue retries then configured DLQ.
            existing=c.scalar(text('SELECT result FROM sahayak.dispatch_preflights WHERE event_id=:id'),{'id':event['id']})
            if existing: return 'duplicate'
            context=c.execute(text('SELECT * FROM sahayak.dispatch_context(:id)'),{'id':event['id']}).mappings().one()
            result=workflow.invoke(dict(context))['result']
            if result=='deferred': return result
            c.execute(text("""INSERT INTO sahayak.dispatch_preflights
              (event_id,ticket_id,schedule_generation,result,workflow_version)
              VALUES (:id,:ticket,:generation,:result,'preflight-v1')"""),
              {'id':event['id'],'ticket':event['ticket_id'],'generation':event['schedule_generation'],'result':result})
        # Commit precedes the caller's queue deletion. Redelivery uses the receipt.
        return result

    def status(self, limit):
        with self.engine.connect() as c:
            rows=c.execute(text("""SELECT
              count(*) FILTER(WHERE published_at IS NULL AND NOT is_test AND event_type='ai.call.requested' AND publish_attempts<:limit AND available_at<=now()) AS pending_due,
              count(*) FILTER(WHERE published_at IS NULL AND NOT is_test AND event_type='ai.call.requested' AND available_at>now()) AS future,
              count(*) FILTER(WHERE published_at IS NULL AND NOT is_test AND event_type='ai.call.requested' AND publish_attempts>=:limit) AS exhausted,
              count(*) FILTER(WHERE published_at IS NOT NULL AND NOT is_test AND event_type='ai.call.requested') AS published
              FROM sahayak.outbox_events"""),{'limit':limit}).mappings().one()
            results=c.execute(text('SELECT result,count(*) AS count FROM sahayak.dispatch_preflights GROUP BY result')).mappings().all()
            attention=c.execute(text('''SELECT o.id,o.publish_attempts,o.last_error_code,
              CASE WHEN o.published_at IS NULL THEN 'publish_exhausted' ELSE 'awaiting_receipt' END AS reason
              FROM sahayak.outbox_events o WHERE NOT o.is_test AND o.event_type='ai.call.requested'
              AND ((o.published_at IS NULL AND o.publish_attempts>=:limit)
                OR (o.published_at IS NOT NULL AND NOT EXISTS
                  (SELECT 1 FROM sahayak.dispatch_preflights p WHERE p.event_id=o.id)))
              ORDER BY o.created_at LIMIT 20'''),{'limit':limit}).mappings().all()
            return {'outbox':dict(rows),'preflights':[dict(r) for r in results],
                    'attention':[dict(row,id=str(row['id'])) for row in attention]}


    def retry(self, event_id, limit):
        with self.engine.begin() as c:
            return c.execute(text("""UPDATE sahayak.outbox_events
              SET publish_attempts=0,lease_owner=NULL,lease_until=NULL,last_error_code=NULL
              WHERE id=:id AND published_at IS NULL AND publish_attempts>=:limit
                AND (lease_until IS NULL OR lease_until<=now()) AND NOT is_test
                AND event_type='ai.call.requested'"""),{'id':event_id,'limit':limit}).rowcount==1

    def replay(self, event_id):
        # Explicit operator recovery for a lost/DLQ message; never erase a receipt.
        with self.engine.begin() as c:
            return c.execute(text("""UPDATE sahayak.outbox_events o SET published_at=NULL,
              publish_attempts=0,lease_owner=NULL,lease_until=NULL,last_error_code=NULL
              WHERE o.id=:id AND o.published_at IS NOT NULL AND NOT o.is_test
                AND o.event_type='ai.call.requested'
                AND (o.lease_until IS NULL OR o.lease_until<=now())
                AND NOT EXISTS(SELECT 1 FROM sahayak.dispatch_preflights p WHERE p.event_id=o.id)"""),
              {'id':event_id}).rowcount==1
