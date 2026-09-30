# M6B — Student Progress Frontend

The Student Dashboard and `/student/progress` consume the authenticated
`GET /student/progress/me` response. No user ID is sent and no analytics are
recomputed in the frontend. M6A defines all metrics.

The dashboard shows overview metrics, seven topics and five recent completed
attempts. The detailed page adds completed-attempt counts, eight skills and the
latest ten completed attempts. Review links use the existing attempt review route.

Null accuracy displays “No data”; written responses are not marked incorrect.
Empty history links to quizzes. Loading and retryable errors do not fabricate
zeros. Missing historical metadata is explained using M6A unattributed counts.

AXIOM Design v1, session authentication and role restrictions are preserved.
No backend or schema changes. Focused rendering checks covered empty, objective,
null, ungraded and mixed histories, review links, loading and errors. ESLint,
TypeScript and production build passed. No browser automation was performed.
