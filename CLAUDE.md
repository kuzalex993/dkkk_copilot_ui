# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Streamlit front end for the Copilot backend (`aigw-rest-service`, the sibling repo at
`../dkkk_copilot` — FastAPI + LangGraph agents doing Excel cashflow-model analysis). The user uploads an
Excel file, then chats with the agent about it. Python 3.13, managed with `uv`. User-facing strings are in
Russian; keep new UI text consistent with that.

## Commands

```sh
cp .env.example .env          # backend URL/paths/client id/timeout; .env is gitignored
uv sync
uv run streamlit run src/dkkk_copilot_ui/app.py
```

There are no tests and no lint/type-check config or dev dependencies in `pyproject.toml` (ruff/mypy have
been run ad hoc, e.g. `uvx ruff check src` / `uvx mypy src`). The `dkkk-copilot-ui` console script points
at a placeholder `main()` in `__init__.py` — it does not launch the app; use `streamlit run`.

## Architecture

Three modules under `src/dkkk_copilot_ui/`:

- `config.py` — `load_dotenv()` at import time; `get_settings()` returns a frozen `Settings` with
  `upload_url` / `stream_url` built from `BACKEND_HOST` + paths. Empty env values fall back to defaults.
- `backend_client.py` — stateless `requests` wrapper. Every call sends the backend's required headers:
  `x-trace-id` (fresh UUID per request), `x-request-time`, `x-client-id`, `x-session-id`, `x-user-id`.
  Non-2xx responses become `BackendError(status_code, message)`, with the message taken from the JSON
  body's `error_description` or `detail` when present.
  - `upload_file` → `POST` multipart `file`; expects JSON `{content, filename, save_dir}`.
  - `stream_agent` → `POST` JSON `{"message": ...}` to the SSE endpoint (`/api/v1/invoke-agent/stream`),
    yields `StreamEvent(type, data)` (`turn.started`, `phase`, `plan`, `tool.started`, `tool.finished`,
    `summary`) until the terminal `answer` or `error`; `: ping` heartbeats are skipped.
- `app.py` — the Streamlit script (re-executed top to bottom on every interaction). All state lives in
  `st.session_state`: `session_id` (UUID, fixed per browser session), `user_id` (8-char, editable in the
  sidebar), `messages` (chat history; assistant entries keep their progress log and plan for the «Ход выполнения» expander),
  `uploaded_filename`. "Новый диалог" clears messages and the uploaded filename but keeps `session_id`.

The backend keys the uploaded file and the conversation history by these ids (`user_id` is the namespace
for both), so the upload and subsequent chat calls must use the same `session_id`/`user_id`. When changing
the request/response contract, check the backend's API in `../dkkk_copilot` (`openapi_copilot.yaml`,
`openapi.json`) rather than guessing.
