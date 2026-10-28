# AXIOM — Final Academic Project Handover

**Author:** Toghrul Hasanli. **Context:** academic internship, ELTE Faculty of Informatics, Discrete Mathematics I. **Documentation review:** 28 October 2026, application baseline `75ede6a` plus documentation changes. AXIOM is not an officially endorsed ELTE production system.

## Purpose and delivered scope

AXIOM supports reuse of Discrete Mathematics I questions, student practice and feedback, and preparation of recurring assessment information. Implemented scope through M9 includes:

- Authentication, verified Student registration, server-side sessions, CSRF, role-based access and protected operator accounts.
- Structured Question Bank with topic hierarchy, response types, skills, problem sets and suitability classifications.
- Quiz composition, Student-owned attempts, Unicode mathematical input, automatic objective checks, submission and solution review.
- Personal progress overview, topic/skill breakdowns and recent attempts; automatic practice accuracy excludes written responses.
- Staff manual grading and feedback on submitted written answers.
- Semester assessment configuration, policies, schedules, writing/arrival times, room/group assignments and group-specific coursework deadlines.
- Seven academic LaTeX templates, live HTML Draft Preview and bounded real PDF generation. Downloads require relevant edits to be saved in the UI.
- AXIOM Design v1 and role-specific navigation.

## Technology and operations

Next.js/TypeScript/Tailwind CSS frontend; FastAPI/Pydantic backend; PostgreSQL with SQLAlchemy/Psycopg and Alembic; Tectonic 0.15.0 with pinned offline resources. Owner-reported hosting is Vercel → Render container → Neon, with GHCR images and Brevo HTTPS verification email. The reported frontend is [AXIOM](https://axiom-orcin-xi.vercel.app/) and the API is [AXIOM API](https://axiom-api-te6o.onrender.com/). Hosting availability, deployed image digest and live schema revision were not independently inspected in this documentation task.

## Verification evidence and its limits

| Evidence                                                                 | Meaning                                                                                                                                                                                |
| ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Owner reports 242 backend tests passed, including PostgreSQL integration | Historical result; raw log/date/release association should be retained by the owner. Not a new test run.                                                                               |
| Alembic source chain ends at 0012                                        | Confirmed from migration files; not proof of the current production revision.                                                                                                          |
| M9D.2C local image measurements                                          | Seven PDFs passed offline at 0.1 CPU/512 MiB; image about 439 MiB, peak container memory 264 MiB, compilation 7.5–8.1 s. Includes an extra test driver, not production classroom load. |
| Current documentation review                                             | Routes, permissions, schemas, frontend source/workflows, environment names, migrations, Dockerfile and test structure reviewed. No browser or production acceptance test.              |
| Documentation QA                                                         | Markdown formatting, local link targets, credential-pattern review and `git diff --check`; see the accompanying completion report for executed results.                                |

No application test count is claimed as newly passed by this documentation-only task. Before operational acceptance, record the exact release commit, image digest, migration revision, test logs and a supervisor-approved live smoke-test result.

## Documentation index

| Document                                                                         | Audience/purpose                                                 |
| -------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| [Root README](../README.md)                                                      | Project scope, quick setup, attribution and status               |
| [Lecturer user guide](user-guide.md)                                             | Actual navigation and supported workflows                        |
| [Developer handover](developer-handover.md)                                      | Architecture, invariants, tests and maintenance                  |
| [Production deployment](production-deployment.md)                                | Environment, GHCR, release order, recovery and troubleshooting   |
| [Backend README](../backend/README.md), [frontend README](../frontend/README.md) | Component setup and contracts                                    |
| [Progress definitions](milestone-6a-progress-analytics.md)                       | Meaning and limits of analytics                                  |
| [Manual grading](milestone-7a-manual-grading.md)                                 | Grading contract and behavior                                    |
| [Template foundation](milestone-9c-latex-rendering.md)                           | Shared document data and unresolved academic wording             |
| [Container evidence](milestone-9d2c-render-compatibility.md)                     | Local compiler/resource measurements and historical rollout plan |

Other milestone documents remain historical records. Early requirements/MVP/roadmap files record original intent; they are not current feature promises. Current guides take precedence where a later implementation changed behavior, notably saved-only PDF downloading.

## Known limitations and optional improvements

Exam Builder, Practice Sheet Generator, Question Generator, general LaTeX/PDF Tools, Course Materials, AI/variant generation and advanced visualizations are not delivered features. Learn is a course outline; the notification menu is a placeholder. There is no password reset, MFA, distributed rate limiter, persistent PDF job queue, full grade-change history or group-scoped grading. Student Progress remains personal, not a staff cohort dashboard. Free-hosting availability and memory limits prevent a reliability guarantee for classroom-scale simultaneous usage.

Academic confirmation remains required for source conflicts: Endterm arrival 10:05 versus 16:05; last versus penultimate coursework class; plus-point eligibility/total wording; fractional grade thresholds; retake wording and seating instructions. Review the full template notes before distributing course documents. Documentation does not resolve these policies on the professor's behalf.

Optional next work should prioritize an agreed monitoring/backup process, recovery rehearsal, load testing, accessibility/usability feedback, dependency maintenance and account recovery before additional features. No public software license is currently present; code reuse and course-content permissions need explicit agreement.

## Acceptance and ownership checklist

- Supervisor and author agree delivered scope, academic wording and whether/when students may rely on the service.
- Identify a primary maintainer, backup operator, incident contact and funding/billing owner.
- Transfer repository and GHCR package permissions, Render/Vercel access, Neon administration and Brevo sender/account ownership through provider access controls, with MFA and recovery arrangements.
- Record approved image/resource digests and preserve the Tectonic cache artifact. A clean clone alone cannot retrieve the local-only default resource image.
- Confirm live migration revision, deployment commit and HTTPS/cookie/origin/email configuration; do not store secret values in the handover documents.
- Agree retention/deletion/export rules for student identities, answers, grades and backups, and responsibility for access requests and incident handling.
- Verify a recoverable backup, recovery objectives and an isolated restore rehearsal. Agree who may authorize migrations, publication and rollback.
- Preserve historical evidence and exclude `README.backup.md`, local environments, generated output, database exports and credentials from commits.

Completion of source/documentation delivery is separate from operational acceptance. The named decisions and access transfer remain the service owner's and supervisor's responsibilities.
