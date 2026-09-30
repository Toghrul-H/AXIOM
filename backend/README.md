# Backend — authenticated course platform

Python 3.11+, PostgreSQL, FastAPI, SQLAlchemy 2, Psycopg 3, Alembic.
Run commands below from `backend/` in PowerShell.

## Setup and startup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Only if `.env` does not exist, copy `.env.example` to `.env`. Enter the local
PostgreSQL role password in `DATABASE_PASSWORD` there, or provide that process
environment variable. Never commit or share the file. Process environment variables
override `.env`; its path is resolved relative to the backend. The remaining defaults
are localhost:5432, database `dmi_platform`, role `dmi_app`. SQLAlchemy URL objects
handle password encoding. The role needs migration privileges.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
# Optional development examples, never official course material:
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Swagger: http://127.0.0.1:8000/docs. OpenAPI: `/openapi.json`.
Tables are created only through Alembic, never on application startup.
Existing startup commands are unchanged; apply all migrations through revision `0006` before using the API.

## Authentication and permissions

See the [Milestone 5 guide](../docs/milestone-5-authentication.md) for the permission
matrix, API contracts, session/CSRF behavior, environment settings and production
limitations. Public registration creates Students only. Question CRUD, answer checks
and quiz composition require Demonstrator, Lecturer or Admin. Student attempts are
private to their authenticated owner. Course metadata requires any active account.

Bootstrap the first Admin from this directory:

```powershell
.\.venv\Scripts\python.exe -m app.scripts.create_admin
```

Enter the email and password at the prompts, never in source or chat. In Swagger,
call `/auth/login` to set the cookie; use its `csrf_token` in the documented
`X-CSRF-Token` header for protected mutations. The frontend handles this automatically.

## API

| Endpoint | Behavior |
| --- | --- |
| `GET /` | Existing greeting, unchanged |
| `GET /question-metadata` | Ordered topics, response types, skills, problem sets, suitability tags |
| `POST /questions` | Create; 201 plus Location header |
| `GET /questions` | `{items, total, offset, limit}`; ascending ID order |
| `GET /questions/{id}` | Retrieve; 404 if missing |
| `PATCH /questions/{id}` | Validated partial update; 404 if missing |
| `DELETE /questions/{id}` | 204; 404 if missing |
| `POST /questions/{id}/check` | Stateless objective answer check and reference solution; no attempts or scores |

This deliberately replaces the previous free-text topic / `question_type` /
`correct_answer` contract. Read responses include a topic object with its parent,
ordered option objects, problem-set objects, suitability objects, and timestamps.
The frontend was migrated together with the backend.

Get IDs from `/question-metadata`. Example FREE_RESPONSE body (topic 6 is the
seeded Sets topic):

```json
{
  "topic_id": 6,
  "title": "Set cardinality",
  "difficulty": "easy",
  "response_type": "FREE_RESPONSE",
  "skill_type": "CALCULATION",
  "question_text": "Find the cardinality of {a, b, c}.",
  "expected_answer": "3",
  "explanation": "The set has three distinct elements.",
  "is_active": true,
  "problem_set_ids": [],
  "assessment_suitability_codes": ["GENERAL_PRACTICE"]
}
```

For SINGLE_CHOICE or MULTIPLE_SELECT, omit `expected_answer` and use:

```json
"options": [
  {"text": "3", "is_correct": true},
  {"text": "4", "is_correct": false}
]
```

Choice questions require 2–20 distinct nonempty options: exactly one correct for
single choice, at least one for multiple select. For TRUE_FALSE use
`correct_boolean: true` or `false`, with no options or expected answer.
FREE_RESPONSE always stores a reference answer and is never automatically graded.
Skills are independent of response types. Difficulty is `easy`, `medium`, or `hard`.
Title is optional (200 characters); question/answer/explanation text is trimmed and
limited to 20,000 characters. Explanation is optional. Booleans must be JSON booleans.

PATCH omission preserves a field. An association/option array replaces that collection;
`[]` clears associations. Preserve option IDs to retain their identity while editing
or reordering; omit IDs for new options. Foreign option IDs are rejected. Explicit
null can clear title or explanation, and answer fields only when the resulting response
type permits it. The complete resulting question is validated before database mutation.
Invalid payloads/associations return 422; database failures return a generic 503 without
credentials or SQL parameters.

### Filters and pagination

`GET /questions` accepts `topic_id`, `problem_set_id`, `difficulty`, `response_type`,
`skill_type`, `assessment_suitability`, `is_active`, and `q` (title/question text).
Filters combine with AND, run in PostgreSQL, and affect the returned total.
Parent topics include all descendants; use `include_descendants=false` for an exact
node. Search is case-insensitive literal substring matching (including `%` and `_`).
`offset` starts at 0; `limit` defaults to 50 and is bounded to 1–100.
Unknown lookup filter values return an empty result rather than mutating metadata.

### Objective checks

POST `/questions/{id}/check` with `{"selected_option_ids":[123]}` for choices,
`{"boolean_answer":false}` for TRUE_FALSE, or `{"free_response":"..."}` for free text.
Use actual option IDs from the question response. Multiple select uses exact set
equality, with no partial score. Duplicate/foreign option IDs and mismatched answer
fields return 422. Feedback returns the correct answer and explanation for both right
and wrong submissions. FREE_RESPONSE returns `auto_gradable=false` and
`is_correct=null`. No submission is stored and no proof/AI grading is implemented.

## Tests and migration checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
$env:RUN_POSTGRES_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:RUN_POSTGRES_TESTS
.\.venv\Scripts\python.exe -m alembic check
```

Default tests skip database integration. The opt-in suite uses the configured real
PostgreSQL database, removes its own test accounts/questions/quizzes/attempts, and tests legacy migration in
an isolated temporary schema which it removes afterwards. Sequences may advance.
The role must be able to create a schema for that migration test. No SQLite fallback.

Revision `0002` preserves legacy values while normalizing relationships. It intentionally
refuses downgrade: restoring the old shape would lose multi-select and classification
data. Use a reviewed backup restore or a deliberate forward migration instead.
See [architecture](../docs/milestone-3-architecture.md) and
[verification](../docs/milestone-3-verification.md) for transformations and results.

Management responses expose answers only to authorized staff. Students use owner-scoped quiz endpoints; solutions become available after submission. Manual grading remains planned.

## Milestone 4 — student quizzes

The quiz workflow is documented in [architecture](../docs/milestone-4-architecture.md)
and [verification](../docs/milestone-4-verification.md). Run `alembic upgrade head` to
apply revision `0003`; optionally run `.\.venv\Scripts\python.exe -m app.seed_quizzes`
after the existing question seed. Server commands and database environment are unchanged.

Staff composition APIs live at `/quizzes`; student catalog and attempt APIs at
`/student/quizzes` and `/student/attempts`. Swagger describes all payloads. Milestone 5
replaces the former `X-Development-Session` UUID with authenticated User ownership;
that header no longer grants access. Sign in and supply CSRF for mutations.
Active response schemas exclude answers/solutions. Only a successful final submission
unlocks review. Attempts use immutable question/option snapshots and reuse the existing
objective checker; written responses remain ungraded. The opt-in PostgreSQL suite
now includes these quiz tests and concurrent final-submission checks.


## Milestone 4.1 — topic context

Apply `alembic upgrade head` for revision `0004`, which adds a nullable snapshot topic
slug for contextual mathematical input. Existing answers and grading are unchanged;
old snapshots retain null and use the frontend fallback. See
[Milestone 4.1](../docs/milestone-4.1-math-input.md).
