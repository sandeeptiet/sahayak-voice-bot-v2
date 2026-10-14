from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict
from sahayak.api.config import Settings

class WorkerSettings(Settings):
    model_config = SettingsConfigDict(env_prefix="SAHAYAK_", env_file=".env.worker", extra="ignore")
    db_user: str = "sahayak_dispatch"
    aws_region: str = "ap-south-1"
    aws_profile: str | None = None
    queue_url: str = ""
    worker_mode: Literal["preflight"] = "preflight"
    outbound_calls_enabled: Literal[False] = False
    max_publish_attempts: int = Field(default=8, ge=1, le=50)
    lease_seconds: int = Field(default=120, ge=60, le=600)
    poll_seconds: int = Field(default=10, ge=1, le=60)

    @field_validator("outbound_calls_enabled", mode="before")
    @classmethod
    def parse_disabled_calls(cls, value):
        # dotenv/environment values are strings; still reject every enabled value.
        if isinstance(value, str) and value.strip().lower() == "false":
            return False
        if value is not False:
            raise ValueError("Outbound calls must remain disabled")
        return value

    @field_validator("queue_url")
    @classmethod
    def queue_is_aws(cls, value):
        if not value: return value
        u = urlsplit(value)
        parts = u.path.strip("/").split("/")
        if (u.scheme != "https" or not u.hostname or not u.hostname.startswith("sqs.")
            or not u.hostname.endswith(".amazonaws.com") or u.username or u.password
            or u.port or u.query or u.fragment or len(parts)!=2
            or len(parts[0])!=12 or not parts[0].isdigit() or parts[1].endswith(".fifo")):
            raise ValueError("Use the standard AWS SQS queue URL")
        return value
