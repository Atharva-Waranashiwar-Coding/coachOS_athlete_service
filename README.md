# CoachOS Athlete Service

Athlete profile, relationship, and timeline service for CoachOS.

## Responsibilities

- Athlete CRUD
- Athlete profile fields
- Coach-athlete relationship
- Goals and development notes
- Position and sport context
- Injury notes
- Athlete timeline events

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker

## Project Structure

- `app/api`: API route modules
- `app/core`: configuration
- `app/db`: database connection and session setup
- `app/models`: database models
- `app/schemas`: request and response schemas
- `app/services`: athlete business logic
- `app/utils`: shared utilities
- `alembic`: database migrations
- `tests`: service tests

## Environment

Copy `.env.example` to `.env` for local development. Do not commit `.env`.

Required values:

- `APP_NAME`
- `ENVIRONMENT`
- `DATABASE_URL`

## Running Locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The service exposes:

- Local app: `http://localhost:8000`
- Docker Compose port: `http://localhost:8002`
- Health check: `GET /health`

## Docker

```bash
docker compose up --build
```

## Planned API

- `GET /athletes`
- `POST /athletes`
- `GET /athletes/{athlete_id}`
- `PATCH /athletes/{athlete_id}`
- `DELETE /athletes/{athlete_id}`
- `GET /athletes/{athlete_id}/timeline`

## Testing

```bash
pytest
```

## Status

Stage 0: service skeleton created. Athlete models, relationship logic, timeline endpoints, and tests are next.
