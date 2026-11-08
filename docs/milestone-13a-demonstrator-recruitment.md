# M13A — Demonstrator Recruitment

Students can view published demonstrator opportunities, see database-derived
applicant counts, receive one in-app vacancy notification, submit one private
questionnaire per vacancy, and view only their own submissions. Applications
are accepted only for open, dated, non-zero-position vacancies.

Lecturers and administrators manage draft/open/closed vacancies, review
paginated applicant questionnaires, and export a staff-only `.xlsx` file.
The export prefixes formula-like values and contains an authenticated staff
route rather than public questionnaire links.

`0015_demonstrator_recruitment` adds vacancies, applications, and private
notifications with ownership foreign keys, indexes, and uniqueness constraints.
Endpoints are under `/demonstrator-vacancies`, `/demonstrator-applications/me`,
`/notifications/recruitment`, and `/staff/demonstrator-vacancies`.

Future work may add application-status decisions or course eligibility data;
this milestone deliberately has no ranking, hiring, payroll, HR, or external
Neptun integration.
