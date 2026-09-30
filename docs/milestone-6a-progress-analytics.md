# Milestone 6A — Student progress analytics

`GET /student/progress/me` requires an active STUDENT session. Identity comes exclusively from the session; no student ID parameter is used. Staff analytics are not implemented. Responses retain the application's no-store policy.

## Definitions
- `completed_quizzes`: distinct quiz IDs with submitted attempts.
- `completed_attempts`: every submitted attempt, including repeats; no best/latest selection.
- `questions_answered`: nonempty selections, a boolean (including false), or non-whitespace written text in submitted attempts.
- `auto_graded_questions`: answered objective questions with a stored non-null correctness result.
- `auto_graded_correct`: those results marked true.
- `auto_graded_accuracy`: correct / auto-graded questions × 100, rounded to two decimals; null for a zero denominator.
- In-progress attempts and unanswered questions are excluded from practice metrics. Existing assessment points still penalize blanks as before. Written responses count as answered but never enter automatic accuracy.

## Attribution and history
The response includes seven course areas (the four Foundations children separately) and eight skills, including zero-data entries. Slugs/codes are identifiers; display labels come from existing taxonomy. Each topic/skill has answered, automatically graded, correct counts and nullable accuracy. Unrecognized/missing snapshot metadata is reported separately in `unattributed_topic` and `unattributed_skill`, preserving reconciliation with overview totals.

M4.1 already snapshots topic slugs. M4 did not snapshot skills. Small migration 0006 adds nullable `attempt_answers.skill_code`; new attempts copy the skill at creation. Old snapshots remain null: no backfill from mutable Question rows. Existing attempts already in progress also retain unknown skills. This is necessary for reliable future skill attribution without rewriting history. No Question join, regrading, answer content, or solutions appear in progress responses.

Recent history returns the latest ten submitted attempts ordered by submission time and ID, including historical quiz title, counts, accuracy, and unchanged objective points. Overall metrics cover all submitted attempts, not just the ten recent entries. Current question edits/deletion do not change attribution or results. Taxonomy labels are current; historical label/hierarchy renames are not snapshotted. Unknown or broad legacy topic slugs are not guessed into one of the seven areas.

## Implementation and verification
Pydantic response models; read-only service; eager batched loading of attempt items, with options loading disabled. No per-answer queries, cache or progress table. Aggregation is linear in the student's history; SQL aggregation/pagination can follow if history becomes large.

Apply with `python -m alembic upgrade head` from backend. Focused PostgreSQL tests cover access control, empty history, objective/written/blank answers, attribution, repeated and unfinished attempts, ownership, metadata changes/deletion, legacy null metadata and recent-history limit. M6B frontend integration and any staff/manual grading analytics remain deferred.

Verification: nine new progress cases passed. Full suite: 84 passed with one outdated 0005-head assertion; after updating that assertion to 0006, its targeted rerun passed (85 tests total). Alembic current reports 0006 (head), and alembic check reports no new upgrade operations. No frontend files were changed in M6A.
