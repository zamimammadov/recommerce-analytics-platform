"""Runtime configuration loaded from environment variables.

The project deliberately keeps secrets out of source control.  Local values
come from ``.env`` while deployed environments inject the same variables via
their secret manager.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "recommerce"
    postgres_user: str = "recommerce"
    postgres_password: str = "change-me-locally"
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        explicit_url = os.getenv("DATABASE_URL")
        if explicit_url:
            return explicit_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            postgres_host=os.getenv("POSTGRES_HOST", cls.postgres_host),
            postgres_port=int(os.getenv("POSTGRES_PORT", str(cls.postgres_port))),
            postgres_db=os.getenv("POSTGRES_DB", cls.postgres_db),
            postgres_user=os.getenv("POSTGRES_USER", cls.postgres_user),
            postgres_password=os.getenv("POSTGRES_PASSWORD", cls.postgres_password),
            log_level=os.getenv("LOG_LEVEL", cls.log_level).upper(),
        )
