# M9C: shared assessment configuration and LaTeX rendering foundation

## M9C.2 update: seven templates

All seven document types now generate LaTeX through the existing authenticated
`GET /assessment-configurations/{id}/documents/{document_type}/latex` API:

| Document type | Template |
| --- | --- |
| `DATES_OF_ASSESSMENTS` | `dates_of_assessments.tex` |
| `ENDTERM_TEST_INFORMATION` | `endterm_test_information.tex` |
| `RULES_OF_ASSESSMENT` | `rules_of_assessment.tex` |
| `RULES_OF_EARNING_PLUS_POINTS` | `rules_of_earning_plus_points.tex` |
| `MIDTERM_TEST_INFORMATION` | `midterm_test_information.tex` |
| `TEST_RETAKE_INFORMATION` | `test_retake_information.tex` |
| `COURSEWORK_ASSIGNMENT_INFORMATION` | `coursework_assignment_information.tex` |

The five supplied PDFs were read in full again for implementation. The source
section order, introductory explanations and stable student instructions are
retained. Variable academic rules remain in the M9C shared configuration, not
reference-semester defaults. Specifically:

- `conduct_instructions` supplies paper/ID requirements, lateness limits,
  leaving-room restrictions and marking deadlines. The detailed test templates
  retain beginning/during/end/after headings and stable invigilator instructions.
- Coursework `assessment_mode` and `conduct_instructions` supply submission
  format; `preparation_instructions` supplies assignment-specific question guidance
  (including the source's polar-form and diagram instructions when applicable).
  The template does not assume every future assignment has those three questions.
- `plus_points_rules` supplies homework/coding/noncoding/Canvas task awards,
  quiz names, eligibility, deadlines and submission channels. `total_score_rules`
  supplies plus-point usage conditions; the cap has one numeric source.
- Attendance exceptions and replacement-test policies use the existing attendance,
  total-score and retake descriptions. No legal rule, historical absence allowance
  or reference access date is silently treated as current semester policy.
- Rules of assessment uses official scheduled intervals. Midterm/retake detailed
  information uses writing intervals, with the existing whole-interval fallback.
  Retake arrival and seating belong to TEST_RETAKE, not MIDTERM or ENDTERM.
  Original midterm and endterm policies are shown separately for retakers.
- Both coursework documents and Dates of assessments call the same submission
  formatter, including sorted group overrides and general-value inheritance.
- Grade thresholds and maximum total are read from the validated context, not
  recalculated from source-PDF numbers. Missing policies render neutral text.

The new documents allow missing events and render neutral placeholders. The
existing Endterm document's missing-event 422 behavior is preserved. Populating
reviewed semester policies is necessary for complete publication-ready instructions.
No schema, migration, dependency or configuration-variable change was needed.

The same-origin proxy allowlist now admits all seven preview paths and the existing
M9C rules/policy routes (previously rejected by the proxy). Cookie/CSRF forwarding,
no-store responses, role enforcement and unsupported-path rejection remain intact.
No UI redesign, PDF compilation, download or split-screen preview was added.

The professor-confirmation questions below remain unresolved, including arrival,
coursework deadline, plus-point scope, fractional thresholds and retake wording.
The five templates are now implemented; the older scope and verification sections
below record M9C's original checkpoint rather than the current template count.

M9C.2 changed files: `service.py`, the five new `.tex` files listed above,
`tests/test_document_api.py`, new `tests/test_seven_documents.py`,
the frontend assessment proxy route and `frontend/tests/assessments.test.mjs`,
and this documentation. No existing source PDFs were modified.

M9C.2 verification: focused backend 30 passed; focused frontend 25 passed.
Full backend 214 passed (two existing Starlette dependency deprecation warnings);
full frontend 48 passed. Formatting, ESLint, TypeScript, production build and
`git diff --check` passed. Tests used guarded local PostgreSQL and mocked external
email delivery. No PDF compilation, production access, commit or deployment occurred.

## Scope and recovery

Recovered the interrupted M9C work: migration 0011, optional writing times,
editor labels, typed rendering context, safe LaTeX escaping, two templates and
preview tests. Fixed the context's `date` annotation shadowing (which prevented
test collection). Updated tests that assumed fixed academic policies: those
policies are now semester configuration, following professor feedback.

