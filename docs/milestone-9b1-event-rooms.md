# M9B.1 — Event-level room assignments

Migration 0010 already relates rooms to an assessment event, with groups stored
as relational rows and uniqueness scoped to that event. No schema change or new
migration is needed. Existing endterm assignments remain unchanged.

API eligibility and UI visibility now include MIDTERM, ENDTERM, SHORT_QUIZ_RETAKE
and TEST_RETAKE. Coursework events do not expose room management. Explicit event
type allowlists can be extended later without changing the relational design.
Changing between supported types preserves rooms; changing to an unsupported type
requires removing its assignments first.

Venue remains nullable and room assignments optional. No placeholder text is
stored. Future templates decide how to render unknown venues/rooms. Each entered
room requires a nonblank name and at least one unique group. Groups cannot appear
in different rooms within one event but may have different rooms across events.
Existing event/configuration cascades, Lecturer/Admin permissions, CSRF and proxy
behavior are unchanged.

The editor reuses the existing room CRUD UI for all four event types and labels it
optional. No generation button, LaTeX/PDF rendering or document downloads exist.
Before M9C, confirm whether any additional event types need rooms; rendering of
missing information belongs to the forthcoming templates.
