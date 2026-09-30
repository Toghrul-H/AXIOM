# Milestone 4 verification

Verified locally on 21 September 2026 using the existing Python 3.11.9, PostgreSQL
18.6, Next.js 16.3.5 and TypeScript stack. No new dependency or secret was needed.

## Database and backend

- Preflight: revision `0002`, exactly seven original `[DEV]` bank questions (IDs 19–25).
- Applied additive Alembic `0003`, creating five quiz/attempt/snapshot tables. No reset.
- Final revision: `0003 (head)`; `alembic check`: no new upgrade operations detected.
- Original seven bank questions preserved; no new content imported.
- Seeded `[DEV] Foundations Quiz` (four questions, three objective points) and
  `[DEV] Mixed DMI Quiz` (six questions, four objective points). Both use existing
  questions; rerunning `app.seed_quizzes` created zero duplicates.
- All backend tests with `RUN_POSTGRES_TESTS=1`: **46 passed**, two existing dependency
  deprecation warnings. All previous Question Bank and migration tests were included.

New tests cover composition, ordering/points, availability, all four response types,
answer replacement/clearing, real PostgreSQL persistence, objective results, unanswered
questions, ungraded written responses, wrong-session access, invalid IDs/shapes,
pre-submit review denial, active-response field allowlists, no-store headers, closed
attempt immutability and concurrent idempotent submission. Snapshot tests change source
text, answers, options and explanations and delete a source question, confirming the
completed review is unchanged. A source Boolean answer is also edited during an active
attempt to verify grading uses its start-time snapshot.

Integration fixtures clean up only their own rows. Legacy migration still runs in its
own disposable PostgreSQL schema. Existing student/browser attempt data is not cleared.

## Browser verification

Used the real Next.js frontend and FastAPI/PostgreSQL backend through the in-app browser.

1. Student Dashboard leads to Quizzes; student navigation contains no Question Bank.
2. Both development quizzes appear with question counts and objective points.
3. Foundations quiz: selected True, navigated forward/back, changed to False, saved,
   refreshed and observed False still selected.
4. Selected only one correct element in the multi-select question (deliberately incomplete),
   entered a written response and left the final objective question unanswered.
5. Finish confirmation correctly reported one unanswered question. Continue Quiz returned
   to editing; Finish Anyway submitted the entire attempt.
6. Results: **1/3 objective points**, one correct, two incorrect including one unanswered,
   one written response explicitly ungraded.
7. Review showed all four questions: explanation for the correct answer, explanation for
   the incorrect answer, reference/solution for the written response, and correct answer/
   explanation for the unanswered objective question.
8. Reloaded completed review and reopened results from attempt history successfully.
9. Mixed quiz: answered true/false, exact multi-select and single-choice questions; left
   through Back to quizzes and resumed, confirming the selected single choice remained.
   Finished with all four objectives correct: **4/4 objective points**, two ungraded
   written responses. No misleading overall percentage was displayed.
10. A third development attempt verifies immediate sidebar navigation saves dirty text
    before leaving. With the updated client reloaded, resuming recovered the latest text.
    That attempt remains in progress to demonstrate resume during manual inspection.
11. Teacher quiz management: created a disposable two-question quiz, reversed order,
    changed points to three, activated, removed a question and deactivated. Verified
    composition/status directly in PostgreSQL, then removed only that disposable quiz.
12. Teacher Question Bank: created a disposable question, edited its explanation and
    deleted it through confirmation. Original seven questions remained. Demonstrator
    view opens the shared Question Bank; role switch is labelled development-only.

The active quiz never displayed correctness or reference/solution content. Backend
response-schema tests verify those fields are absent from active payloads, not merely
hidden with CSS. Browser-created completed attempts were independently queried in
PostgreSQL, confirming their status, scores and snapshot/answer rows.

## Frontend validation

ESLint and TypeScript `--noEmit` passed. Prettier format check and the Next.js production
build passed for all existing and new routes. Browser preview remains available at
`http://127.0.0.1:3000/student/quizzes` for manual testing.

## Changed files

Backend additions:

- `app/quiz_models.py`, `app/quiz_schemas.py`
- `app/routers/quizzes.py`, `app/services/quizzes.py`
- `app/seed_quizzes.py`, `tests/test_quizzes.py`
- `alembic/versions/0003_quiz_composition_and_attempt_snapshots.py`

Backend updates: `app/main.py` (router/cache policy), `app/services/grading.py` (shared
snapshot interface), `alembic/env.py` (metadata registration), `tests/test_postgres.py`
(head revision), `README.md`.

Frontend additions:

- `src/lib/quizzes.ts`
- `src/components/quiz-list.tsx`, `take-quiz.tsx`, `quiz-results.tsx`, `quiz-manager.tsx`
- Student quiz list/attempt/results/review pages, teacher quiz management page,
  demonstrator page and `src/app/quizzes.css`

Frontend updates: `next.config.ts` (same-origin proxy paths), `src/app/layout.tsx`,
`src/app/globals.css`, `src/app/student/[section]/page.tsx`, `src/components/app-shell.tsx`,
`src/components/student-dashboard.tsx`, `README.md`. Root README and these Milestone 4
architecture/verification documents were also updated.

## Warnings and scope limits

- Existing Starlette HTTPX/AnyIO deprecation warnings and ESLint 9 deprecation remain;
  functional checks pass. No unrelated dependency upgrade was introduced.
- Development session UUIDs and view switching are not real authentication/authorization.
  Clearing browser storage loses the local identity; database attempts remain.
- Wait for Saved before closing/reloading. No offline mode; browser-history navigation
  during the brief unsaved interval is not a full navigation-blocking/offline system.
- Question Bank deletion removes future quiz membership but preserves attempt snapshots.
- Positive integer points and full/zero-credit objective grading only.
- Student catalog currently shows at most 100 available quizzes; staff/history are paginated.
- Dashboard progress figures remain explicitly labelled pre-existing UI examples.
- No deployment, real content import, advanced progress, account system or grading workflow.

See [architecture](milestone-4-architecture.md) for API routes, identity migration plan,
snapshot decisions and startup commands. Existing startup commands are unchanged;
`alembic upgrade head` and optional `python -m app.seed_quizzes` are the new setup steps.
