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
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-workflow-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    log = pathlib.Path(tempfile.mktemp(prefix="webnovel-workflow-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-workflow-worker-", suffix=".log"))
    api = None
    worker = None
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
        worker = subprocess.Popen(
            [sys.executable, "-m", "webnovel.entrypoints.worker.main"],
            cwd=pathlib.Path.cwd(),
            env=env,
            stdout=worker_log.open("w"),
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
                await client.post("/api/v1/works", json={"title": "Workflow", "genre": "悬疑"})
            ).json()
            run = (
                await client.post(
                    f"/api/v1/works/{work['id']}/workflow-runs",
                    json={"template": "outline_to_draft"},
                )
            ).json()
            queued = await client.post(f"/api/v1/workflow-runs/{run['id']}/execute-async")
            print("execute_async:", queued.status_code)
            payload = queued.json()
            for _ in range(240):
                current = (await client.get(f"/api/v1/workflow-runs/{run['id']}")).json()
                if current["artifacts"].get("outline"):
                    payload = current
                    break
                await asyncio.sleep(0.5)
            print("stage:", payload["current_stage"], "status:", payload["status"])
            print("artifact:", str(payload["artifacts"].get("outline", {}))[:100])
            if not payload["artifacts"].get("outline"):
                raise SystemExit(1)
            advanced = await client.post(
                f"/api/v1/workflow-runs/{run['id']}/advance",
                json={"artifact": {"confirmed": True}, "note": "ok"},
            )
            print("advance:", advanced.status_code, advanced.json()["current_stage"])
            auto_run = (
                await client.post(
                    f"/api/v1/works/{work['id']}/workflow-runs",
                    json={"template": "outline_to_draft"},
                )
            ).json()
            queued_all = await client.post(f"/api/v1/workflow-runs/{auto_run['id']}/run-all")
            print("run_all_async:", queued_all.status_code)
            for _ in range(600):
                current = (await client.get(f"/api/v1/workflow-runs/{auto_run['id']}")).json()
                if current["status"] in {"completed", "failed", "cancelled"}:
                    print("run_all_status:", current["status"])
                    print("run_all_stages:", sorted(current["artifacts"]))
                    if current["status"] != "completed":
                        raise SystemExit(1)
                    break
                await asyncio.sleep(0.5)
            else:
                raise SystemExit("run-all timeout")
    except Exception:
        print("api log:\n", log.read_text()[-4000:] if log.exists() else "")
        print("worker log:\n", worker_log.read_text()[-6000:] if worker_log.exists() else "")
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
