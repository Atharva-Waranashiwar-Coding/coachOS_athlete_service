# CoachOS Athlete Service

Standalone FastAPI service for athlete profiles, coach-athlete relationships, goals, reusable drills, athlete drill assignments, and athlete timeline records.

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
- Private coach drill library records
- Athlete drill assignments and assignment activity

This service does not own:

- Authentication signup or login
- Passwords
- JWT issuance
- Video files
- AI reviews
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

Drill library:

- `POST|GET /api/v1/drills`
- `GET|PATCH|DELETE /api/v1/drills/{drill_id}`
- `POST /api/v1/drills/{drill_id}/restore`

Drill assignments:

- `POST|GET /api/v1/athletes/{athlete_id}/drill-assignments`
- `GET|PATCH /api/v1/athletes/{athlete_id}/drill-assignments/{assignment_id}`
- `POST .../{assignment_id}/start`
- `POST .../{assignment_id}/complete`
- `POST .../{assignment_id}/cancel`

Athlete account access:

- `POST|GET /api/v1/athletes/{athlete_id}/invite`
- `POST /api/v1/athletes/{athlete_id}/invite/resend`
- `POST /api/v1/athletes/{athlete_id}/access/disable`
- `POST /internal/v1/athlete-user-links/{auth_user_id}/activate`

Athlete self-service:

- `GET /api/v1/athlete/me`
- `GET /api/v1/athlete/dashboard`
- `GET /api/v1/athlete/timeline`
- `GET /api/v1/athlete/goals`
- `GET /api/v1/athlete/drill-assignments`
- `GET /api/v1/athlete/drill-assignments/{assignment_id}`
- `POST .../{assignment_id}/start`
- `POST .../{assignment_id}/progress`
- `POST .../{assignment_id}/complete`

Coach progress insights:

- `GET /api/v1/athletes/{athlete_id}/insights`
- `GET /api/v1/coach/insights`
- `GET /api/v1/coach/insights/athletes-needing-attention`

## Authentication Expectations

The Auth Service issues JWT access tokens. The Athlete Service validates bearer tokens locally using the shared `JWT_SECRET_KEY` during MVP.

Expected token claims:

- `sub`: Auth Service user UUID
- `email`: authenticated user's email
- `role`: authenticated user's role
- `exp`: token expiration

For transition compatibility, the validator also accepts `user_id` when `sub` is absent.

Coach endpoints require `role=coach`. Athlete self endpoints require `role=athlete`, resolve an active `AthleteUserLink` from JWT `sub`, and never accept an athlete ID as identity input. Missing, disabled, or archived links return a safe not-found response.

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
- `AI_REVIEW_SERVICE_URL`
- `UPSTREAM_TIMEOUT_SECONDS`
- `MAX_DRILL_TITLE_CHARACTERS`
- `MAX_DRILL_DESCRIPTION_CHARACTERS`
- `MAX_DRILL_INSTRUCTIONS_CHARACTERS`
- `MAX_COACH_NOTES_CHARACTERS`
- `MAX_DRILL_TAGS`
- `MAX_DRILL_EQUIPMENT_ITEMS`
- `DEFAULT_DRILL_ASSIGNMENT_PAGE_SIZE`
- `AUTH_SERVICE_INTERNAL_URL`
- `INTERNAL_SERVICE_NAME`
- `INTERNAL_SERVICE_TOKEN`
- `ATHLETE_DASHBOARD_RECENT_ITEMS_LIMIT`
- `ATHLETE_ACCOUNT_LINK_REQUIRED`
- `MAX_ATHLETE_NOTE_CHARACTERS`
- `AI_REVIEW_SERVICE_INTERNAL_URL`
- `MEDIA_SERVICE_INTERNAL_URL`
- `INSIGHT_DEFAULT_RANGE_DAYS`
- `INSIGHT_MAX_RANGE_DAYS`
- `INSIGHT_TREND_MIN_SAMPLE_SIZE`
- `INSIGHT_TREND_THRESHOLD_PERCENTAGE_POINTS`
- `INSIGHT_RECURRING_AREA_MIN_REVIEWS`
- `INSIGHT_LOW_ACTIVITY_DAYS`
- `INSIGHT_INCOMPLETE_ASSIGNMENT_THRESHOLD`
- `INSIGHT_REPEATED_AREA_REVIEW_THRESHOLD`
- `INSIGHT_REPEATED_AREA_WINDOW_DAYS`
- `INSIGHT_GOAL_DUE_SOON_DAYS`
- `INSIGHT_NO_FEEDBACK_DAYS`
- `INSIGHT_UPSTREAM_TIMEOUT_SECONDS`
- `INSIGHT_MAX_BATCH_ATHLETES`

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
- `drills`
- `drill_assignments`
- `drill_assignment_activities`
- `athlete_user_links`

Relationships:

- A coach relationship references an external Auth Service user UUID and a local athlete.
- A goal belongs to an athlete.
- A timeline event belongs to an athlete.
- Secondary positions are normalized child rows for each athlete.

## Current Limitations

- Uses shared-secret JWT validation for MVP.
- No media, AI review, or workout-plan ownership in this service.
- Tests require an available PostgreSQL database.

