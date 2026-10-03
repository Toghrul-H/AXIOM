# M7A — Manual grading backend foundation

## Semantics

Only submitted attempt answers with snapshot response type `FREE_RESPONSE` are
eligible. Pending/completed status is derived from nullable `manual_points`; there
is no duplicate stored status. Objective answers report `NOT_APPLICABLE`.
In-progress attempts are not in the queue and cannot be inspected/graded here.

All submitted written questions require review, including blank answers. Blank or
whitespace-only answers may receive only zero points; they remain pending until
staff explicitly grade them. Awarded points are strict integers from zero through
the immutable attempt answer's `points` maximum. Feedback is optional, trimmed,
limited to 20,000 characters, and cleared when omitted/null on a replacement PUT.

Grades are immediately visible in the owner's existing submitted review response.
Re-grading replaces score, feedback, grader and timestamp; the latest successful
write wins. Updates lock the attempt and recheck the active staff role under a user
lock. This milestone stores the latest grade, not a revision/audit history or a
separate publish/approval workflow.

## Authorization and API

DEMONSTRATOR, LECTURER and ADMIN may inspect and grade all submitted manual work
under the existing shared-course staff authorization model. Students and anonymous
clients cannot use these endpoints. Existing session/CSRF protection applies.

- `GET /grading/attempts?status=pending&offset=0&limit=20`: paginated queue; status
  may also be `completed` or `all`, limit 1–100. Oldest submissions first, ID tie-break.
  Returns total, student ID/email only, historical quiz title/ID, submission time,
  manual-answer count, pending count and aggregate grading status.
- `GET /grading/attempts/{attempt_id}`: submitted snapshot review with student
  ID/email and grader IDs for staff. Also permits already completed manual work.
- `PUT /grading/attempts/{attempt_id}/answers/{answer_id}`:
  `{"points": 2, "feedback": "Explain the final implication."}`. Returns the staff
  attempt review. 404 for missing/mismatched IDs; 409 for unsubmitted/no-manual-work
  attempts; 422 for invalid input, objective answers, excess points or positive
  points for blanks; 401/403 for authentication/authorization/CSRF failures.

Existing submitted review/submit responses gain `manual_grading_status`,
`manual_points`, `manual_feedback` and `graded_at` on each item. Students receive no
grader identity. History list and active-attempt contracts are unchanged; existing
review ownership checks continue to apply. No frontend/proxy routes are added yet.

## Database and historical integrity

Alembic `0007` adds four nullable columns to `attempt_answers`: integer manual
points, text feedback, grader user FK and timezone-aware timestamp. A check
constraint enforces all-or-none grade metadata, FREE_RESPONSE eligibility and the
snapshot point range. The grader FK is indexed and uses RESTRICT on deletion,
preserving attribution; normal account deactivation remains available.

Existing rows are preserved with null grading fields; submitted FREE_RESPONSE
answers therefore appear pending without inventing grades or graders. Downgrade
removes only the new grading fields/constraints/index, intentionally discarding
manual grade data while preserving original answers and attempts. Export grades
before a deliberate downgrade. No production migration was run.

Automatic `is_correct`, `points_awarded`, objective totals, submission grading and
M6 practice accuracy are unchanged. Manual points never enter automatic accuracy.
The existing `ungraded_count` retains its historical meaning of written items not
automatically graded; use the new manual status for manual completion. Reference
answers, question text and maximum points come from snapshots even after bank
edits/deletion. The queue uses SQL aggregates, not per-attempt queries.

## Verification

Focused tests cover staff roles, Student/anonymous/inactive/CSRF denial, pending
and completed queues, unsubmitted and mismatched answers, strict score/feedback
validation, blank responses, persistence and re-grading, private Student review,
historical edits/deletion, unchanged progress and database constraints. An isolated
schema test exercises 0006 → 0007 → 0006 → 0007 with existing answer preservation.
No UI, design, deployment settings or automatic grading changes are included.

## M7B — staff frontend implemented

Staff navigation now includes Manual Grading for Demonstrator, Lecturer and Admin.
`/teacher/grading` loads the backend queue with pending/completed/all filters,
20-row pagination, explicit refresh and retryable errors. Returning from an attempt
mounts the queue and fetches current backend counts; completed work is not retained
in the pending list. Use Completed or All to reopen work for re-grading.

`/teacher/grading/[id]` displays only the historical FREE_RESPONSE snapshots,
student response, reference/explanation and stored grading state. Each answer has
independent integer score/optional feedback controls, save lock, validation, success
confirmation and server errors. Saving updates that answer without resetting
unsaved edits to other answers. Re-grading replaces the latest grade as in M7A.

The frontend uses the shared cookie/CSRF client. A narrow same-origin Next.js
`/api/grading/attempts/[[...parts]]` GET/PUT handler forwards only grading requests
to the existing API_BASE_URL, including session/CSRF/origin headers, with no caching.
This fills a missing grading transport route without editing deployment settings,
Next.js rewrite configuration or backend endpoints. Existing staff-page guards and
backend authorization remain authoritative. Student feedback UI remains M7C.

## M7C — student review feedback implemented

The existing completed-attempt review now shows a neutral “Pending manual review”
state for ungraded FREE_RESPONSE answers, or persisted manual points/maximum,
optional staff feedback and grading timestamp for completed grades. Zero points is
an explicit completed grade, including blank answers graded zero. Feedback is plain
React text; no grader identity or staff-only data is requested/displayed.

Objective answer checks, reference solutions, objective points and automatic
practice accuracy remain unchanged. No combined percentage is calculated. The
results summary still labels written responses as not automatically graded, which
is true even after manual grading. Review All Answers opens the existing review.
Refresh results fetches the latest persisted grades; errors provide Retry. No
revision history, backend changes, migrations, deployment changes or notifications.
