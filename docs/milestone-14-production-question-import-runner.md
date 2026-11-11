# M14 — Controlled production question import

`app.scripts.import_verified_dmi_production` is the only intended path for a
separately authorized production import of the existing 52 verified DMI
questions: M10A.3 (23), M10C (14), and M10E (15). It does not replace or relax
the local-only importer, which still refuses any hosted target.

## Preconditions

An operator must use the released backend image and set
`AXIOM_PRODUCTION_IMPORT_DATABASE_URL` only in the restricted release job. It
must use a dedicated least-privileged database credential, rather than the web
application's normal credential. Grant it only the reads needed for
`alembic_version`, `topics`, and `questions`, plus question insertion and its
identity-sequence use; do not grant DDL, update, delete, or application-user
access. An approved backup/recovery-point and restore attestation, and an
Alembic revision of exactly `0017`, are also required. The manifest and every referenced
artifact must reside in one reviewed directory. Its keys must be exactly
`m10a3`, `m10c`, and `m10e`; each path must use the artifact filename required
by the closed registry. The runner validates all artifact adapters and all 52
canonical IDs before it queries the database.

The backup evidence is non-secret JSON with `backup_verified: true`,
`target_host`, `database`, `recovery_point`, and `verified_by`. It is matched
against the configured database but never printed.

## Approval sequence

1. Obtain explicit release-owner approval and a tested backup/restore record.
2. Run the command below **without** `--apply`. Review that every batch has
   zero conflicts/rejections and that the total proposes 52 creates or expected
   idempotent skips.
3. Obtain a second, explicit write approval. Re-run with `--apply` and the
   required write acknowledgement.
4. Record the sanitised report. The runner verifies all external IDs and all
   stored content before its single transaction commits.

```text
python -m app.scripts.import_verified_dmi_production \
  --manifest <reviewed-artifact-directory>/production-import-manifest.json \
  --backup-evidence <reviewed-artifact-directory>/backup-evidence.json \
  --production-import-ack AXIOM_PRODUCTION_IMPORT_INSPECTION_APPROVED
```

For the separately approved write, add:

```text
--apply --production-write-ack AXIOM_PRODUCTION_IMPORT_WRITE_APPROVED
```

The command has no HTTP endpoint, never runs on startup or under Alembic, does
not print database URLs or artifact paths, and rejects local/non-PostgreSQL
targets. Failure during writes or post-import verification rolls back all 52
records. It never updates pre-existing questions; mismatched external IDs stop
the run. A repeat with unchanged artifacts is idempotent.

Do not run this command against production without release-owner authorization.
