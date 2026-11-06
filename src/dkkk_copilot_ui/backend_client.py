"""Thin HTTP client for the Copilot backend service."""

from __future__ import annotations

import json
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

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


TERMINAL_EVENTS = frozenset({"clarification", "answer", "error"})


@dataclass
class StreamEvent:
    type: str
    data: dict[str, Any]


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


def stream_agent(
    settings: Settings,
    message: str,
    client_id: str,
    session_id: str,
    user_id: str,
) -> Iterator[StreamEvent]:
    """Yield SSE events or a final answer from the non-streaming ZIP endpoint."""
    headers = _common_headers(client_id, session_id, user_id)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "text/event-stream, application/zip"
    with requests.post(
        settings.stream_url,
        headers=headers,
        json={"message": message},
        stream=True,
        # Read timeout applies between chunks; the backend pings every ~15 s.
        timeout=settings.request_timeout,
    ) as response:
        _raise_for_error(response)
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type == "application/zip":
            try:
                with zipfile.ZipFile(BytesIO(response.content)) as archive:
                    text = archive.read("txt_response.txt").decode("utf-8-sig")
            except (zipfile.BadZipFile, KeyError, UnicodeError) as exc:
                raise BackendError(
                    response.status_code,
                    "Некорректный ZIP-ответ агента: не удалось прочитать txt_response.txt.",
                ) from exc
            yield StreamEvent("answer", {"text": text})
            return
        if content_type != "text/event-stream":
            raise BackendError(
                response.status_code,
                f"Неожиданный формат ответа агента: {content_type or 'Content-Type отсутствует'}.",
            )
        response.encoding = "utf-8"
        event_type = "message"
        data_lines: list[str] = []
        for line in response.iter_lines(decode_unicode=True):
            if line is None:
                continue
            if line == "":
                if data_lines:
                    event = _make_event(event_type, "\n".join(data_lines))
                    yield event
                    if event.type in TERMINAL_EVENTS:
                        return
                event_type, data_lines = "message", []
            elif line.startswith(":"):
                continue  # heartbeat `: ping`
            elif line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
    raise BackendError(0, "Поток оборвался без финального ответа.")


def _make_event(event_type: str, raw: str) -> StreamEvent:
    try:
        data = json.loads(raw)
    except ValueError:
        data = {"text": raw}
    if not isinstance(data, dict):
        data = {"text": str(data)}
    return StreamEvent(type=event_type, data=data)
