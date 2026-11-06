# dkkk-copilot-ui

Streamlit UI for the Copilot chat bot backend: upload an Excel file and chat with the
agent about it.

## Setup

```bash
cp .env.example .env   # adjust BACKEND_HOST / paths if needed
uv sync
```

## Run

```bash
uv run streamlit run src/dkkk_copilot_ui/app.py
```

## Configuration

All backend connection settings are read from `.env` (see `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `BACKEND_HOST` | `http://localhost:8080` | Base URL of the backend service |
| `BACKEND_UPLOAD_PATH` | `/api/v1/upload` | Excel upload endpoint |
| `BACKEND_STREAM_PATH` | `/api/v1/invoke-agent/stream` | SSE chat/agent endpoint |
| `BACKEND_CLIENT_ID` | `CI00000000` | Value sent as `x-client-id` |
| `BACKEND_REQUEST_TIMEOUT` | `60` | Request timeout (seconds) |

## Clarification pauses

The chat uses SSE event names from the `event:` line. A terminal `clarification`
stops progress and displays the question. The user replies with a normal chat
message (for example, a number or option name), which is sent in a new stream
request as `{"message": "..."}`. No option buttons are displayed. The client preserves the user, session, and client IDs
and sends all required headers on every request.

While clarification is pending, workbook uploads, user changes, and chat reset
are disabled. Repeated clarifications keep the conversation paused. An `answer`,
including `outcome: "clarify"`, completes the turn; an `error` displays its text.
Assistant history retains answer outcomes and error kinds. Connection failures
keep the pending clarification available to retry.

The non-streaming ZIP endpoint has no structured clarification options and is
not used for this flow.

## Tests

```bash
uv run python -m unittest discover -s tests -v
```