## Future Service Integrations

- Media Service can create timeline events for video uploads through an internal interface.
- AI Review Service can create timeline events for review generation and coach approval.
- A dedicated Drill Service may be extracted when independent scaling, marketplace ownership, or separate deployment requirements justify it.
- Auth Service can move JWT verification to asymmetric public-key validation without changing endpoint code.

## Unified Timeline

Athlete Service owns canonical timeline records. Internal producers call `POST /internal/v1/athletes/{athlete_id}/timeline-events` using `X-Service-Name` and `X-Service-Token`. Stable external event IDs make identical retries return the existing row and changed-payload reuse return `409`. Public coach queries filter by category, type, source, visibility, and date range.

Configure `INTERNAL_API_PREFIX` and JSON `INTERNAL_SERVICE_TOKENS`, then run `alembic upgrade head`.

## Drill Assignment Architecture

Drills are reusable coach-owned definitions. AI recommendations remain immutable advisory content in AI Review Service. Assignments are athlete-specific execution records with source snapshots, dates, targets, progress, private notes, and lifecycle state.

Creation modes are `library`, `review`, and `custom`. Review mode fetches `GET /api/v1/reviews/{review_id}/approved` with the current coach JWT and never trusts recommendation text from the browser. A recommendation may be assigned directly, saved as a new private drill, or mapped to an accessible existing drill. No recommendation is assigned automatically.

Allowed transitions are `assigned -> in_progress|completed|cancelled` and `in_progress -> completed|cancelled`. Completed and cancelled states are terminal. Progress above zero moves an assigned record to `in_progress`; completion uses the dedicated endpoint and sets progress to 100.

`drill_assigned`, `drill_started`, and `drill_completed` are athlete-visible timeline events. `drill_cancelled` is coach-only by default. Timeline metadata excludes coach notes, completion notes, cancellation reasons, full instructions, and AI rationale.

Migration:

```bash
alembic upgrade 20260716_0003
alembic downgrade 20260710_0002
```

## Athlete Identity And Dashboard

`athlete_user_links` is the explicit boundary between an external Auth Service user and a local athlete profile. Partial unique indexes permit only one invited or active link per athlete and per Auth user. Disabled links remain historical records.

Only an active link can resolve `/api/v1/athlete/*`. Athlete response schemas omit injury notes, general coach notes, relationship internals, coach IDs, coach notes, cancellation reasons, and internal source references. Timeline queries force `athlete_visible` in the service and apply a metadata allowlist.

Dashboard status is deterministic:

- `needs_attention`: one or more active assignments are overdue
- `on_track`: active assignments exist and none are overdue
- `getting_started`: a recently activated account has no active or completed work
- `no_current_assignments`: no assigned or in-progress work

The dashboard synchronously requests a minimal approved-feedback summary from AI Review Service with a bounded timeout. Failure returns `partial_data: true` and does not fail local drill, goal, or timeline data.

Athletes may start assigned drills, submit non-decreasing progress from 0 through 99, and complete assigned or in-progress drills with explicit confirmation. They cannot create, edit, assign, cancel, or change definitions and dates. Athlete notes are stored on assignment activity for coach visibility and are never copied into timeline metadata.

Stage 9 migration:

```bash
alembic upgrade 20260716_0004
```

## Coach Progress Insights

Athlete Service is the Stage 10 aggregation owner. It combines authoritative local drill, goal, assignment activity, and timeline records with safe approved-review and practice-activity summaries from AI Review and Media. It never reads another service's database and never makes one upstream request per athlete.

Time ranges support `7d`, `30d`, `60d`, `90d`, and bounded custom dates. Day boundaries are resolved in the requested IANA timezone and converted to start-inclusive, end-exclusive UTC timestamps. The comparison period has the same duration immediately before the current period.

Metric definitions:

- Drill completion rate: completed non-cancelled assignments divided by non-cancelled assignments created before period end.
- On-time completion rate: qualifying due-dated completions completed by due-date end of day.
- Goal completion rate: completed non-cancelled goals divided by non-cancelled goals created before period end.
- Empty denominators and unavailable upstream ratios return `null`, not zero.
- Trends require the configured minimum sample in both periods and compare percentage-point change against the configured threshold.
- Recurring feedback counts a normalized area at most once per approved review.

Normalization prefers a valid `taxonomy_code`, then `app/core/insight_aliases.v1.json`, then a conservative lowercased title. The API describes changes in approved-feedback mentions and does not infer objective skill improvement.

Attention flags are deterministic: overdue drills, multiple incomplete assignments, limited recent activity, repeated high-priority approved feedback, goals due soon, overdue goals, and recent practice without recent approved feedback. Rules requiring unavailable review or media data are suppressed.

If AI Review or Media times out, local insights still return with `partial: true`, service availability booleans, and safe warning codes. Database migration `20260716_0005` adds composite indexes for assignment due/completion, goal target/completion, and timeline visibility/occurrence queries. No Redis, analytics snapshot table, athlete ranking, prediction, or opaque score is used.

Stage 10 quality:

```bash
black --check app tests alembic
ruff check app tests alembic
mypy app
pytest -q
```
