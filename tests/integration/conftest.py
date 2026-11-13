from __future__ import annotations

import pathlib
import tempfile

import pytest


@pytest.fixture(scope="session")
def postgres_url():
    pgserver = pytest.importorskip("pgserver")
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-pg-"))
    server = pgserver.get_server(pgdata)
    yield server.get_uri().replace("postgresql://", "postgresql+asyncpg://")
    server.cleanup()


@pytest.fixture(scope="session")
def redis_url():
    redislite = pytest.importorskip("redislite")
    client = redislite.Redis()
    path = client.connection_pool.connection_kwargs["path"]
    yield f"unix://{path}"
    client.shutdown()