This continuation implements the shared domain and existing Lecturer/Admin forms.
Only **Dates of assessments** and **Endterm test information** render LaTeX.
The five additional templates are mapped below, **not implemented**. There is no
PDF compilation, download, new compilation dependency or production operation.

## Database and ownership

- **0011** adds nullable SQL `Time` columns `writing_start_time` and
  `writing_end_time`, with an independent ordering check. The existing
  `latest_arrival_time` came from 0010 and is reused, not duplicated.
- **0012** adds nullable semester rule fields, event submission/seating fields and
  three child tables: `assessment_policies`, `assessment_grade_boundaries`,
  `assessment_group_deadlines`. No reference-semester data or policy defaults are
  inserted. Existing schedules, users, questions and assessment data are retained.
- Children cascade on parent deletion. Policies have a composite semester/code
  primary key; group deadlines have an event/group key. Grade thresholds are
  unique per semester. Numeric/date/time columns and database checks back the API
  validation. Downgrading drops only the respective new fields/tables, so exporting
  newly entered configuration first is necessary if downgrading deliberately.
- Existing audit timestamps/actor IDs on semester/event are updated when policies,
  rules or deadlines change. Existing manager role checks, live account rechecks,
  session cookies, CSRF and same-origin proxy remain in effect.

## Shared configuration

### Scheduled, writing and arrival times

`date`, `start_time`, `end_time` remain the official scheduled interval. Dates of
assessments uses it. Detailed test information uses the optional writing interval;
only when **both** writing values are absent does it fall back to the schedule.
A partial writing interval never borrows the other endpoint from the schedule.
Both intervals require start < end if both endpoints exist. Times are local campus
clock times; UTC offsets are rejected. No implied time is stored.

`latest_arrival_time` is independent. Both arrival sentences use the same value.
An absent value produces a complete neutral announcement sentence.

### Four reusable component policies

Each semester can configure `SHORT_QUIZZES`, `MIDTERM`, `ENDTERM`, `COURSEWORK`.
These represent assessment components, not individual quiz-platform attempts.
Retakes reference the corresponding original policy when rendering; a combined
test retake does **not** assume midterm and endterm scoring are identical.

| Field | Meaning |
| --- | --- |
| `topics` | Plain-text syllabus/problem-set description |
| `assessment_mode` | In-person/online, written/oral, paper/submission instructions |
| `duration_minutes` | Optional positive whole-minute duration |
| `duration_description` | Alternative description for ranges/relative duration; used if minutes absent |
| `maximum_score`, `passing_score` | Decimal component scores; passing cannot exceed maximum |
| `assessment_count` | Optional number of assessments; no default ten quizzes |
| `success_criteria` | Additional academic conditions |
| `permitted_equipment` | Permitted items and restrictions |
| `retake_rules` | Eligibility, number of retakes, score replacement and submission rules |
| `preparation_instructions` | Schedule descriptions, preparation and assignment-specific question guidance |
| `conduct_instructions` | Before/during/after test instructions, materials, lateness and feedback rules |

Short-quiz maximum/passing scores are **aggregate component values**, not per-quiz
scores. Scores have two decimal places, support fractional points, reject negative,
non-finite and excessive-precision values. Descriptions use existing trimmed,
nonblank, length-limited plain-text validation. All settings remain optional.

### Semester rules and grade boundaries

`course_topics`, `attendance_rules`, `total_score_rules`, `plus_points_rules` are
validated descriptions. They support semester-specific attendance exceptions,
passing gates, total-score conditions, optional tasks, half-point awards,
deadlines and submission channels without executing a formula or academic policy.
`plus_points_maximum` is a nullable decimal, including an explicitly configured zero.

Grade boundaries store grade 1–5 and minimum scores: either all five are supplied,
with grade 1 starting at zero and strictly increasing thresholds, or none are.
A threshold is inclusive, the next grade's threshold exclusive. This avoids
ambiguous decimal gaps between integer upper/lower boundaries. Thresholds cannot
exceed a fully configured total maximum.

