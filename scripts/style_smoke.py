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
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-style-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    log = pathlib.Path(tempfile.mktemp(prefix="webnovel-style-", suffix=".log"))
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
            work = (
                await client.post("/api/v1/works", json={"title": "Style", "genre": "悬疑"})
            ).json()
            chapter = (
                await client.post(
                    f"/api/v1/works/{work['id']}/chapters",
                    json={
                        "number": 1,
                        "title": "雨夜",
                        "content": (
                            "雨落在旧巷，沈砚把伞收了，水珠顺着伞骨滴下来。"
                            "他没有说话，只听见远处的钟声。"
                        ),
                    },
                )
            ).json()
            profile_response = await client.post(
                f"/api/v1/works/{work['id']}/style-profiles",
                json={"chapter_ids": [chapter["id"]]},
            )
            print("profile_status:", profile_response.status_code)
            profile = profile_response.json()
            print("profile_summary:", str(profile.get("summary", ""))[:100])
            rewrite = await client.post(
                f"/api/v1/works/{work['id']}/style-profiles/{profile['id']}/rewrite",
                json={"content": "他走进巷子，雨很大。"},
            )
            print("rewrite_status:", rewrite.status_code)
            payload = rewrite.json()
            print("rewrite_prefix:", str(payload.get("content", ""))[:100])
            print("check_score:", payload.get("check", {}).get("score"))
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
