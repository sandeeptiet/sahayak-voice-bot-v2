from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sahayak.intake import Category

Status = Literal["new", "in_progress", "transferred_to_human", "completed", "failed", "cancelled"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NewTicket(Input):
    request_key: UUID
    category: Category
    description: str = Field(min_length=1, max_length=10000)
    asset_tag: str | None = Field(default=None, max_length=100)
    callback_at: datetime | None = None

    @field_validator("asset_tag")
    @classmethod
    def empty_asset(cls, value):
        return value or None


class Claim(Input):
    expected_version: int = Field(ge=1)


class Outcome(Claim):
    status: Literal["completed", "failed"]
    note: str = Field(min_length=1, max_length=5000)


class TicketView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticket_number: int
    employee_id: UUID
    category: str
    description: str
    asset_tag: str | None
    priority: str
    status: Status
    assigned_engineer_id: UUID | None
    callback_at: datetime | None
    version: int
    resolution_summary: str | None
    created_at: datetime
    updated_at: datetime
