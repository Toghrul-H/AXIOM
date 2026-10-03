# M7D — Local demo and integration

Only the existing development account mechanism is used. No public role selector,
startup/migration seeding or production data is added. Registration remains STUDENT
only. `app.seed_m7` shares existing loopback/cookie/password/enable guards.

## Configure locally

In ignored `backend/.env` (or process environment), set these privately:

```dotenv
DEMO_SEED_ENABLED=true
DEMO_STUDENT_PASSWORD=<your-local-password-12-to-128-characters>
DEMO_DEMONSTRATOR_PASSWORD=<your-local-password-12-to-128-characters>
DEMO_LECTURER_PASSWORD=<your-local-password-12-to-128-characters>
DEMO_ADMIN_PASSWORD=<your-local-password-12-to-128-characters>
```

Do not paste passwords into chat, commits or shared terminals. Use the same values
as existing demo accounts to preserve credentials. Confirm DATABASE_HOST is localhost,
127.0.0.1 or ::1 and AUTH_COOKIE_SECURE=false for local HTTP. Never use Neon here.

From `backend` in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m app.seed_m7 --local-development
```

This creates/ensures Student, Demonstrator, Lecturer and Admin via the existing
idempotent account seeder. It restores four reserved `[DEV M7]` questions and the
active `M7 Manual Grading Demo` quiz. It uses existing QuestionCreate/QuizWrite and
save services, one transaction with savepoints and a serialized seed lock. Reruns
retain IDs and associations. Edited reserved demo content is reset deliberately;
other questions/quizzes and historical attempt snapshots are not changed. Do not
rename reserved demo titles if you want them recognized on reruns.

Four questions in order: subset single choice (1 point), reflexivity true/false
(1 point), intersection proof (5 points), injective/surjective definition (4 points).

## Run and review

Backend, from `backend`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend, in another terminal from `frontend`:

```powershell
pnpm dev
```

1. Open http://127.0.0.1:3000/login. Use SIGN IN as `student1@axiom.local`
   with DEMO_STUDENT_PASSWORD; do not register the demo accounts.
2. Open Quizzes, start M7 Manual Grading Demo, answer all four questions and submit.
3. Review All Answers: objective answers show automatic results; written work is pending.
4. Sign out. Sign in as `lecturer1@axiom.local` or `demonstrator1@axiom.local`
   using the corresponding local password variable.
5. Manual Grading → Grade: assign whole-number points within 5 and 4 respectively,
   enter feedback, save. Blank answers can receive only explicit zero points.
6. Sign out and return as Student. Review the same attempt, or Refresh results.
   Manual points and feedback appear; objective points and automatic accuracy stay separate.
7. Completed/All queue filters allow re-grading. Student Refresh retrieves the latest grade.

## Production provisioning — instructions only

Never use the demo seed in production. In a trusted private server shell configured
for the intended database, bootstrap the FIRST Admin using
`python -m app.scripts.create_admin` and its private prompts. It refuses to run if
an Admin already exists. Use a separate, previously unregistered admin email.
There is no direct first-Lecturer bootstrap: bootstrap Admin first, have the intended
Lecturer register normally as STUDENT, then have Admin promote that account through
Staff Management. Lecturers can promote registered Students to Demonstrators;
Admin can promote registered Students/Demonstrators to Lecturer. Role changes revoke
sessions and require a new sign-in. Additional Admin creation is not exposed publicly.
Verify the recipient's identity through a trusted channel before elevating them.
No production account or migration is executed by this document or seed.

## Deployment prerequisites

Production still requires an explicitly reviewed migration to 0007, the M7 frontend
release and controlled staff provisioning. These operations are outside M7D. Email
verification and grading revision history remain deferred.

## Verification status

104 backend tests passed, including three new seed/guard/integration tests.
The exact four-question workflow was verified with temporary local fixtures:
Student submission, pending written work, Lecturer and Demonstrator grading,
Student feedback visibility, and unchanged objective score/progress. Test fixtures
were cleaned up. Transactional repeat seeding verified stable question/quiz counts
and four associations. Existing four demo users were verified active with correct roles.

Persistent local demo preparation completed after private environment configuration.
The command ensured all four demo accounts and created the four questions and active
quiz #165. A second seed preserved question/quiz IDs and confirmed exactly four
questions and one demo quiz, without duplicates. Existing attempts were preserved.
No frontend source changed, so frontend checks were not rerun.
