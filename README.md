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
| `BACKEND_INVOKE_PATH` | `/api/v1/invoke-agent` | Chat/agent endpoint |
| `BACKEND_CLIENT_ID` | `CI00000000` | Value sent as `x-client-id` |
| `BACKEND_REQUEST_TIMEOUT` | `60` | Request timeout (seconds) |
