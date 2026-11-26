from __future__ import annotations

import os

os.environ["XDG_RUNTIME_DIR"] = "/tmp/wn-studio-xdg"
os.environ["TMPDIR"] = "/tmp/wn-studio-tmp"
os.makedirs("/tmp/wn-studio-xdg", exist_ok=True)
os.makedirs("/tmp/wn-studio-tmp", exist_ok=True)
os.chmod("/tmp/wn-studio-xdg", 0o700)
os.chmod("/tmp/wn-studio-tmp", 0o700)

import pathlib
import subprocess
import sys
import tempfile

import pgserver
import redislite

repo = pathlib.Path(__file__).resolve().parents[1]
pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-studio-pg-", dir="/tmp/wn-studio-tmp"))
server = pgserver.get_server(pgdata)
redis_client = redislite.Redis("/tmp/webnovel-studio.rdb")
redis_path = redis_client.connection_pool.connection_kwargs["path"]
env = {
    **os.environ,
    "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
    "REDIS_URL": f"unix://{redis_path}",
    "LLM_PROVIDER": "fake",
    "LLM_MODEL": "fake",
    "ENABLE_EXPERIMENTS": "true",
    "API_TOKEN": "",
    "RATE_LIMIT_PER_MINUTE": "0",
}
subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", "head"],
    cwd=repo,
    env=env,
    check=True,
)
print("STUDIO_READY http://127.0.0.1:8000/app/studio.html", flush=True)
subprocess.run(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "webnovel.entrypoints.api.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ],
    cwd=repo,
    env=env,
    check=True,
)
