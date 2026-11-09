# M13C — Fixed and Custom Demonstrator Application Questionnaires

Each vacancy has the same locked fixed application fields: full name, six-character
Neptun code, separate lecture and practice grades (1–5 or `NOT_YET_GRADED`),
practice teacher, motivation, weekly availability, preferred responsibilities,
optional relevant experience, and optional additional comments.

Lecturers and administrators can use the recruitment page to create, edit, reorder,
and remove up to 30 custom questions before any application exists. Supported types
are short text, long text, single choice, multiple choice, and yes/no. Choice
options and submitted answers are validated on the backend. Fixed fields are shown
in the builder but are not editable.

After the first application, the custom questionnaire is locked. Each submitted
custom answer retains a snapshot of the original question title, type, order, and
answer, so staff review and XLSX exports remain historically readable. M13A/M13B
applications remain valid; new fields render as `Not provided` rather than being
invented.

The staff-only export has separate lecture/practice grades, availability,
responsibilities, decisions, and labeled custom-question columns. Formula-like
values remain escaped. The Next.js proxy forwards the protected questionnaire PUT
endpoint with the existing cookie and CSRF handling.
