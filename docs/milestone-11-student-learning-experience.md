# Milestone 11 — Student Learning Experience

## Scope

M11 adds student-owned topic practice while retaining the established quiz, attempt, review, manual-grading, session, CSRF, RBAC, and KaTeX paths. It does not alter the verified DMI question corpus or import any blocked questions.

## Student workflow

- The dashboard now presents a server-calculated Continue Learning action, practice/feedback totals, and links to topic practice and learning history.
- Students can choose one of the seven course topics and create a private practice session from active curated DMI questions in that topic. The service prefers questions the student has not encountered, then reuses eligible questions only when necessary.
- A practice session is an `INACTIVE`, private quiz composition owned by the student. It is not visible in staff quiz management or the public student quiz catalogue.
- The existing autosave, mathematical input, immutable question snapshot, submit, review, and manual-grading workflow is used unchanged. Reference answers and explanations remain unavailable until the attempt is submitted.
- Learning history identifies practice sessions and shows whether written responses are awaiting, partly through, or fully through staff grading.

## API

All endpoints require an active authenticated `STUDENT` session. Mutating requests use the existing CSRF header and same-origin client.

- `GET /student/learning/summary` returns Continue Learning, aggregate practice/feedback metrics, and per-topic practice state.
- `GET /student/practice/topics` returns available curated-question counts and the student's topic-level attempt and manual-grading state.
- `POST /student/practice/sessions` accepts `topic_slug` and `question_count` (1–20) and returns the existing active-attempt contract. It does not save a public course quiz.

## Data and integrity

Alembic revision `0014_private_topic_practice` adds `quizzes.is_practice` and optional `quizzes.practice_owner_id`. A database constraint prevents a normal quiz from acquiring an owner and prevents a private practice quiz from lacking one. Existing quizzes receive `is_practice = false` and remain unchanged.

All learning counts are derived from immutable `AttemptAnswer` snapshots. Free-response answers are never treated as incorrect: they remain pending until a staff member assigns a score. Existing M6 auto-graded accuracy remains authoritative for objective questions; M11 adds separate manual-grading status and points rather than fabricating an overall grade.

## Verification

- Isolated PostgreSQL tests migrate a temporary schema to `0014`, create a practice session, verify ownership isolation, confirm hidden solutions before review, submit a Hungarian-accented response, apply a manual grade, and verify aggregate topic/history state.
- Importer isolation fixtures were advanced to migration `0014` to preserve migration-regression coverage.
- Frontend checks cover the authenticated same-origin learning client, selected-topic practice navigation, and dashboard use of server-calculated Continue Learning data.

## Limitations

Practice availability deliberately includes only active curated imports with `M10A3:` provenance. A topic with no eligible question shows a neutral unavailable state. Practice selection is deterministic by question ID after prioritising unseen questions; it is not an adaptive recommendation engine. Manual grading remains staff-operated and no answer is exposed during an active attempt.
