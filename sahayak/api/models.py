"""Mappings for the existing PostgreSQL schema; migrations own DDL."""
from datetime import datetime
from uuid import UUID
from sqlalchemy import Boolean, DateTime, ForeignKey, Identity, Integer, BigInteger, String, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = {"schema": "sahayak"}
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    identity_issuer: Mapped[str] = mapped_column(String)
    identity_subject: Mapped[str] = mapped_column(String)
    employee_code: Mapped[str] = mapped_column(String)
    display_name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean)
    is_test: Mapped[bool] = mapped_column(Boolean)
    phone_e164: Mapped[str | None] = mapped_column(String)
    phone_trusted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProfileRole(Base):
    __tablename__ = "profile_roles"
    __table_args__ = {"schema": "sahayak"}
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("sahayak.profiles.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String, primary_key=True)


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"schema": "sahayak"}
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, server_default=text("gen_random_uuid()"))
    ticket_number: Mapped[int] = mapped_column(BigInteger, Identity(always=True))
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("sahayak.profiles.id"))
    request_key: Mapped[UUID] = mapped_column(Uuid)
    category: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    asset_tag: Mapped[str | None] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, server_default=text("'new'"))
    assigned_engineer_id: Mapped[UUID | None] = mapped_column(ForeignKey("sahayak.profiles.id"))
    callback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schedule_generation: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    resolution_summary: Mapped[str | None] = mapped_column(String)
    resolved_by_kind: Mapped[str | None] = mapped_column(String)
    resolved_by_profile_id: Mapped[UUID | None] = mapped_column(Uuid)
    completion_evidence_id: Mapped[UUID | None] = mapped_column(Uuid)
    is_test: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
