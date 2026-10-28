"""Backend configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urljoin

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


@dataclass(frozen=True)
class Settings:
    host: str
    upload_path: str
    stream_path: str
    client_id: str
    request_timeout: float

    @property
    def upload_url(self) -> str:
        return urljoin(self.host.rstrip("/") + "/", self.upload_path.lstrip("/"))

    @property
    def stream_url(self) -> str:
        return urljoin(self.host.rstrip("/") + "/", self.stream_path.lstrip("/"))


def get_settings() -> Settings:
    return Settings(
        host=_env("BACKEND_HOST", "http://localhost:8080"),
        upload_path=_env("BACKEND_UPLOAD_PATH", "/api/v1/upload"),
        stream_path=_env("BACKEND_STREAM_PATH", "/api/v1/invoke-agent/stream"),
        client_id=_env("BACKEND_CLIENT_ID", "CI00000000"),
        request_timeout=float(_env("BACKEND_REQUEST_TIMEOUT", "60")),
    )
