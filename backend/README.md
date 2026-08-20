# VED Electrical Services API

This directory contains the minimal FastAPI foundation for the VED Electrical Services API. The health endpoint is an application-liveness check only; it does not check a database, model, or storage service.

## Requirements

- Python 3.13.7
- A required `JWT_SECRET` supplied through the process environment or an ignored root `.env` file

## Setup

From `backend/` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The application optionally reads `.env` from the repository root. Process environment variables take precedence over values in that file. The `.env` file is not required and must not be committed. If it is created from `.env.example`, replace placeholder values before use.

## Run

Set the required secret for the current PowerShell process, then start Uvicorn:

```powershell
$env:JWT_SECRET="replace-with-a-local-secret"
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
