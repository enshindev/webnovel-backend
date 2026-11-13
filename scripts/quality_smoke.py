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


async def wait_health(client: httpx.AsyncClient) -> None:
    for _ in range(120):
        try:
            if (await client.get("/health")).status_code == 200:
                return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("API did not become healthy")


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-quality-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    api_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-quality-api-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-quality-worker-", suffix=".log"))
    api = worker = None
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
            stdout=api_log.open("w"),
            stderr=subprocess.STDOUT,
        )
        worker = subprocess.Popen(
            [sys.executable, "-m", "webnovel.entrypoints.worker.main"],
            cwd=pathlib.Path.cwd(),
            env=env,
            stdout=worker_log.open("w"),
            stderr=subprocess.STDOUT,
        )
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=240) as client:
            await wait_health(client)
            work = (
                await client.post("/api/v1/works", json={"title": "Quality", "genre": "悬疑"})
            ).json()
            chapter = (
                await client.post(
                    f"/api/v1/works/{work['id']}/chapters",
                    json={
                        "number": 1,
                        "title": "雨夜",
                        "content": (
                            "沈砚站在旧巷口。雨很大，他没有伞，却一点也不湿。"
                            "他看见远处的灯灭了，于是决定明天再去查看。"
                        ),
                    },
                )
            ).json()
            review = await client.post(
                f"/api/v1/works/{work['id']}/quality-reviews",
                json={"chapter_id": chapter["id"]},
            )
            print("review_create:", review.status_code)
            report = review.json()
            for _ in range(240):
                current = (await client.get(f"/api/v1/quality-reports/{report['id']}")).json()
                if current["status"] not in {"queued", "running"}:
                    print("review_status:", current["status"])
                    print("review_score:", current["score"])
                    print("issue_count:", len(current["issues"]))
                    usage = (await client.get(f"/api/v1/works/{work['id']}/usage")).json()
                    print("usage_entries:", len(usage["items"]))
                    overview = (await client.get("/api/v1/usage/overview")).json()
                    print("overview_calls:", overview["summary"]["calls"])
                    print("overview_cost:", overview["summary"]["cost"])
                    if current["status"] == "failed":
                        raise SystemExit(1)
                    return
                await asyncio.sleep(0.5)
            raise RuntimeError("quality review did not finish")
    except Exception:
        print("api log:\n", api_log.read_text()[-3000:] if api_log.exists() else "")
        print("worker log:\n", worker_log.read_text()[-5000:] if worker_log.exists() else "")
        raise
    finally:
        for process in (api, worker):
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
        redis_client.shutdown()
        server.cleanup()
        shutil.rmtree(pgdata, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
