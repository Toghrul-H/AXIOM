# M9B — Assessment Documents management UI

Routes: `/teacher/assessments` lists/creates semesters;
`/teacher/assessments/[id]` edits semester metadata, all eight assessment types,
and endterm room/group assignments. Only Lecturer/Admin navigation and page
access are enabled; M9A backend permissions remain authoritative.

The list supports pagination, empty/error/loading states, opening a semester and
confirmed deletion. Each event has its own save/delete form. Optional dates/times,
venue, notes, document date and latest arrival remain typed API values. Each room
has an editable list of comma/newline-separated group identifiers; requests send
structured arrays. Blank/duplicate groups and backend conflicts show errors.
Successful edits preserve other open forms. Delete actions require confirmation;
dirty forms warn on browser unload and link navigation. Browser history navigation
does not have a custom blocker. No additional state-management dependency is used.

The explicit `/api/assessment-configurations/[[...parts]]` proxy allowlists M9A
CRUD routes, forwards cookies/CSRF/origin headers, disables caching and prevents
upstream redirects. It uses the existing API_BASE_URL. No backend change or migration.

This is configuration management only. LaTeX/PDF generation, preview, downloads
and templates are not implemented. M9C will use the highlighted source documents
to define templates and confirm any additional semester-variable fields.
