"""Rollback-only PostgreSQL integration checks, invoked by the setup command.

Temporary fictional profiles have no committed lifetime. All events remain
uncommitted and invisible to any worker. No network calls or queue publishing.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import HTTPException
from .api.service import Actor, create_ticket, claim_ticket, record_outcome, tickets, ticket
from .api.schemas import NewTicket, Outcome


def verify(connection):
    transaction = connection.begin()
    try:
        employee, engineer, other = uuid4(), uuid4(), uuid4()
        for pid, role in [(employee,"employee"),(engineer,"engineer"),(other,"engineer")]:
            connection.execute(text("""INSERT INTO sahayak.profiles
                (id,identity_issuer,identity_subject,employee_code,display_name,email,
                 phone_e164,phone_trusted_at,phone_trusted_by,phone_trust_method)
                VALUES (:id,'urn:sahayak:rollback-test',:subject,:code,'Rollback test',
                  'test@example.invalid','+919999999999',now(),'setup','Synthetic rollback-only fixture')"""),
                {"id":pid,"subject":str(pid),"code":f"TEST-{pid}"})
            connection.execute(text("INSERT INTO sahayak.profile_roles(profile_id,role) VALUES (:id,:role)"),{"id":pid,"role":role})
        connection.exec_driver_sql("SET LOCAL ROLE sahayak_portal")
        a=Actor(employee,"Test",frozenset({"employee"}),True)
        e=Actor(engineer,"Engineer",frozenset({"engineer"}),True)
        b=Actor(other,"Other",frozenset({"engineer"}),True)
        with Session(bind=connection,join_transaction_mode="create_savepoint",expire_on_commit=False) as session:
            data=NewTicket(request_key=uuid4(),category="account_access",description="Locked out and cannot work",
                           callback_at=datetime.now(timezone.utc)+timedelta(days=1))
            created=create_ticket(session,a,data)
            assert created.priority=="critical" and created.status=="new"
            tid=created.id
            assert create_ticket(session,a,data).id==tid
            session.commit()
        # Audit and outbox can only be inspected by the setup administrator.
        connection.exec_driver_sql("RESET ROLE")
        assert connection.scalar(text("SELECT count(*) FROM sahayak.ticket_events WHERE ticket_id=:id"),{"id":tid})==1
        assert connection.scalar(text("SELECT count(*) FROM sahayak.outbox_events WHERE ticket_id=:id"),{"id":tid})==1
        assert connection.scalar(text("SELECT count(*) FROM sahayak.callback_requests WHERE ticket_id=:id"),{"id":tid})==1
        # Model an already-escalated agent ticket in this uncommitted test only.
        # Disable only the portal guard; restore it before testing human operations.
        connection.exec_driver_sql("ALTER TABLE sahayak.tickets DISABLE TRIGGER tickets_portal_guard")
        connection.execute(text("UPDATE sahayak.tickets SET status='transferred_to_human' WHERE id=:id"),{"id":tid})
        connection.exec_driver_sql("ALTER TABLE sahayak.tickets ENABLE TRIGGER tickets_portal_guard")
        connection.exec_driver_sql("SET LOCAL ROLE sahayak_portal")
        with Session(bind=connection,join_transaction_mode="create_savepoint",expire_on_commit=False) as session:
            claimed=claim_ticket(session,e,tid,1)
            assert claimed.assigned_engineer_id==engineer and claimed.version==2
            assert claim_ticket(session,e,tid,1).version==2
            try: claim_ticket(session,b,tid,2)
            except HTTPException as exc: assert exc.status_code==409
            else: raise AssertionError("Second engineer stole the claim")
            done=record_outcome(session,e,tid,Outcome(expected_version=2,status="completed",note="Synthetic outcome"))
            assert done.status=="completed" and done.version==3
            assert record_outcome(session,e,tid,Outcome(expected_version=2,status="completed",note="Synthetic outcome")).version==3
            session.commit()
        # Runtime cannot edit directory, delete tickets, or publish outbox directly.
        for sql in ["UPDATE sahayak.profiles SET active=false WHERE id=:id",
                    "DELETE FROM sahayak.tickets WHERE id=:id",
                    "UPDATE sahayak.outbox_events SET published_at=now() WHERE ticket_id=:id"]:
            savepoint=connection.begin_nested()
            try:
                connection.execute(text(sql),{"id":tid})
            except Exception as exc:
                assert getattr(getattr(exc,"orig",None),"sqlstate",None)=="42501"
                savepoint.rollback()
            else:
                savepoint.rollback(); raise AssertionError("Unexpected runtime privilege")
        connection.exec_driver_sql("RESET ROLE")
        assert connection.scalar(text("SELECT count(*) FROM sahayak.ticket_events WHERE ticket_id=:id"),{"id":tid})==3
        assert connection.scalar(text("SELECT count(*) FROM sahayak.outbox_events WHERE ticket_id=:id"),{"id":tid})==1
    finally:
        transaction.rollback()
