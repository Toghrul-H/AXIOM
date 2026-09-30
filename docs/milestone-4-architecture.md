# Milestone 4 — student quiz architecture

## Data model

Migration `0003_quiz_composition_and_attempt_snapshots.py` adds five tables. It changes
no existing Question Bank rows or columns and requires no database reset.

| Model/table | Purpose |
| --- | --- |
| Quiz / `quizzes` | Title, description, DRAFT/ACTIVE/INACTIVE status, creation/update timestamps |
| QuizQuestion / `quiz_questions` | Relational quiz/question association, ordered position and positive integer points |
| QuizAttempt / `quiz_attempts` | UUID, quiz reference, development session UUID, title snapshot, timestamps, IN_PROGRESS/SUBMITTED status, objective score and denominator |
| AttemptAnswer / `attempt_answers` | One question snapshot and saved answer per attempt question; source FK, order, points, prompt, response type, reference/Boolean answer, explanation, submitted fields and grading result |
| AttemptOption / `attempt_options` | Independent ordered option snapshots with their own IDs and correct flags |

Each attempt question is both
its immutable content snapshot and its mutable draft/final answer row; a separate
QuestionAttempt table would duplicate that relationship.

Quiz/question pairs and positions are unique. Points are integers from 1 to 1000;
quizzes hold at most 100 distinct questions through API validation. Referenced quiz
records cannot be deleted while attempts exist. Quiz-question membership cascades
when a bank question is deleted; attempt source references instead become null,
leaving the historical prompt, answer, solution, options and points intact. Deleting
a source question can leave an empty quiz, which is not startable. Inactive questions
make a quiz unavailable for new attempts until composition/content is fixed. Existing
attempts remain resumable and submittable from their original snapshots.

Selected snapshot-option IDs are the only JSONB field: a short validated integer
array on each answer. This stores a variable-length student selection without adding
another join entity. API validation rejects duplicate IDs, IDs from another question
or attempt, and invalid type combinations. The rest of the attempt, content snapshots,
options, score and lifecycle are relational columns/rows, not a giant JSON document.
An empty selection/null Boolean/null text represents an unanswered question; `{}`
clears an answer. Whitespace-only text is normalized to null by the UI.

## Snapshot and grading strategy

All content is copied **when the attempt starts**, including correct-answer data held
only on the server. Subsequent changes to the bank, quiz order/points or quiz title
cannot change what that attempt means. Options receive snapshot IDs; student answers
refer to those IDs, not live bank-option IDs. No general content-versioning system is
needed for this milestone.

Saves and final submission lock the parent attempt row in PostgreSQL. Grading and the
SUBMITTED transition commit in a single transaction. A save arriving after submission
returns 409. Repeating submission is idempotent and returns the original stored result.
Quiz composition edits and attempt creation lock the quiz row; creation also locks the
source questions while snapshotting them. The browser queues autosave requests to
avoid stale writes within one mounted quiz page. Separate tabs use last committed
answer semantics until submission; cross-device collaboration is outside scope.

The existing `check_answer` service now accepts a small structural interface shared
by bank questions and attempt snapshots. SINGLE_CHOICE, MULTIPLE_SELECT and TRUE_FALSE
reuse this logic. Objective questions award full points or zero, with exact set equality
for multiple select. Unanswered objective questions award zero, contribute to the
incorrect count, and also have an explicit unanswered count/status. FREE_RESPONSE
answers are saved, but correctness and points awarded remain null. They are excluded
from the objective denominator, including unanswered written responses. A fully written
quiz has no automatically gradable total and never claims a final percentage.

The results screen labels **automatically graded points** and the count of ungraded
written responses. Review shows all questions, student responses, correct/reference
answers and full explanations for correct, incorrect, unanswered and ungraded entries.
No manual, proof, AI or partial-credit grading was implemented.

## API and answer separation

| Method/path | Use |
| --- | --- |
| GET /quizzes | Paginated staff quiz compositions |
| POST /quizzes | Create a quiz (201) |
| GET /quizzes/{quiz_id} | Staff composition detail |
| PUT /quizzes/{quiz_id} | Replace editable composition, order, points and availability |
| GET /student/quizzes | Available quiz summaries only |
| POST /student/quizzes/{quiz_id}/attempts | Create a persisted snapshot attempt (201) |
| GET /student/attempts | Current development session's paginated history |
| GET /student/attempts/{attempt_id} | Resume; sanitized question and saved-answer data |
| PUT /student/attempts/{attempt_id}/answers/{item_id} | Replace/clear one draft answer |
| POST /student/attempts/{attempt_id}/submit | Finalize atomically and return results/review |
| GET /student/attempts/{attempt_id}/review | Review only after submission; otherwise 409 |

