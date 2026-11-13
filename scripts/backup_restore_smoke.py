from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import pgserver
from sqlalchemy.ext.asyncio import async_sessionmaker


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-backup-pg-"))
    backup_dir = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-backup-out-"))
    server = pgserver.get_server(pgdata)
    database_url = server.get_uri().replace("postgresql://", "postgresql+asyncpg://")
    pg_bin = pathlib.Path(pgserver.__file__).parent / "pginstall" / "bin"
    path = f"{pg_bin}:{os.environ.get('PATH', '')}"
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "BACKUP_DIR": str(backup_dir),
        "PATH": path,
    }
    os.environ["DATABASE_URL"] = database_url
    os.environ["PATH"] = path
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=pathlib.Path.cwd(),
            env=env,
            check=True,
            capture_output=True,
        )
        from webnovel.infra.config import get_settings

        get_settings.cache_clear()
        from webnovel.infra.db.engine import create_engine
        from webnovel.modules.works.repository import SqlAlchemyWorkRepository
        from webnovel.modules.works.service import WorksService

        engine = create_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session, session.begin():
            await WorksService(SqlAlchemyWorkRepository(session)).create("Backup", "悬疑")
        await engine.dispose()
        subprocess.run(
            [sys.executable, "scripts/backup.py"],
            cwd=pathlib.Path.cwd(),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        dumps = list(backup_dir.glob("*/database.dump"))
        if len(dumps) != 1:
            raise RuntimeError("backup dump not produced")
        base = server.get_uri()
        restore_db = "webnovel_restore"
        subprocess.run(
            ["psql", base, "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {restore_db}"],
            check=True,
            capture_output=True,
            text=True,
        )
        restore_uri = base.replace("/postgres?", f"/{restore_db}?")
        subprocess.run(
            [
                "psql",
                restore_uri,
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "CREATE EXTENSION IF NOT EXISTS vector",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        restored = subprocess.run(
            ["pg_restore", "--no-owner", "--dbname", restore_uri, str(dumps[0])],
            capture_output=True,
            text=True,
        )
        if restored.returncode != 0:
            print("pg_restore stderr:", restored.stderr[-2000:])
            raise SystemExit(restored.returncode)
        count = subprocess.run(
            ["psql", restore_uri, "-tAc", "SELECT count(*) FROM works"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        print("backup_file:", dumps[0].name)
        print("restored_works:", count)
        if count != "1":
            raise SystemExit(1)
    finally:
        server.cleanup()
        shutil.rmtree(pgdata, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
