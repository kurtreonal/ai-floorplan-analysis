# VED Electrical Services API

This directory contains the minimal FastAPI foundation for the VED Electrical Services API. The health endpoint is an application-liveness check only; it does not check a database, model, or storage service.

## Requirements

- Python 3.13.7
- XAMPP with its MySQL-compatible server running for local database work

## Setup

From `backend/` on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The application optionally reads `.env` from the repository root. Process environment variables take precedence over values in that file. The `.env` file is not required and must not be committed. If it is created from `.env.example`, replace placeholder values before use.

The A4 foundation does not require authentication configuration at startup. OAuth 2.0 and OpenID Connect will be configured in their dedicated authentication ticket. Feature-specific mandatory settings will be validated when each feature is introduced.

## XAMPP database setup

XAMPP is a local-development convenience. FastAPI connects directly to the MySQL-compatible server through SQLAlchemy and PyMySQL; it does not connect through phpMyAdmin. Apache and PHP are not required by FastAPI.

1. Open the XAMPP Control Panel and start MySQL.
2. Create the `ved_electrical` database manually if it does not exist. phpMyAdmin may be used to create or inspect it.
3. Create an ignored `.env` file in the repository root.
4. Configure `DATABASE_URL` in that file using the `mysql+pymysql` driver. Use `.env.example` as the public template, and keep real credentials only in `.env`.
5. From `backend/`, install the requirements:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

6. Verify database connectivity explicitly:

   ```powershell
   .\.venv\Scripts\python.exe -c "from app.core.database import verify_database_connection; verify_database_connection(); print('Database connection verified.')"
   ```

7. Start FastAPI separately using the command in the next section.

The database connection is initialized lazily, so importing or starting FastAPI does not contact MySQL. The `/health` endpoint remains an application-liveness check only.

B1 provides connectivity and session management only. It does not create tables, run `create_all()`, or include migration tooling.

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