List APIs accept bounded `limit` (1–100) and `offset` (0+). Staff and history UIs have
page controls. The student available-quiz catalog currently requests the first 100
quizzes, sufficient for these two development quizzes; add catalog paging before
publishing a larger collection. IDs are positive integers except attempt/session UUIDs.
Invalid shapes return 422, missing or other-session attempts 404, unavailable quizzes
or closed-attempt mutations 409. Existing SQLAlchemy failures still return a generic
503 with no credentials or SQL parameters. Swagger remains at `/docs`.

Active payloads use explicit Pydantic response allowlists. They do not contain correct
option flags, reference answers, correct Boolean answers, explanations or correctness results.
Only submitted-review schemas include those fields. Merely hiding content in React
would not satisfy this boundary. Active schemas remain sanitized even if their attempt
has subsequently been submitted. Student API responses use `Cache-Control: no-store`.
The management bank/check APIs remain available for staff development, so this is
application/data-flow separation, **not an anti-cheating or authorization guarantee**.

## Temporary identity and future authentication

On first client API use, the browser creates a random UUID and stores it under
`dmi-development-session` in localStorage. Student attempt APIs require it as
`X-Development-Session`, validate it as a UUID and scope lookups/history to it.
The local value contains no answers or password. Clearing site data/private-session
closure or using another origin/browser loses the UI's reference to those attempts;
it does not delete the PostgreSQL rows. Anyone who can supply an identity can act as
that identity; staff routes are also unauthenticated. Do not expose this local preview
as a production system. No fabricated accounts or passwords were created.

When authentication is implemented, add a real user foreign key to QuizAttempt and
populate ownership from the authenticated server-side principal. Replace client-supplied
identity scoping, define a deliberate migration/claim policy for development attempts,
protect every staff API (including existing Question Bank/check routes), enforce actual
roles and protect session transport appropriately. Attempt/answer/snapshot relationships
and grading need not be rewritten. The Student/Teacher/Demonstrator switcher only
changes development views. Demonstrator opens the shared bank; its editing/quiz links
use the shared teacher management routes.

## Pages and persistence

- `/student` links directly to quizzes; its old sample statistics remain labelled examples.
- `/student/quizzes` lists available quizzes and this browser's previous/in-progress attempts.
- `/student/quizzes/attempts/{id}` provides all four input types, answered/unanswered
  navigation, Previous/Next, Clear, Save and Finish confirmation.
- `/student/quizzes/attempts/{id}/results` summarizes objective-only grading.
- `/student/quizzes/attempts/{id}/review` shows every answer after submission.
- `/teacher/quizzes` creates/edits quizzes, searches/paginates bank choices, adds/removes
  questions, reorders them, sets points and switches availability.
- `/demonstrator` opens shared staff Question Bank access. Student navigation has no bank.
- Legacy `/student/practice` redirects to quizzes. Learn and Progress remain placeholders.

Answers autosave after a 600ms pause. Save/Next/Previous/navigator/Finish await a save;
sidebar links also save dirty input before leaving. Save errors keep the current answer
visible and prevent quiz submission/navigation through these controls. A native unload
warning protects unsaved refresh/tab closure; users should wait for “Saved.” Refresh
loads persisted answers and returns to the first question; navigator shows saved states.
No offline mode or sophisticated synchronization is claimed. Completed attempt URLs
reopen read-only results, and server-side writes are rejected after submission.

The documented learning-only feedback notice is now shown with results/review.
Two idempotently seeded `[DEV]` quizzes reuse the original seven development questions;
no official course material was imported. No authentication, advanced progress, exam
builder, manual review, AI, LaTeX or deployment features were added.

## Startup

Existing server commands remain unchanged. From `backend/`, apply the additive migration
and optionally create development quizzes:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed_quizzes
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

From `frontend/`, run `pnpm dev`. Existing local environment files still apply; no new
secret or password is required. Fresh databases need `python -m app.seed` before the
quiz seed. Downgrading `0003` explicitly drops quiz/attempt data; do not use it to undo
content changes. It leaves the previous Question Bank schema in place.

