# CoachOS Athlete Service

Standalone FastAPI service for athlete profiles, coach-athlete relationships, goals, and athlete timeline records.

## Service Purpose

The Athlete Service owns athlete development data after authentication has already happened in the Auth Service. It validates JWT bearer tokens locally, derives coach identity from token claims, and never stores passwords or authentication credentials.

## Architecture

The service follows a clean, layered structure:

- `app/api/v1/endpoints`: FastAPI route handlers
- `app/dependencies`: authentication and access-control dependencies
- `app/services`: domain use cases and transaction boundaries
- `app/repositories`: SQLAlchemy query code
- `app/models`: SQLAlchemy ORM models and enums
- `app/schemas`: Pydantic request and response models
- `app/core`: configuration, security, logging, and exception handling
- `app/db`: database engine, session, and metadata
- `alembic`: database migrations
- `tests`: PostgreSQL integration tests

Endpoint handlers stay thin. Business rules live in services, and SQL queries live in repositories.

## Owned Data

This service owns:

- Athlete profiles
- Coach-athlete relationships
- Athlete goals
- Athlete timeline records

This service does not own:

- Authentication signup or login
- Passwords
- JWT issuance
- Video files
- AI reviews
- Drills
- Workout records
- Cross-service database joins

## API Endpoint Summary

Health:

- `GET /health/live`
- `GET /health/ready`
- `GET /health`

Athletes:

- `POST /api/v1/athletes`
- `GET /api/v1/athletes`
- `GET /api/v1/athletes/{athlete_id}`
- `PATCH /api/v1/athletes/{athlete_id}`
- `DELETE /api/v1/athletes/{athlete_id}`
- `POST /api/v1/athletes/{athlete_id}/restore`

Goals:

- `POST /api/v1/athletes/{athlete_id}/goals`
- `GET /api/v1/athletes/{athlete_id}/goals`
- `GET /api/v1/athletes/{athlete_id}/goals/{goal_id}`
- `PATCH /api/v1/athletes/{athlete_id}/goals/{goal_id}`
- `DELETE /api/v1/athletes/{athlete_id}/goals/{goal_id}`

Timeline:

- `GET /api/v1/athletes/{athlete_id}/timeline`

## Authentication Expectations

The Auth Service issues JWT access tokens. The Athlete Service validates bearer tokens locally using the shared `JWT_SECRET_KEY` during MVP.

Expected token claims:

- `sub`: Auth Service user UUID
- `email`: authenticated user's email
- `role`: authenticated user's role
- `exp`: token expiration

For transition compatibility, the validator also accepts `user_id` when `sub` is absent.

Only `role=coach` can access MVP endpoints. Athlete resources return `404` when they are missing or not accessible to the current coach.

## Environment Setup

Copy `.env.example` to `.env` for local development. Do not commit `.env`.

Required variables:

- `APP_NAME`
- `APP_ENV`
- `API_V1_PREFIX`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `LOG_LEVEL`
- `CORS_ORIGINS`
- `DEFAULT_PAGE_SIZE`
- `MAX_PAGE_SIZE`

Validation range variables:

- `GRADUATION_YEAR_MIN`
- `GRADUATION_YEAR_MAX`

## Local Startup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

OpenAPI docs:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Alembic Migration Commands

```bash
alembic upgrade head
alembic downgrade -1
alembic current
```

## Docker Startup

```bash
docker compose up --build
```

The service is exposed at:

- `http://localhost:8002`

The included Compose file starts a local PostgreSQL container on host port `5433`.

## Test Commands

Tests are PostgreSQL integration tests and require `TEST_DATABASE_URL`.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/coachos_athlete_test
pytest
```

Quality commands:

```bash
ruff check .
black --check .
mypy app
```

## Database Tables

- `athletes`
- `athlete_secondary_positions`
- `coach_athlete_relationships`
- `athlete_goals`
- `timeline_events`

Relationships:

- A coach relationship references an external Auth Service user UUID and a local athlete.
- A goal belongs to an athlete.
- A timeline event belongs to an athlete.
- Secondary positions are normalized child rows for each athlete.

## Current Limitations

- Uses shared-secret JWT validation for MVP.
- No public endpoint exists for cross-service timeline event creation yet.
- No athlete portal login.
- No media, AI review, drill, or workout ownership in this service.
- Tests require an available PostgreSQL database.

## Future Service Integrations

- Media Service can create timeline events for video uploads through an internal interface.
- AI Review Service can create timeline events for review generation and coach approval.
- Drill Service can link assignments into athlete timelines later.
- Auth Service can move JWT verification to asymmetric public-key validation without changing endpoint code.
