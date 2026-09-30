# Milestone 3 — course and Question Bank architecture

## Relational model

| Table | Purpose and relationships |
| --- | --- |
| `topics` | Single-course ordered tree: unique slug, name, nullable parent FK, sort order |
| `response_types` | Four response codes and display labels/order |
| `skill_types` | Eight academic skills plus `UNSPECIFIED` for unclassified legacy rows |
| `problem_sets` | PS1–PS12, unique codes and display order |
| `assessment_suitabilities` | Eight suitability codes and display labels/order |
| `questions` | Topic FK, optional title, difficulty, independent response/skill FKs, question text, reference text or Boolean answer, explanation, active flag, created/updated timestamps |
| `question_options` | Stable option ID, question FK, text, correct flag, position |
| `question_problem_sets` | Many-to-many question/problem-set association |
| `question_suitabilities` | Many-to-many question/suitability association |

Initial hierarchy: Foundations (Logic, Sets, Binary Relations, Functions), Complex
Numbers, Combinatorics, Graphs. No generic course/tenant/LMS layer was introduced.
Topic names, parent relationships and ordering are data; the form, filters and student
outline load them from `GET /question-metadata`. Developers can add/reorder topics
through a reviewed data migration without rewriting the application. A topic-management
UI is outside this milestone. Administrators must keep the tree acyclic; the database
rejects direct self-parenting but does not enforce arbitrary ancestor-cycle detection.

The eight skills are CALCULATION, DEFINITION, PROOF, THEOREM, EXAMPLE, APPLICATION,
CONSTRUCTION and CLASSIFICATION. `UNSPECIFIED` is visibly labelled “Needs classification”
so migration does not fabricate an academic classification. Response type never
implies skill type.

Suitability codes are GENERAL_PRACTICE, WEEKLY_QUIZ, MIDTERM, ENDTERM, COURSEWORK,
RETAKE, THEORY_SHORT and THEORY_PROOF. They describe possible uses, never historical
assessment membership. No actual assessments or assessment-question records exist yet.

Foreign keys restrict deletion of referenced taxonomy rows; deleting a question cascades
to its options and associations. Composite primary keys prevent duplicate associations.
Filter columns and reverse association keys are indexed. Choice position uniqueness is
deferrable to permit atomic reordering. Answer-storage checks prevent contradictory
reference/Boolean/choice answer fields; Pydantic/service validation enforces option
counts, uniqueness, correct-answer cardinality and valid lookup ownership.

## Answer model and extension boundaries

SINGLE_CHOICE has exactly one correct option; MULTIPLE_SELECT has one or more and is
checked by exact set equality. TRUE_FALSE uses a native Boolean. FREE_RESPONSE holds
a reference answer, never a claimed automatically correct proof or explanation.
`explanation` stores the full solution independently of the answer representation.
`POST /questions/{id}/check` is stateless and returns the answer/solution on either
outcome. It does not create attempts, scores, progress or practice sessions.

Additional response types can reuse the lookup and question/option relationships,
but require explicit schema validation, UI/checker handling and an answer-storage
constraint migration. Adding a lookup row alone cannot implement new answer semantics.
Later exact-answer free response should use an explicit, opt-in checking policy and
normalization rules; it must never infer gradeability from arbitrary reference text.

Future submissions/reviews should keep student text separate from question reference
solutions. Before adding persistent attempts or assessment history, design immutable
question revisions or snapshots: current options have stable IDs, but question editing
and deletion are intentionally available today. A future assessment-question link must
record actual usage separately from suitability. No such future tables were built now.

## Migration and preservation

Alembic `0002_course_question_foundation.py` upgrades `0001` transactionally. It creates
and seeds the lookup/relationship tables, maps rows, copies choice options, then removes
the superseded columns. Legacy mapping:

| Old data | New data |
| --- | --- |
| `short_answer` / `correct_answer` | FREE_RESPONSE / `expected_answer` |
| `multiple_choice` with JSON options | SINGLE_CHOICE with ordered option rows and correct flags |
| `true_false` with `true`/`false` text | TRUE_FALSE with Boolean value |
| Relations | Binary Relations |
| Graph Theory | Graphs |
| Other unknown topic names | Preserved as additional legacy topic nodes |
| Missing skill, PS or suitability information | UNSPECIFIED skill, empty associations |

IDs, question text, answers, explanations and creation times are retained. New
`updated_at` starts at `created_at`; legacy questions are active. Unconvertible choice
or Boolean data raises an error instead of silently inventing an answer.

The actual local database contained **zero questions** before this migration. An ignored
pre-migration questions JSON snapshot was saved under `backend/.local-backups/`; this
is an audit snapshot of the old questions table, not a complete PostgreSQL backup.
An automated isolated-schema test also verified preservation of three nonempty legacy
fixtures, including a custom topic. No user database reset was performed.

Downgrade is explicitly blocked because the new shape cannot round-trip without losing
information. Use a deliberate forward migration or a reviewed database backup restore.
The list API deliberately changes from an array to a page envelope; external old clients
must migrate together with the backend. The repository frontend already uses it.

## Development content

`python -m app.seed` creates seven `[DEV]` examples covering the seven subject areas,
all four response types and several skills, including a reference-only proof. It skips
matching existing titles and does not overwrite edited rows. The examples and their
PS/suitability associations are illustrative development data, **not official ELTE
questions, exam material, or authoritative problem-set mappings**. PS1–PS12 exist even
when no example refers to them. No official bulk import was performed.

## Future learning-feedback requirement

The platform is for learning/practice, not official university grading. A later
student-facing submission/feedback workflow must display a notice along these lines:

> Scores, answer checks, solutions, and feedback provided on this platform are intended for learning and practice purposes only. They do not constitute official assessment or guarantee the same score in a university examination. Official assessment may consider reasoning, justification, notation, method, completeness, and other marking criteria.

This is a documented product requirement, not a new disclaimer subsystem. No practice
engine, identity system, attempt history, manual review, exams, AI or LaTeX features
were added in Milestone 3.
