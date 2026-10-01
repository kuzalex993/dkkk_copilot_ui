"""Thin HTTP client for the Copilot backend service."""

from __future__ import annotations

import io
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime

import requests

from dkkk_copilot_ui.config import Settings


class BackendError(Exception):
    """Raised when the backend returns a non-success response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass
class UploadResult:
    content: str
    filename: str
    save_dir: str


@dataclass
class InvokeResult:
    text: str
    excel_filename: str | None = None
    excel_bytes: bytes | None = None


def _request_time() -> str:
    return datetime.now(UTC).astimezone().isoformat()


def _common_headers(client_id: str, session_id: str, user_id: str) -> dict[str, str]:
    return {
        "x-trace-id": str(uuid.uuid4()),
        "x-request-time": _request_time(),
        "x-client-id": client_id,
        "x-session-id": session_id,
        "x-user-id": user_id,
    }


def _raise_for_error(response: requests.Response) -> None:
    if response.ok:
        return
    message = response.text
    try:
        payload = response.json()
        message = (
            payload.get("error_description")
            or payload.get("detail")
            or payload
        )
    except ValueError:
        pass
    raise BackendError(response.status_code, str(message))


def upload_file(
    settings: Settings,
    file_bytes: bytes,
    filename: str,
    client_id: str,
    session_id: str,
    user_id: str,
) -> UploadResult:
    headers = _common_headers(client_id, session_id, user_id)
    files = {
        "file": (
            filename,
            file_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = requests.post(
        settings.upload_url,
        headers=headers,
        files=files,
        timeout=settings.request_timeout,
    )
    _raise_for_error(response)
    payload = response.json()
    return UploadResult(
        content=payload["content"],
        filename=payload["filename"],
        save_dir=payload["save_dir"],
    )


def invoke_agent(
    settings: Settings,
    message: str,
    client_id: str,
    session_id: str,
    user_id: str,
) -> InvokeResult:
    headers = _common_headers(client_id, session_id, user_id)
    headers["Content-Type"] = "application/json"
    response = requests.post(
        settings.invoke_url,
        headers=headers,
        json={"message": message},
        timeout=settings.request_timeout,
    )
    _raise_for_error(response)

    content_type = response.headers.get("content-type", "")

    if "zip" in content_type or "octet-stream" in content_type:
        return _parse_zip_response(response.content)

    try:
        payload = response.json()
    except ValueError:
        return InvokeResult(text=response.text)

    if isinstance(payload, dict) and "message" in payload:
        return InvokeResult(text=str(payload["message"]))
    return InvokeResult(text=str(payload))


def _parse_zip_response(content: bytes) -> InvokeResult:
    text_answer = ""
    excel_filename: str | None = None
    excel_bytes: bytes | None = None

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for name in archive.namelist():
            lower = name.lower()
            data = archive.read(name)
            if lower.endswith((".xlsx", ".xlsm", ".xls")):
                excel_filename = name
                excel_bytes = data
            elif lower.endswith((".txt", ".md", ".json")):
                text_answer = data.decode("utf-8", errors="replace")

    return InvokeResult(
        text=text_answer or "Агент вернул ответ без текстового содержимого.",
        excel_filename=excel_filename,
        excel_bytes=excel_bytes,
    )
