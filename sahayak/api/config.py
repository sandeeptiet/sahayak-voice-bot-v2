"""Private API configuration. Database secrets never enter the browser bundle."""
from pathlib import Path
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, create_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAHAYAK_", env_file=".env.api", extra="ignore")
    cognito_pool_id: str = "ap-south-1_Nd7EEM2ze"
    cognito_client_id: str = "u7bnhek68t0nu1pd1o7oavbjf"
    cognito_domain: str = "https://ap-south-1nd7eem2ze.auth.ap-south-1.amazoncognito.com"
    portal_origin: str = "http://localhost:5173"
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "sahayak"
    db_user: str = "sahayak_portal"
    db_password: SecretStr = SecretStr("")
    db_ca_file: str = ""

    @field_validator("cognito_domain")
    @classmethod
    def domain_is_https(cls, value):
        from urllib.parse import urlsplit
        u = urlsplit(value)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ("", "/"):
            raise ValueError("Cognito domain must be an HTTPS origin")
        return value.rstrip("/")

    @property
    def issuer(self):
        return f"https://cognito-idp.ap-south-1.amazonaws.com/{self.cognito_pool_id}"

    def engine(self):
        if not self.db_host or not self.db_password.get_secret_value() or not Path(self.db_ca_file).is_file():
            raise ValueError("Complete the private database configuration first")
        url = URL.create("postgresql+psycopg", username=self.db_user,
                         password=self.db_password.get_secret_value(), host=self.db_host,
                         port=self.db_port, database=self.db_name)
        return create_engine(url, pool_size=3, max_overflow=0, pool_timeout=10,
                             pool_pre_ping=True, hide_parameters=True,
                             connect_args={"sslmode": "verify-full", "sslrootcert": self.db_ca_file,
                                           "connect_timeout": 10, "options": "-c statement_timeout=15000 -c lock_timeout=5000"})
