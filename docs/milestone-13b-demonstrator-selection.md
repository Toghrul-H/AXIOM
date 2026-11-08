# M13B — Demonstrator Application Review & Selection

Applications progress from `SUBMITTED` to `UNDER_REVIEW`, `ACCEPTED`, or
`REJECTED`. A student may withdraw only a submitted or under-review
application; accepted, rejected, and withdrawn applications are terminal.

Lecturers and administrators can review questionnaires, mark under review, and
confirm accept/reject decisions. Acceptance locks the vacancy row and counts
accepted applications inside the same transaction, so capacity cannot be
exceeded. Closing a vacancy preserves applications and prior decisions.

Students can see only their own application status and may confirm withdrawal.
Status changes create one private in-app notification per application status;
no email is sent. Staff summaries are aggregate-only and student vacancy
responses do not expose private status breakdowns.

The XLSX export includes status, decision timestamp, and decision-maker email,
with formula-like values escaped and questionnaire references kept staff-only.
Migration `0016_application_review_selection` adds nullable decision audit
fields without changing existing application records; existing rows remain
`SUBMITTED`.
