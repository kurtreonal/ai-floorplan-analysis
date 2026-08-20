# VED Electrical Services API

This directory contains the minimal FastAPI foundation for the VED Electrical Services API. The health endpoint is an application-liveness check only; it does not check a database, model, or storage service.

## Requirements

- Python 3.13.7

## Setup

From `backend/` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The application optionally reads `.env` from the repository root. Process environment variables take precedence over values in that file. The `.env` file is not required and must not be committed. If it is created from `.env.example`, replace placeholder values before use.

The A4 foundation does not require authentication configuration at startup. OAuth 2.0 and OpenID Connect will be configured in their dedicated authentication ticket. Feature-specific mandatory settings will be validated when each feature is introduced.

## Run

Start Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Stop the local server with `Ctrl+C`.

## Health endpoint

Request:

```http
GET /health
```

Successful response (`200 OK`):

```json
{
  "status": "ok",
  "service": "VED Electrical Services API"
}
```

Interactive OpenAPI documentation is available at `/docs` while the local server is running.
