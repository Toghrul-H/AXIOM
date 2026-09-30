# AXIOM frontend — through Milestone 6

A local Next.js App Router, TypeScript, and Tailwind CSS interface. No hosting
provider or external fonts are required. Authentication and quizzes use the local FastAPI backend.

## Run locally

Use Node.js 24 LTS and pnpm 11.19.0. The lockfile records the resolved dependencies.
In a terminal opened at the repository root:

```powershell
cd frontend
pnpm install --frozen-lockfile
# Only on first setup, if .env.local does not exist:
Copy-Item .env.example .env.local
pnpm dev
```

Open http://127.0.0.1:3000. In another terminal at the repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Apply all Alembic migrations through revision `0006` in the backend before using this frontend.
Do not copy its password or environment file into the frontend.

## API configuration

`frontend/.env.local` contains `API_BASE_URL=http://127.0.0.1:8000` and is ignored
by Git. `.env.example` is safe to commit. Restart Next.js when changing it;
rebuild when using `pnpm build` / `pnpm start`.

The centralized client in `src/lib/questions.ts` calls `/api/questions` on the
frontend's own origin, plus `/api/question-metadata`. `next.config.ts` rewrites these paths
to the corresponding configured FastAPI endpoints. Requests use GET, POST, PATCH,
and DELETE; no local question database, localStorage cache, or fabricated teacher
records are used. Requests bypass fetch caching. No CORS changes were needed.
The application requires a Node.js server; it is not a static HTML export.

## Structure and routes

```text
src/
  app/                 App Router pages, shared layout, responsive Tailwind/CSS
    student/           Dashboard and planned Learn/Practice/Progress pages
    teacher/           Dashboard and Question Bank/new/edit pages
  components/          Shell, headings, dashboards, bank, form, edit loader
  lib/
    use-metadata.ts    Database-backed course hierarchy and lookup loading
    questions.ts       Typed FastAPI client and error handling
```

| Route                          | Purpose                                                  |
| ------------------------------ | -------------------------------------------------------- |
| `/`                            | Sign-in entry; authenticated users reach their role's dashboard |
| `/login`, `/register`           | Sign in or register a Student account                    |
| `/student`                     | Student Dashboard with clearly marked demo statistics    |
| `/student/learn`               | Database-backed course outline; no actual lessons        |
| `/student/quizzes`             | Available quizzes and signed-in Student's attempt history |
| `/student/progress`            | Planned-feature placeholder; no tracking                 |
| `/teacher`                     | Teacher Dashboard with a real three-question API preview |
| `/teacher/questions`           | Paginated real questions, answers, editing and deletion  |
| `/teacher/questions/new`       | Create a question                                        |
| `/teacher/questions/[id]/edit` | Load and update an existing question                     |
| `/teacher/users`               | Lecturer/Admin account search, promotion and status     |

The reusable `AppShell` provides role-derived navigation, course identity, mobile
menu, account email and Sign out. `AuthProvider` restores the session after refresh
and blocks wrong-role content. FastAPI independently enforces all permissions.
There is no development role switcher or localStorage identity.

`QuestionForm` supports all four response types, including 2–20 distinct choice
options and true/false answer selection. The backend remains the authoritative
validator. Delete uses a modal confirmation with a cancel action. Requests show
loading and error states and disable duplicate submission. Backend failures never
fall back to mock questions.

## Checks

```powershell
pnpm lint
pnpm typecheck
pnpm format:check
pnpm build
# Run the production build locally instead of the dev server:
pnpm start
```

See `../docs/milestone-3-verification.md` for the historical M3 browser verification record.

## Intentional limits

- Learn remains a course-outline preview; lessons are planned.
- Dashboard and Progress use authoritative authenticated M6A analytics.
- Staff routes require authorized roles; student attempts and progress are private.
- Question Bank uses server-side filters, exact totals and offset/limit pagination (12 per page).
- Mathematical text uses Unicode/plain text; LaTeX rendering is not implemented.
- The initial lint toolchain uses ESLint 9 for compatibility with Next's React
  lint plugins; the registry flags it as deprecated. Lint currently passes.

Milestone 4 adds the student quiz workflow described below.

## Structured question editing and filters

Topic/subtopic, response type, skill, PS1–PS12 and suitability choices come from the
metadata endpoint. Problem sets and suitability tags allow multiple selections.
The form also supports title, active/inactive, reference answer and full solution.
Single choice uses radio controls for exactly one correct option; multiple select
uses independent checkboxes. True/false uses a Boolean selector. Free response shows
a reference-answer field and explicitly states that it is not automatically graded.
Existing option IDs are preserved on edits.

Filters cover topic (including descendants), problem set, difficulty, response type,
skill, suitability, status and title/question text. Apply sends the combined filters
to PostgreSQL through FastAPI and resets pagination; Clear resets them. The frontend
never downloads an unlimited collection for filtering. List responses are now
`{items,total,offset,limit}`. Student topic cards also load the same hierarchy.
The stateless answer-check API remains available to staff in Swagger. Student quizzes use separate sanitized attempt APIs.

## Milestone 4 — student quiz workflow

Current routes: `/student/quizzes`, `/student/quizzes/attempts/[id]`, and the attempt's
`/results` and `/review` pages. The catalog includes resumable and completed attempt
history for the signed-in Student. Student navigation has Quizzes and no
Question Bank; the old practice URL redirects to quizzes. `/teacher/quizzes` provides
basic composition/order/points/availability editing. `/demonstrator` opens the shared
staff bank, with management links using teacher routes. Staff routes require a
Demonstrator, Lecturer or Admin account; user management is Lecturer/Admin only.

Apply backend migration `0003` and optionally run `python -m app.seed_quizzes`. No new
frontend dependency or environment value is required. `pnpm dev` and checks are unchanged.
`next.config.ts` additionally proxies `/api/quizzes/:path*` and `/api/student/:path*`.

`src/lib/quizzes.ts` centralizes quiz requests through the shared cookie/CSRF client.
Answers live in PostgreSQL, with 600ms autosave and explicit saved/error
states. Active question payloads contain no answer keys or solutions. Finish requires
confirmation; results and Review All Answers become available only after submission.
Written responses are saved and shown with reference solutions but never auto-graded.
See [Milestone 4 architecture](../docs/milestone-4-architecture.md) and
[verification](../docs/milestone-4-verification.md) for details and known limits.

## Milestone 4.1 — mathematical input

Quiz written answers now use a reusable Unicode textarea with topic-specific symbol
buttons. See [implementation and verification](../docs/milestone-4.1-math-input.md).
Apply backend revision `0004` for immutable topic context on new attempts. Old attempts
use a general toolbar. Startup and dependencies are unchanged.

## Milestone 5 — authentication

See [architecture and bootstrap instructions](../docs/milestone-5-authentication.md)
and [verification](../docs/milestone-5-verification.md). New pages are `/login`,
`/register`, and `/teacher/users`. Registration has no role selector. Existing
accounts can be promoted and deactivated/reactivated by authorized staff, with
confirmation. All affected sessions are revoked and the user must sign in again.
The proxy adds `/api/auth/*` and `/api/users/*`. Authentication cookies are HttpOnly;
the CSRF token stays in memory and is restored from `/auth/me`. No new frontend
dependency or environment variable is required. Startup commands are unchanged.

## Milestone 6 — Student Progress

The dashboard and `/student/progress` use authenticated M6A analytics. See
[frontend notes](../docs/milestone-6b-progress-frontend.md) and
[metric definitions](../docs/milestone-6a-progress-analytics.md).
