"""Streamlit UI for the Copilot chat bot backend."""

from __future__ import annotations

import uuid

import streamlit as st

from dkkk_copilot_ui.backend_client import (
    BackendError,
    StreamEvent,
    stream_agent,
    upload_file,
)
from dkkk_copilot_ui.config import get_settings

st.set_page_config(page_title="Copilot Chat", page_icon="💬", layout="centered")

settings = get_settings()

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "user_id" not in st.session_state:
    st.session_state.user_id = uuid.uuid4().hex[:8]
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

with st.sidebar:
    st.header("1. Загрузите Excel-файл")
    uploaded_file = st.file_uploader(
        "Excel файл для анализа",
        type=["xlsx", "xlsm", "xls"],
        accept_multiple_files=False,
    )

    if uploaded_file is not None and st.button(
        "Отправить файл на сервер", type="primary"
    ):
        with st.spinner("Загрузка файла..."):
            try:
                upload_result = upload_file(
                    settings,
                    file_bytes=uploaded_file.getvalue(),
                    filename=uploaded_file.name,
                    client_id=settings.client_id,
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.user_id,
                )
            except BackendError as exc:
                st.error(f"Ошибка загрузки ({exc.status_code}): {exc.message}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Не удалось связаться с бэкендом: {exc}")
            else:
                st.session_state.uploaded_filename = upload_result.filename
                st.success(upload_result.content)

    if st.session_state.uploaded_filename:
        st.info(f"Текущий файл на сервере: **{st.session_state.uploaded_filename}**")

    st.divider()
    st.header("Пользователь")
    st.session_state.user_id = st.text_input(
        "User ID",
        value=st.session_state.user_id,
        max_chars=8,
        help="Используется бэкендом как пространство имён для загруженного файла и истории диалога.",
    )
    st.caption(f"Session ID: `{st.session_state.session_id}`")

    if st.button("Новый диалог"):
        st.session_state.messages = []
        st.session_state.uploaded_filename = None
        st.rerun()

st.title("💬 Copilot Chat")

st.subheader("2. Чат с агентом")

PLAN_ICONS = {
    "pending": "⏳",
    "in_progress": "🔄",
    "completed": "✅",
    "skipped": "⏭️",
    "blocked": "⛔",
}
TOOL_ICONS = {"ok": "✅", "retry": "🔁", "failed": "❌"}
OUTCOME_NOTES = {
    "partial": "Ответ неполный.",
    "clarify": "Агенту нужно уточнение.",
    "refusal": "Агент отказался отвечать.",
}


def format_plan(steps: list[dict]) -> str:
    lines = []
    for step in steps:
        icon = PLAN_ICONS.get(step.get("status", ""), "•")
        line = f"{icon} {step.get('n', '')}. {step.get('title', '')}"
        if step.get("reason"):
            line += f" — _{step['reason']}_"
        lines.append(line)
    return "\n\n".join(lines)


def describe_event(event: StreamEvent) -> str | None:
    """One progress line for the log, or None for events shown elsewhere."""
    data = event.data
    if event.type == "phase":
        return f"**{data.get('text', data.get('phase', ''))}**"
    if event.type == "tool.started":
        return f"▶️ {data.get('label', '')}"
    if event.type == "tool.finished":
        icon = TOOL_ICONS.get(data.get("outcome", ""), "•")
        line = f"{icon} {data.get('label', '')} ({data.get('elapsed_s', 0):.1f} с)"
        detail = data.get("summary") or data.get("text")
        return f"{line} — {detail}" if detail else line
    if event.type == "summary":
        return f"📋 {data.get('text', '')}"
    return None


def render_progress(progress: list[str], plan: str | None) -> None:
    if plan:
        st.markdown("**План**")
        st.markdown(plan)
    for line in progress:
        st.markdown(line)


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("progress") or message.get("plan"):
            with st.expander("Ход выполнения"):
                render_progress(message.get("progress", []), message.get("plan"))
        if message.get("error"):
            st.error(message["content"])
        else:
            st.markdown(message["content"])

prompt = st.chat_input("Задайте вопрос по загруженному файлу...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        progress: list[str] = []
        plan: str | None = None
        reply: str | None = None
        is_error = False

        status = st.status("Агент думает...", expanded=True)
        with status:
            plan_box = st.empty()
            log_box = st.container()
        try:
            for event in stream_agent(
                settings,
                message=prompt,
                client_id=settings.client_id,
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
            ):
                if event.type == "plan":
                    plan = format_plan(event.data.get("steps", []))
                    with plan_box.container():
                        st.markdown("**План**")
                        st.markdown(plan)
                elif event.type == "answer":
                    reply = event.data.get("text", "")
                    note = OUTCOME_NOTES.get(event.data.get("outcome", ""))
                    status.update(
                        label=note or "Готово", state="complete", expanded=False
                    )
                elif event.type == "error":
                    reply = f"Ошибка агента: {event.data.get('text', '')}"
                    is_error = True
                    status.update(label="Ошибка", state="error", expanded=False)
                else:
                    line = describe_event(event)
                    if line:
                        progress.append(line)
                        log_box.markdown(line)
                        if event.type == "phase":
                            status.update(label=event.data.get("text", "Агент думает..."))
        except BackendError as exc:
            reply = f"Ошибка агента ({exc.status_code}): {exc.message}"
            is_error = True
        except Exception as exc:  # noqa: BLE001
            reply = f"Не удалось связаться с бэкендом: {exc}"
            is_error = True

        if is_error:
            status.update(label="Ошибка", state="error", expanded=False)
            st.error(reply)
        else:
            st.markdown(reply or "Агент вернул пустой ответ.")
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply or "Агент вернул пустой ответ.",
                "progress": progress,
                "plan": plan,
                "error": is_error,
            }
        )
