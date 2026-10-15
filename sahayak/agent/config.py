from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAHAYAK_AGENT_", env_file=ROOT / ".env",
        extra="ignore", hide_input_in_errors=True,
    )
    sarvam_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="SARVAM_API_KEY")
    aws_profile: str = "default"
    aws_region: str = "ap-south-1"
    knowledge_base_id: str = "HP5QXRQ6LQ"
    source_prefix: str = "s3://sahayak-dev-knowledge-docs-346401055256/pilot-v1/"
    chat_model: str = "sarvam-105b-conversations"
    stt_model: Literal["saaras:v3"] = "saaras:v3"
    tts_model: Literal["bulbul:v3"] = "bulbul:v3"
    speaker: str = "shubh"
    sample_rate: Literal[16000, 22050, 24000] = 24000
    timeout_seconds: float = Field(default=30, gt=0, le=60)
    max_output_tokens: int = Field(default=400, ge=64, le=800)

    def key(self):
        value = self.sarvam_api_key.get_secret_value().strip()
        if not value:
            raise ValueError("SARVAM_API_KEY is required")
        return value
