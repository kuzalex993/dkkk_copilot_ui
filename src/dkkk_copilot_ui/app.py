"""Streamlit UI for the Copilot chat bot backend."""

from __future__ import annotations

import uuid

import streamlit as st

from dkkk_copilot_ui.backend_client import BackendError, invoke_agent, upload_file
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

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("excel_bytes"):
            st.download_button(
                "Скачать Excel-файл ответа",
                data=message["excel_bytes"],
                file_name=message.get("excel_filename") or "response.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"download-{id(message)}",
            )

prompt = st.chat_input("Задайте вопрос по загруженному файлу...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"), st.spinner("Агент думает..."):
        try:
            invoke_result = invoke_agent(
                settings,
                message=prompt,
                client_id=settings.client_id,
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
            )
        except BackendError as exc:
            reply = f"Ошибка агента ({exc.status_code}): {exc.message}"
            st.error(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        except Exception as exc:  # noqa: BLE001
            reply = f"Не удалось связаться с бэкендом: {exc}"
            st.error(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            st.markdown(invoke_result.text)
            assistant_message: dict[str, str | bytes | None] = {
                "role": "assistant",
                "content": invoke_result.text,
            }
            if invoke_result.excel_bytes:
                assistant_message["excel_bytes"] = invoke_result.excel_bytes
                assistant_message["excel_filename"] = invoke_result.excel_filename
                st.download_button(
                    "Скачать Excel-файл ответа",
                    data=invoke_result.excel_bytes,
                    file_name=invoke_result.excel_filename or "response.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download-{len(st.session_state.messages)}",
                )
            st.session_state.messages.append(assistant_message)