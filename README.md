# AXIOM — Interactive Teaching and Learning Support Platform for Discrete Mathematics I

AXIOM supports students and teaching staff in the ELTE Faculty of Informatics
Discrete Mathematics I course. Current implementation: M1–M6 (M6A and M6B),
with AXIOM Design v1.

## Technology

Next.js, TypeScript, Tailwind CSS, FastAPI, PostgreSQL, SQLAlchemy and Alembic.

## Implemented

- Authentication and role-based access: STUDENT, DEMONSTRATOR, LECTURER, ADMIN.
- Question Bank, course topic hierarchy, response types and skill taxonomy.
- Quiz Management and Student Quiz System with saved attempts and ownership.
- Mathematical answer input; quiz results, review and solutions.
- Student Progress Tracking: overview, topic performance, skill performance,
  recent attempts and auto-graded practice accuracy.
- AXIOM Design v1 with the navy, gold/champagne and beige/ivory palette.

Practice accuracy uses answered, automatically graded questions in completed
attempts. Ungraded written answers do not count as incorrect. No-data accuracy
is null, not zero; repeated completed attempts count as practice history.

## Planned — not implemented

Staff manual grading/review, Exam Builder, Practice Sheet Generator, Question
Generator, solution/variant generation, LaTeX/PDF tools, course material tools
and advanced visualizations. Visible tool placeholders do not implement these features.

## Local development

See [backend setup](backend/README.md) and [frontend setup](frontend/README.md)
for installation and startup. Apply all migrations with `python -m alembic upgrade head`
from `backend`; the current head is `0006`. Keep actual environment values in
ignored local `.env` files; `.env.example` contains safe placeholders only.

Optional demo accounts are created only by manually running
`python -m app.scripts.seed_demo_users --local-development` from `backend`.
Set `DEMO_SEED_ENABLED=true` and the four `DEMO_*_PASSWORD` variables listed in
`backend/.env.example` in your local environment or ignored `backend/.env` first.
Use 12–128 character passwords. Seeding is idempotent and restores the configured
roles/passwords when explicitly invoked. It is never called at startup or by
migrations. Never enable or run it in production. Existing accounts do not
require reseeding to sign in.

## Milestone documentation

- [M5 authentication and roles](docs/milestone-5-authentication.md)
- [M6A progress analytics and historical limitations](docs/milestone-6a-progress-analytics.md)
- [M6B progress frontend](docs/milestone-6b-progress-frontend.md)

## Author

Hasanli Toghrul — ELTE Faculty of Informatics internship.