Read-only `maximum_total_score` sums the four component maxima and the plus-point
cap **only when all are known**; otherwise null. Counts do not multiply an already
aggregate short-quiz maximum, and retakes are never double-counted. These fields
describe course policy; they do not compute a student's grade or modify M6/M7.

### Submission deadlines and seating

Coursework hand-in and coursework-retake hand-in events support nullable
`submission_deadline_date`, `submission_deadline_time`, `submission_venue`,
`submission_instructions`. They are independent of scheduled/writing intervals.
For backward compatibility, rendering falls back to an existing hand-in event's
date/start/venue if its explicit submission fields are absent.

Each event can have group-specific overrides: arbitrary `group_identifier`, date,
time, venue and instructions. Unspecified group fields inherit the general
submission value; nothing is copied into the database. A group may occur once per
event. Relative deadlines (e.g. penultimate class) go in instructions, not invented
dates. Submission details are rejected for non-hand-in events. Changing event type
requires clearing incompatible submission/room data first. Old clients that omit
new submission/seating fields preserve existing values.

`seating_plan` is event-specific plain text. It can describe announced-on-arrival
plans, room-specific rows/columns, and separate midterm/endterm retaker columns.
Existing structured practice-group room assignments remain separate and unchanged.
This is not an automatic seat allocation engine.

## API and UI

All routes below require an active Lecturer or Admin. Mutations use existing CSRF.

- Existing semester/event/room CRUD remains available.
- `GET/PUT /assessment-configurations/{id}/rules`
- `PUT /assessment-configurations/{id}/policies/{code}` (idempotent profile save)
- Semester detail includes policies, rules, thresholds and derived total.
- Event payloads/read responses include seating, submission fields and group overrides.
- `GET /assessment-configurations/{id}/documents/{document_type}/latex` returns
  `text/plain`, no-store, for `DATES_OF_ASSESSMENTS` or `ENDTERM_TEST_INFORMATION`.
  Missing semester: 404; missing Endterm event: 422; unsupported type: 422.

The existing editor adds collapsible semester rules and four policy forms, clearly
separated scheduled/writing labels, seating text and add/remove group deadline
rows. It reuses existing save/error/loading/unsaved-change behavior, styling and
authenticated API helpers. There is no new navigation or preview/download UI.

## Rendering and source mapping

The service converts validated DTOs into an explicit document context. Templates
receive preformatted values, not raw ORM objects. Only two fixed local template
paths are selectable. Dynamic strings escape `\\ { } # $ % & _ ~ ^` and control
characters. A single interpolation pass prevents user text becoming template
instructions. Notes are internal and not printed. No shell, subprocess, arbitrary
LaTeX, external include or network action is invoked by rendering.

Both original highlighted PDFs were inspected (4 + 2 pages). The five additional
PDFs were inspected in full by text extraction and rendered page images (13 pages).
Source examples are evidence for configurable fields, not imported semester defaults.

| Reference / pages | Shared mapping | Template status |
| --- | --- | --- |
| Dates_of_assessments_Spring_2025_highlighted (4) | Semester label; scheduled dates/intervals; venues; shared component policies; publication events; submission deadlines and group overrides | LaTeX implemented; updated to remove fixed scoring/topics/mode/deadline policies |
| Endterm_test_information_Spring_2025_highlighted (2) | Writing interval, arrival, document date, room groups, seating and Endterm profile | LaTeX implemented; configured instructions replace source-semester fixed rules |
| Midterm test information_Fri_Spring 2026 (2) | MIDTERM event/profile, writing/arrival, lecture/group context in descriptions, seating announced at test, equipment/conduct | Mapped only |
| Midterm_Endterm retake information_Spring 2026 (2) | TEST_RETAKE schedule/arrival/venue/seating; original MIDTERM and ENDTERM policies; submission-dependent score override in retake rules | Mapped only |
| dm1_Information for the Coursework assignment_2025 Autumn (2) | COURSEWORK profile, group-specific hand-in dates, submission instructions, Canvas access and question-by-question preparation guidance | Mapped only |
| Rules of assessment for the DM1 practice classes_Autumn 2026 (5) | Semester topics/attendance/passing gates; four component scores; grade thresholds; plus cap; event schedules; group deadlines; retake policies | Mapped only |
| Rules of earning plus points in the DM1 practice classes_Autumn 2026 (2) | Plus cap/rules: homework 0.5/1 examples, optional coding/noncoding work, deadlines, special Canvas quiz awards, teacher-defined tasks | Mapped only |

