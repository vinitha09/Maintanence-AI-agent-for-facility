# Maintenance AI

Maintenance AI is a local facility-maintenance application built with FastAPI,
PostgreSQL/pgvector, React, and Ollama. It stores organizations, facilities,
shared machine records, maintenance history, and manuals; its assistant answers
questions using hybrid retrieval over maintenance and manual content.

## Architecture

```text
React browser
    │ REST + streaming SSE
    ▼
FastAPI routes ── SQLModel ── PostgreSQL + pgvector
    │                                  ▲
    ├── PDF extraction and indexing ───┤
    ├── sentence-transformer embeddings│
    └── hybrid RAG ── Ollama           │
```

Organizations contain facilities. Each facility has independent functional
system and physical location trees. A machine belongs to one facility and may
be assigned to one node in each tree; both trees reference the same machine
record.

## Requirements and configuration

- Python 3.11 or newer
- Node.js and npm
- Docker Desktop with Linux containers
- Ollama and a locally available model

Create `.env` from `.env.example`, then configure PostgreSQL and Ollama. Keep
`.env` private; it is ignored by Git.

Start the pgvector database from the project root:

```powershell
docker compose up -d
docker compose ps
```

On backend startup, the application enables pgvector, creates missing tables,
and applies additive checks for known schema updates. Existing tables and
records are preserved; startup does not drop or reset the database. Database
changes are managed by the application's SQLAlchemy initialization code rather
than Alembic. New schema changes must add a corresponding safe, idempotent
check to that initialization code.

## Run locally

From the project root:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Generate a signing key and configure SMTP in `.env` before starting the
backend. For example, generate a key with
`python -c "import secrets; print(secrets.token_urlsafe(48))"`. Use HTTPS and
set `COOKIE_SECURE=true` outside local development.

Create the initial administrator through the interactive CLI:

```powershell
python -m backend.app.cli.create_admin
```

Open the Vite URL to sign in or register. Public user accounts must verify
their email and receive administrator approval. Administrators can generate a
shared recruiter code from User Management; anyone with that code can create a
regular USER account with full application access, without administrator
approval. Codes can be reused and expire after 7 days. Administrators can also
send email-bound invitations or invite other administrators. FastAPI's
interactive API documentation is available at `/docs`.

## Local access

Authentication uses Argon2 password hashes and a JWT held in a secure,
HttpOnly cookie. Public registration always creates a USER registration.
Verified users awaiting approval can view and edit existing records; full
application access, including AI assistance and machine registration, is
granted after administrator approval or acceptance of an administrator-issued
user invitation. A shared recruiter code is reusable by multiple people and is
not tied to an email address; accepting it creates a regular USER account,
never an administrator account. Administrator accounts are created by the CLI or
administrator invitation; there is no public administrator registration.
API route permissions are enforced by FastAPI, independently of frontend
navigation.

### Authentication API

| Endpoint | Purpose | Access |
|---|---|---|
| `POST /auth/register` | Start user registration and email verification | Public |
| `POST /auth/verify-email` | Verify email and create a pending USER account | Verification token |
| `POST /auth/user/login` | User login | Public |
| `POST /auth/admin/login` | Administrator login | Public |
| `GET /auth/me` | Return the current verified account | Verified user |
| `POST /auth/logout` | Revoke the current session | Public; clears cookie |
| `POST /auth/forgot-password` | Send a password-reset link | Public |
| `POST /auth/reset-password` | Reset password and revoke sessions | Reset token |
| `POST /auth/admin-invitations/accept` | Create an invited administrator account | Invitation token |
| `POST /auth/user-invitations/accept` | Create a full-access USER account | 7-character invitation code |
| `GET /admin/users` | List non-archived accounts | ADMIN |
| `POST /admin/users/{id}/approve` | Approve a verified user | ADMIN |
| `POST /admin/users/{id}/reject` | Reject and archive a registration | ADMIN |
| `PATCH /admin/users/{id}/status` | Suspend or reactivate an account | ADMIN |
| `DELETE /admin/users/{id}` | Soft-delete a user profile | ADMIN |
| `POST /admin/invitations` | Invite another administrator | ADMIN |
| `POST /admin/user-invitations` | Invite a USER with full access | ADMIN |

Email-bound invitations are single-use. Shared recruiter codes can be reused
by multiple users and expire after 7 days. Each user enters the code, their own
email, name, and password on the invitation page.

Organizations, facilities, and hierarchies are read-only to USER accounts and
administratively managed by ADMIN accounts. Verified users can add and edit
machines and maintenance records; only administrators can archive machines,
delete maintenance records, and manage manuals.

## Search and answer flow

PDF pages and maintenance entries are chunked and embedded with
`sentence-transformers/all-MiniLM-L6-v2` (384 dimensions). PostgreSQL stores
the embeddings, generated English full-text vectors, HNSW vector index, and GIN
full-text index. Retrieval filters chunks to the selected machine, functional
system subtree, physical location subtree, or facility; vector and full-text
results are merged with Reciprocal Rank Fusion. Ollama generates the answer as
a token stream; sources are sent after the answer.

## Database initialization

Database initialization runs during FastAPI startup. It enables PostgreSQL's
pgvector extension, creates missing tables, and adds required columns and
indexes without deleting existing records. Uploaded PDF files under
`backend/data/manuals/` are stored separately from PostgreSQL.

Configure `JWT_SECRET_KEY`, `FRONTEND_URL`, and the SMTP settings in `.env`.
`COOKIE_SECURE` must be enabled when serving the application over HTTPS.
Registration verification, password reset, and administrator invitations
require working SMTP settings.

## Code and file guide

The formal architecture guide, `BACKEND_ARCHITECTURE_GUIDE.pdf`, documents the
backend modules, model relationships, API flows, startup sequence, RAG path,
and database indexes.
