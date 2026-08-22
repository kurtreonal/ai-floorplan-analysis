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

FastAPI startup does not require authentication configuration. C1 defines provider-neutral OAuth 2.0/OpenID Connect settings, but validates them only when the authentication feature requests its configuration. This keeps `/health` available during local setup while making incomplete or placeholder authentication configuration fail clearly before an OAuth flow starts.

The authentication configuration uses `OAUTH_PROVIDER`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `OAUTH_DISCOVERY_URL`, `OAUTH_SCOPES`, and `SESSION_SECRET`. OIDC configuration must include the `openid` scope. Client and session secrets use Pydantic secret values so their representations remain redacted. C1 does not add OAuth routes, provider integration, or session middleware; those belong to later authentication tickets.

C2 adds `GET /api/auth/login` and `GET /api/auth/callback`. The login route redirects through the configured provider and stores temporary state and nonce data only in the signed, HttpOnly application session. The callback requires matching state, relies on Authlib's OIDC ID-token validation, and uses only the validated `userinfo.sub` claim as the provider subject. Provider access tokens, refresh tokens, ID tokens, and authorization codes are not stored in MySQL or the application session and are not logged.

After a validated callback, provider plus subject resolves the local user. An existing user's local role is preserved. A previously unseen external identity is created with the local `DESIGNER` role, which is the least-privileged current VED application role; provider claims never grant `ADMIN`. The callback stores only the local user ID in the application session and redirects to `FRONTEND_URL`. C2 does not add database tables or columns.

C3 adds `GET /api/auth/me`. It reads the local user ID from the signed application session, reloads the user and current `ADMIN` or `DESIGNER` role from MySQL, and returns only the local ID, display name, email, avatar URL, and role. Missing, malformed, or stale session identities return `401 Unauthorized`; a stale user ID is removed from the session. The endpoint does not contact the OAuth provider and does not return provider subjects, provider tokens, authorization codes, or secrets. Role-based route restrictions and logout remain deferred to later tickets.

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

## Development schema initialization

B2 provides one canonical SQLAlchemy `Base` and an explicit development-only schema initializer. Run it deliberately from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m app.core.schema
```

The command loads every model registered through `app.models` and calls `Base.metadata.create_all()` to create missing tables. It is blocked unless `APP_ENV=development`, and it does not run automatically when FastAPI starts or when `/health` is requested.

During B2 alone there are no domain models, so a successful command reports zero registered application tables and leaves the database without application tables. B3 and later model tickets will register their tables with the same canonical `Base`.

`create_all()` is not a migration system. It creates missing tables but does not reliably alter existing tables when model definitions change. A deliberate development reset/recreation may therefore be necessary while the prototype schema is experimental. Any destructive reset must be performed manually and intentionally after confirming the development target; this project does not provide an automatic reset command. No production schema-migration guarantee is provided during the prototype phase.

## OAuth user and role schema

B3 registers the `roles` and `users` models with the canonical SQLAlchemy `Base`. The user record maps an external OAuth/OIDC provider identity to a local VED role; it does not store a local password, JWT, provider token, or application session.

Create the registered development tables with the existing explicit initializer:

```powershell
.\.venv\Scripts\python.exe -m app.core.schema
```

Then seed the required local authorization roles explicitly:

```powershell
.\.venv\Scripts\python.exe -m app.core.seed
```

The seed command is development-only and idempotently ensures that `ADMIN` and `DESIGNER` exist. It does not seed users and does not run automatically during FastAPI startup or schema creation.

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