No historic durations, scores, arrival values, room numbers or academic policies are
seeded. Missing configuration renders “to be announced”; it does not silently use
Spring 2025 policy. The two templates retain their document purposes and section
structure, but optional configured descriptions determine academic instructions.

## Professor confirmation still needed

1. Original highlighted Endterm source says **10:05 and 16:05** for arrival.
   Neither is assumed a typo. One event field prevents contradictory generated
   arrival instructions; the intended historical value remains unconfirmed.
2. Autumn 2025 coursework introduction says **last practice class**, while the
   summary/submission sections say **penultimate class**. Configure the confirmed
   group deadlines; do not inherit one of those words as a universal default.
3. Autumn 2026 plus-points document omits coursework from its total/eligibility
   wording; the assessment-rules document explicitly includes coursework. Confirm
   the desired plus-points prose. The shared four-component total includes a
   configured coursework maximum once, not zero or twice.
4. Confirm fractional-score interpretation of the integer grade-boundary table;
   the model represents inclusive minimum thresholds without computing grades.
5. Retake source's “maximum ... endterm test” in a combined retake document,
   submission-dependent overrides, and differences from general assessment rules
   need editorial confirmation. The original coursework-retake source also says
   “original test” where “coursework” may be intended.
6. Source seating text says “row is is”; confirm intended row numbering before
   publishing. Configurable seating accommodates the different retaker columns.
7. Source-relative deadlines (Spring break, lecture 10, last/penultimate class,
   midnight on an event day) and conduct rules must be confirmed for each semester.
   Public regulation links in the reference are source references, not verified
   current university rules.

## Verification and next milestone boundary

Tests cover scheduled/writing/arrival distinction, fallback/null values, safe
escaping, shared policy rendering, group overrides, persistence, validation,
Lecturer/Admin authorization, Student/Demonstrator denial, CSRF, old-client
preservation, cascade deletion and 0011/0012 migration compatibility in temporary
local PostgreSQL schemas. Frontend tests exercise payloads, editor saves, role
access and the existing proxy path. Test fixtures clean up their own data.

Remaining work: implement and proofread the five mapped templates from the actual
references; confirm unresolved prose; populate reviewed semester policies. Later
PDF work must address compiler isolation, resource limits, Unicode/font support,
visual pagination, preview/download UX and deployment requirements. LaTeX was not
compiled in this milestone, per the continuation's explicit restriction.

Final local verification: 194 backend tests and 47 frontend tests passed.
Frontend formatting, ESLint, TypeScript and production build passed. Alembic
reports `0012 (head)` and no new upgrade operations. Two existing Starlette test
dependency deprecation warnings remain. No production database was accessed.

## Changed-file inventory

Modified tracked files:
- `backend/app/assessment_models.py`
- `backend/app/assessment_schemas.py`
- `backend/app/routers/assessments.py`
- `backend/tests/test_postgres.py`
- `frontend/src/components/assessment-editor.tsx`
- `frontend/src/lib/assessments.ts`
- `frontend/tests/assessments.test.mjs`

New/recovered untracked source and documentation:
- `backend/alembic/versions/0011_assessment_writing_times.py`
- `backend/alembic/versions/0012_assessment_shared_policies.py`
- `backend/app/assessment_policy_schemas.py`
- `backend/app/document_generation/__init__.py`
- `backend/app/document_generation/context.py`
- `backend/app/document_generation/latex.py`
- `backend/app/document_generation/service.py`
- `backend/app/document_generation/templates/dates_of_assessments.tex`
- `backend/app/document_generation/templates/endterm_test_information.tex`
- `backend/tests/test_document_generation.py`
- `backend/tests/test_document_api.py`
- `backend/tests/test_assessment_policies.py`
- `docs/milestone-9c-latex-rendering.md`
