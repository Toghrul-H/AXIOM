# M9D.1 - Live Assessment Document Preview

Lecturer/Admin assessment detail pages now have a split workspace. Existing forms
remain on the left; an independently scrolling, ivory academic document appears
on the right with seven document selections. Below 1100px the panes stack.

## Data flow and safety

Form scopes identify metadata, policies, semester rules, events and room rows.
The workspace snapshots actual current form values (including unsaved edits and
group-deadline rows), rather than older saved React data. Input/change events and
structural form changes trigger a 350ms debounce. Document selection does not
remount or clear the editor. Pending requests abort immediately on subsequent
edits; a request version prevents stale responses from replacing newer content.

`POST /assessment-configurations/{id}/documents/{document_type}/preview` validates
the draft using the existing configuration schemas, assembles the document context
and calls the same renderer and seven LaTeX templates as the source-preview API.
It does not modify ORM objects, commit, update audit fields or automatically save.
Totals use current draft component maxima and cap. Until the rules form loads,
the saved semester rules are used. Invalid/partial inputs show a useful error and
explicitly mark any previous preview as out of date; Save behavior is unchanged.

A restricted presentation reader turns the rendered LaTeX into a JSON tree of
text, emphasis, headings, lists, tables, breaks and centered blocks. React renders
only known element kinds, with ordinary escaped text children. No HTML injection,
TeX execution, arbitrary includes, compilation or new dependencies are involved.
The existing templates were not rewritten, duplicated or replaced with seven HTML
documents. The same-origin proxy forwards authenticated POSTs and CSRF headers;
the backend retains Lecturer/Admin-only access. Responses remain no-store.

Unsaved indicators and existing navigation/unload warnings remain. Adding/removing
group rows, modifying existing room assignments and typing a new room assignment
are included in the draft. Empty unused add-room forms are omitted. Existing Save
actions still control persistence; deleting saved objects still uses the existing
explicit delete confirmation.

## Preview limitations

The panel is explicitly **Draft Preview**, not a PDF or pixel-identical typeset
output. Browser serif fonts, line wrapping, table widths, whitespace and page
breaks differ from a TeX engine. A4 proportions are approximate; long documents
flow continuously, and explicit template page breaks appear as separators.
Only the presentation commands used by the seven current templates are supported;
new template syntax needs a corresponding reader test/extension. Unknown syntax
is displayed as text, never executed. No mathematical TeX engine is introduced.

## Manual checks

1. Sign in locally as Lecturer or Admin; open Assessment Documents and a semester.
2. Select each of the seven documents in the right pane.
3. Edit an Endterm venue, writing time, arrival, topic or score without Save. After
   a short pause, check the draft and its unsaved indicator.
4. Switch to Dates of Assessments and back. Values must remain in the forms; Dates
   uses scheduled time while detailed information uses writing time.
5. Edit semester plus-point rules/grade boundaries and coursework group deadlines;
   inspect their documents. Try room edits and retake seating text too.
6. Enter literal HTML or LaTeX-like text in a description: it must appear as text.
7. Enter an invalid interval or incomplete grade boundaries: an error should mark
   the previous preview stale. Correct it and verify automatic recovery.
8. Leave with unsaved changes to check the existing warning. Save explicitly, then
   reload to verify persistence. Preview alone must not persist anything.
9. Narrow the window: panes stack and the document remains scrollable.

## Files for this milestone

- Backend: `app/document_generation/draft.py`, `preview.py`,
  `app/routers/assessments.py`, `tests/test_draft_preview.py`.
- Frontend: `src/lib/document-preview.ts`,
  `src/components/document-preview.tsx`, `src/components/assessment-editor.tsx`,
  `src/app/globals.css`, the assessment API proxy route,
  `tests/document-preview.test.mjs`, `tests/assessments.test.mjs`.
- This document. Existing uncommitted M9C.2 work is preserved.

No migration, production access, deployment, commit or push is part of M9D.1.

## Verification

- Focused backend preview/template tests: 32 passed.
- Focused frontend assessment/preview tests: 31 passed.
- Full backend suite: 226 passed (two existing Starlette deprecation warnings).
- Full frontend suite: 54 passed.
- Formatting, ESLint, TypeScript, production build and whitespace checks passed.
- A test-only variable name triggered Next.js lint; it was renamed and the focused
  tests/lint rechecked before completing TypeScript/build. No full suite was repeated.
- No browser automation or PDF compilation was performed. Use the manual steps
  above to review the browser layout and editing workflow locally.

## Document-focused editor recovery

The interrupted redesign had updated the preview navigation/render prop and visibility helper, but had not written the matching assessment editor. The editor now retains one mounted form per authoritative event/policy/rules record and changes visibility without copying or resetting values. Seven document buttons select both the relevant controls and the preview. Semester-wide component sections are collapsible; Midterm/Endterm scoring is shown directly alongside their schedule, rooms and instructions. Retakes reuse the original test policies; Coursework includes the four existing publication/hand-in events and existing hand-in group overrides. Plus Points exposes its rules, limit and shared total-score rules. No new publication-deadline schema was introduced.

Save buttons identify their section; each saves only its existing record. Hidden forms do not submit on navigation or preview. Unsaved changes and departure warnings remain active. The Endterm template explicitly labels conduct instructions to separate its missing-value fallback from the arrival sentence.

Manual verification: select each of the seven documents; edit a test score and venue without saving, switch to Dates/Retake and back, and confirm values and draft content survive. Save the changed sections, reload, and check persistence. Test room/group edits, coursework group overrides, Plus Points, an empty arrival time, and a narrow viewport. Preview remains a draft rather than a pixel-identical PDF. No browser automation, PDF compilation or production access is required.

Recovery verification: 55 frontend tests and 21 targeted template tests passed; frontend formatting, ESLint and TypeScript checks passed. No backend schema, authentication, proxy or persistence changes were needed.
