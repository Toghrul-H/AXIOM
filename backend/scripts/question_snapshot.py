"""Save a local, ignored pre-migration snapshot without exposing credentials."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.database import get_engine


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / ".local-backups"
    directory.mkdir(exist_ok=True)
    with get_engine().connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        rows = [dict(row) for row in connection.execute(text("SELECT * FROM questions ORDER BY id")).mappings()]
    path = directory / f"questions-{revision}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json"
    path.write_text(json.dumps({"revision": revision, "questions": rows}, default=str, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} questions at revision {revision} to {path}")
    for row in rows:
        print({key: row[key] for key in ("id", "topic", "question_type") if key in row})


if __name__ == "__main__":
    main()
