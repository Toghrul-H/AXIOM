# M9A — Semester assessment configuration

This is course-level management data for Discrete Mathematics I. Stable document
prose, topics, scoring, equipment and duration rules belong to future predefined
templates, not these tables. No rendering, uploads, downloads or frontend is added.

## Domain

- `assessment_configurations`: unique academic-year start and SPRING/FALL term,
  display label, timestamps and nullable last-modifier User FK.
- `assessment_events`: one event of each supported type per configuration;
  optional DATE date/document_date, TIME start/end/latest-arrival, venue and notes.
  Timestamps and modifier are recorded. Schedule fields can remain unspecified.
- `assessment_rooms`: any number of named endterm rooms.
- `assessment_room_groups`: one row per group identifier, linked by a composite
  FK to its room/event. The event/identifier primary key prevents cross-room
  duplication even under concurrent writes. Group identifiers are trimmed strings,
  not a fixed numeric range or comma-separated list.

Owned data cascades on deletion. Modifier FKs use SET NULL and never delete users.
Nested edits update the parent configuration timestamp/modifier; room edits also
update the event. This records latest modification, not a full revision audit.
Mutation locks serialize edits to a configuration and recheck the actor's live role.

## API

Prefix: `/assessment-configurations`.

| Method | Path | Operation |
| --- | --- | --- |
| GET | prefix | List metadata, offset/limit pagination |
| POST | prefix | Create metadata |
| GET | `/{id}` | Detail including events, rooms and group rows |
| PATCH | `/{id}` | Update supplied metadata fields |
| DELETE | `/{id}` | Delete owned graph |
| POST | `/{id}/events` | Create event |
| PUT / DELETE | `/{id}/events/{event_id}` | Replace / delete event |
| POST | `/{id}/events/{event_id}/rooms` | Create room and groups |
| PUT / DELETE | `/{id}/events/{event_id}/rooms/{room_id}` | Replace / delete assignment |

PUT supplies the complete event or room input; omitted optional event fields reset
to null. Detail GET reads the entire nested graph. Room input uses
`{"room":"Room A","groups":["1","lab-A"]}`; output groups are structured rows
with an `identifier`. Creation returns 201, deletion 204, missing nested resources
404, conflicting uniqueness 409 and invalid inputs 422. No preformatted dates.

Only LECTURER and ADMIN can read/write. STUDENT and DEMONSTRATOR receive 403;
anonymous requests receive 401. Existing opaque sessions and CSRF apply unchanged.

Validation includes year 1900–9998, term/event enums, nonblank trimmed labels/rooms/
venues, distinct groups, nonempty room groups, and end strictly after start when
both are supplied. Times are local campus wall times without UTC offsets. Rooms
are currently endterm-only; remove assignments before changing that event type.

## Migration and open assumptions

`0010_semester_assessment_configuration`, after 0009, adds only four tables and
their constraints/index. Downgrade removes only those structures. No data seed.
Migration/tests run solely on the guarded local development database.

Confirm with the professor: one configuration per DMI academic year/term, one
event per type, local campus time convention, group identifier case/leading-zero
semantics, and whether any further calendar deadlines are needed. Academic-year
start 2026 denotes 2026/27; SPRING is in the latter calendar year. Display label is
editable and not parsed. Relative coursework timing can currently be captured in
notes; additional confirmed variables can be added as typed fields/event types in
later migrations. The list of variables is not assumed exhaustive.

M9B/M9C can build UI and predefined document generation on these structures.
No production/Neon operation or document-generation implementation is included.
