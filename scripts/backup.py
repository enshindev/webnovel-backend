from __future__ import annotations

import os
import pathlib
import subprocess
import tarfile
from datetime import UTC, datetime

from webnovel.infra.config import get_settings


def main() -> None:
    settings = get_settings()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = pathlib.Path(os.getenv("BACKUP_DIR", "backups")) / stamp
    out.mkdir(parents=True, exist_ok=True)
    database_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    db_file = out / "database.dump"
    subprocess.run(
        ["pg_dump", "--format=custom", "--file", str(db_file), database_url],
        check=True,
    )
    data_file = out / "data.tar.gz"
    with tarfile.open(data_file, "w:gz") as archive:
        for path in (settings.library_dir, settings.export_dir):
            if path.exists():
                archive.add(path, arcname=path.name)
    print(f"backup: {out}")
    print(f"database: {db_file}")
    print(f"data: {data_file}")


if __name__ == "__main__":
    main()
