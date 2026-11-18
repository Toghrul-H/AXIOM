# M20 Course Materials — local release status

## Verified locally

M20 adds additive Alembic revision 0028_course_materials after 0027. It stores
Course Material metadata only; it does not rewrite existing users, questions,
quizzes, Course chapters, or lessons.

The local implementation validates supported PDF, Office, image and text
uploads before storage; stores a SHA-256 checksum and an opaque Google Drive
file ID; serves authorized reads through the API; and never creates public Drive
links or returns provider URLs to students. Student access requires a published
material under published Course content.

Verified local evidence:

- isolated PostgreSQL 0027 → 0028 → 0027 migration rehearsal;
- real private Google Drive folder access, TXT upload, byte-for-byte download,
  and deletion;
- disposable-schema API workflow covering staff upload, parent-publication
  gating, student isolation, authorization, safe download headers, notification
  deduplication, and cleanup;
- pytest tests/test_course.py tests/test_course_materials.py -q: 13 passed,
  2 skipped.

No production database, Drive object, Render service, or Vercel deployment was
changed by this work.

## Release gates

1. **Google Cloud:** In Google Cloud Console, open **Google Auth Platform →
   Audience** and change the External app publishing status from **Testing** to
   **In production** using **Publish app**. The only requested scope is
   drive.file. Testing refresh tokens expire after seven days; after
   publication, run the local authorization helper again to obtain a
   replacement production refresh token. Do not reuse a Testing-issued token.
2. **Render:** configure only secret values through Render's secret UI:

       MATERIALS_STORAGE_PROVIDER=google_drive
       MATERIALS_GOOGLE_DRIVE_FOLDER_ID=<dedicated private folder ID>
       MATERIALS_GOOGLE_DRIVE_TOKEN_JSON=<complete OAuth token JSON secret>
       MATERIALS_MAX_UPLOAD_BYTES=25000000

   Leave MATERIALS_GOOGLE_DRIVE_TOKEN_FILE unset in Render. The folder must
   remain private and owned by the dedicated AXIOM Google account. Do not set
   public sharing permissions.
3. **Database:** obtain/verify an approved Neon recovery point and isolated
   restore evidence; record the live revision; use an approved migration runner
   to apply alembic upgrade 0028; confirm alembic current is 0028.
4. **Images:** build and test a new immutable API image because
   requirements.txt now includes the Google API client libraries. The existing
   Dockerfile installs that file and requires no other M20 Docker change.
5. **Smoke test:** after backend deployment, use a non-sensitive staff test
   account and a disposable test material to verify create/upload, draft
   isolation, publish, student preview/download, notification, and deletion.

## Rollback

0028 is additive. Prefer rolling back the backend/frontend image while leaving
the schema in place. Normal staff deletion removes the AXIOM metadata and first
attempts the owned private Drive object deletion. If Drive deletion fails, the
metadata is retained; if the database commit fails after a successful Drive
deletion, retrying deletion reconciles the retained metadata because a missing
object is treated as already cleaned up. Do not downgrade 0028 after material
data exists without a reviewed recovery plan: the downgrade drops material
metadata but cannot delete private Drive files that were not successfully
removed.
