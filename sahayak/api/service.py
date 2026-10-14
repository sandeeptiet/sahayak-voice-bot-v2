"""Transactional ticket operations. Never initiates an external call."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sahayak.intake import assign_priority, validate_callback_time
from .auth import Principal
from .models import Profile, ProfileRole, Ticket
from .schemas import NewTicket, Outcome


@dataclass(frozen=True)
class Actor:
    id: UUID
    name: str
    roles: frozenset[str]
    phone_ready: bool

    @property
    def engineer(self):
        return "engineer" in self.roles


def actor_for(session: Session, principal: Principal) -> Actor:
    profile = session.scalar(select(Profile).where(
        Profile.identity_issuer == principal.issuer, Profile.identity_subject == principal.subject,
        Profile.active.is_(True), Profile.is_test.is_(False)))
    if profile is None:
        raise HTTPException(403, "Your active employee profile is not configured")
    directory_roles = set(session.scalars(select(ProfileRole.role).where(ProfileRole.profile_id == profile.id)))
    roles = frozenset(directory_roles.intersection(principal.groups))
    if not roles.intersection({"employee", "engineer"}):
        raise HTTPException(403, "Your account needs an employee or engineer role")
    return Actor(profile.id, profile.display_name, roles,
                 bool(profile.phone_e164 and profile.phone_trusted_at))


def require_engineer(actor: Actor):
    if not actor.engineer:
        raise HTTPException(403, "Only engineers can perform this action")


def context(session: Session, actor: Actor, reason: str):
    for key, value in {"actor_id": str(actor.id), "actor_kind": "engineer" if actor.engineer else "employee", "reason": reason}.items():
        session.execute(text("SELECT set_config(:key, :value, true)"), {"key": f"sahayak.{key}", "value": value})


def scoped_query(actor: Actor):
    query = select(Ticket).where(Ticket.is_test.is_(False))
    return query if actor.engineer else query.where(Ticket.employee_id == actor.id)


def tickets(session: Session, actor: Actor, status: str | None, before: int | None):
    query = scoped_query(actor)
    if status:
        query = query.where(Ticket.status == status)
    if before is not None:
        query = query.where(Ticket.ticket_number < before)
    return list(session.scalars(query.order_by(Ticket.ticket_number.desc()).limit(51)))


def ticket(session: Session, actor: Actor, ticket_id: UUID, *, lock=False):
    query = scoped_query(actor).where(Ticket.id == ticket_id)
    if lock:
        query = query.with_for_update()
    value = session.scalar(query)
    if value is None:
        raise HTTPException(404, "Ticket not found")
    return value


def same_request(existing: Ticket, data: NewTicket):
    return (existing.category == data.category and existing.description == data.description
            and existing.asset_tag == data.asset_tag and existing.callback_at == data.callback_at)


def create_ticket(session: Session, actor: Actor, data: NewTicket):
    if "employee" not in actor.roles:
        raise HTTPException(403, "An employee role is required to create a ticket")
    old = session.scalar(select(Ticket).where(Ticket.employee_id == actor.id, Ticket.request_key == data.request_key))
    if old is not None:
        if not same_request(old, data):
            raise HTTPException(409, "This submission key was already used for different ticket details")
        return old
    if not actor.phone_ready:
        raise HTTPException(422, "Ask your administrator to confirm your callback number before creating a ticket")
    if data.callback_at is not None:
        try:
            validate_callback_time(data.callback_at, now=datetime.now(timezone.utc))
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
    context(session, actor, "Employee submitted a ticket")
    statement = insert(Ticket).values(employee_id=actor.id, request_key=data.request_key,
        category=data.category.value, description=data.description, asset_tag=data.asset_tag,
        callback_at=data.callback_at, priority=assign_priority(data.category, data.description).value)
    new_id = session.scalar(statement.on_conflict_do_nothing(index_elements=["employee_id", "request_key"]).returning(Ticket.id))
    result = session.scalar(select(Ticket).where(Ticket.employee_id == actor.id, Ticket.request_key == data.request_key))
    if result is None or not same_request(result, data):
        raise HTTPException(409, "This submission key was already used for different ticket details")
    return result


def claim_ticket(session: Session, actor: Actor, ticket_id: UUID, expected_version: int):
    require_engineer(actor)
    value = ticket(session, actor, ticket_id, lock=True)
    if value.status != "transferred_to_human":
        raise HTTPException(409, "Only tickets escalated to human support can be claimed")
    if value.assigned_engineer_id == actor.id:
        return value  # Retrying a successful claim is safe.
    if value.assigned_engineer_id is not None:
        raise HTTPException(409, "Another engineer has already claimed this ticket")
    if value.version != expected_version:
        raise HTTPException(409, "Ticket changed; refresh the list and try again")
    context(session, actor, "Engineer assigned the ticket to themselves")
    value.assigned_engineer_id = actor.id
    session.flush()
    session.refresh(value)
    return value


def record_outcome(session: Session, actor: Actor, ticket_id: UUID, data: Outcome):
    require_engineer(actor)
    value = ticket(session, actor, ticket_id, lock=True)
    if value.assigned_engineer_id != actor.id:
        raise HTTPException(403, "Only the assigned engineer can update this ticket")
    if value.status == data.status and value.resolution_summary == data.note:
        return value  # Same outcome retry after a lost response.
    if value.status != "transferred_to_human" or value.version != data.expected_version:
        raise HTTPException(409, "Ticket changed or is already final; refresh the list")
    context(session, actor, data.note)
    value.status = data.status
    value.resolution_summary = data.note
    value.resolved_by_kind = "engineer"
    value.resolved_by_profile_id = actor.id
    session.flush()
    session.refresh(value)
    return value
