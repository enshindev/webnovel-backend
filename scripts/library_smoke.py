from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile

import httpx
import pgserver
import redislite


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-library-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    log = pathlib.Path(tempfile.mktemp(prefix="webnovel-library-", suffix=".log"))
    api = None
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=pathlib.Path.cwd(),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "webnovel.entrypoints.api.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=pathlib.Path.cwd(),
            env=env,
            stdout=log.open("w"),
            stderr=subprocess.STDOUT,
        )
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=240) as client:
            for _ in range(120):
                try:
                    if (await client.get("/health")).status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            collection = (
                await client.post(
                    "/api/v1/experiments/library/collections",
                    json={"name": "民国资料"},
                )
            ).json()
            print("collection:", collection["id"])
            upload = await client.post(
                "/api/v1/experiments/library/documents",
                data={"collection_id": collection["id"]},
                files={
                    "file": (
                        "notes.txt",
                        "旧巷的灯在雨夜熄灭，守灯人知道地下入口的位置。".encode(),
                        "text/plain",
                    )
                },
            )
            print("upload:", upload.status_code)
            document = upload.json()
            print("document_status:", document.get("status"))
            search = await client.post(
                "/api/v1/experiments/library/search",
                json={"query": "旧巷的灯", "limit": 5},
            )
            print("search:", search.status_code)
            chunks = search.json().get("chunks", [])
            print("chunk_count:", len(chunks))
            print("top_text:", str(chunks[0].get("text", ""))[:80] if chunks else "none")
            if not chunks:
                raise SystemExit(1)
    except Exception:
        print("api log:\n", log.read_text()[-4000:] if log.exists() else "")
        raise
    finally:
        if api is not None:
            api.terminate()
            try:
                api.wait(timeout=10)
            except subprocess.TimeoutExpired:
                api.kill()
        redis_client.shutdown()
        server.cleanup()
        shutil.rmtree(pgdata, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
