# Milestone 4.1 — mathematical answer input

`frontend/src/components/math-answer-input.tsx` is a reusable controlled textarea with
labelled symbol buttons. `frontend/src/lib/math-symbols.ts` centralizes symbol definitions,
topic mapping, optional extra-symbol merging, spacing and cursor-insertion behavior.
Only FREE_RESPONSE in the quiz uses it now; the staff editor was not redesigned.

## Profiles

| Snapshot topic slug | Toolbar |
| --- | --- |
| `logic` | Logic |
| `sets` | Sets |
| `binary-relations`, `functions` | Relations / Functions |
| `complex-numbers` | Complex Numbers |
| `combinatorics` | Combinatorics |
| `graphs` | Graphs |
| Missing/unrecognized (including Foundations itself) | Small general toolbar |

Each group contains the requested basic Unicode symbols and pairs. Relations/Functions
also includes the Unicode squared character so `x ↦ x²` is practical without an exponent
editor. The `extraSymbols` prop merges additional symbols with a profile, deduplicated by
button text. No teacher configuration UI or persisted custom-symbol field was added.

Clicking inserts at the textarea selection/cursor and restores focus/caret. Binary
operators add separating spaces where needed. Inverse, squared, factorial and degree
symbols attach directly. Pairs insert both delimiters and put the cursor inside; selected
text is wrapped by pairs. For other symbols, a selection is replaced as in normal typing.
Text outside the selection is preserved. Buttons work with keyboard activation, have
accessible names/tooltips, and wrap using flex layout. Insertion respects the textarea
length limit. This remains ordinary Unicode text, not LaTeX or an equation document.

## Minimal backend change

The old active-attempt API had no topic metadata. Alembic `0004_attempt_topic_context.py`
adds nullable `attempt_answers.topic_slug` (120 characters). New attempts copy the bank
question's topic slug when snapshotting. Active/review schemas expose this non-answer
context; they still exclude answer keys during the quiz. Later topic changes cannot
silently change an existing attempt's input profile.

Existing snapshots deliberately retain null rather than guessing historical topic from
current bank data. They use General symbols and remain fully usable. No answer-storage,
grading, identity, submission or review-format change was needed. Review already renders
Unicode and preserves line breaks. No new dependency was installed.

Before migration: revision 0003, seven questions and four attempts. After verification
cleanup: the same seven questions and four original attempts remain. Migration 0004 is
applied, and Alembic reports no schema drift. Normal startup commands are unchanged;
other checkouts should run `alembic upgrade head` before restarting the backend.

## Verification — 22 September 2026

- **47 backend tests passed**, including all previous tests. Added coverage for exact
  multiline Unicode persistence, resume, submission/review, unchanged topic context after
  a bank edit, and loading a legacy null topic. The two existing Starlette dependency
  deprecation warnings remain.
- Frontend ESLint, TypeScript, Prettier and Next.js production build passed.
- No frontend component-test framework exists; no new framework was introduced for this
  small extension. Component behavior was verified in the real browser.
- Disposable quiz fixtures covered Sets, Logic, Relations, Functions, Complex Numbers,
  Combinatorics, Graphs and an unrecognized-profile fallback, plus a true/false question.
- Typed `AB`, moved the cursor between characters, clicked intersection: `A ∩ B`.
  Focus remained in the textarea. Typed `C` at the resulting caret: `A ∩ CB`, then
  removed it and continued normally. Used equals/braces to construct `A ∩ B = {2, 4}`.
- Verified each topic displayed its own group and inserted representative symbols:
  `p ∧ q`, `R⁻¹`, `x ↦ x²`, `z = √2`, `n!`, `v ∈ V`; general keyboard activation produced `a = b`.
- At a 375px viewport, the Sets toolbar wrapped to three rows. Its client and scroll
  widths both measured 278px (no horizontal overflow). Restored default viewport.
- Refresh restored the exact Unicode answer. Submission/review showed every saved
  mathematical response unchanged; written answers remained ungraded. The objective
  question scored 1/1 and displayed its normal explanation.
- Independently verified the answer in PostgreSQL. Removed only the temporary quiz,
  its temporary questions and its attempt afterward.

## Limits

Plain-text insertion only: no structured fractions, roots, matrices, rendering engine,
equivalence checking, AI/proof grading or authentication. The square-root and squared
buttons insert Unicode characters, not editable equation structures. New/unrecognized
topic slugs use General until a mapping is added centrally. Historical attempts without
topic context also use General. Future staff reuse can pass the same profile and optional
extras; it does not require another textarea implementation.
