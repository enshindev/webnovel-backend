from __future__ import annotations

import asyncio
import os
import pathlib
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
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-approval-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    api_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-approval-api-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-approval-worker-", suffix=".log"))
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
            for _ in range(120):
                try:
                    if (await client.get("/health")).status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            run = (
                await client.post(
                    "/api/v1/agent/runs",
                    json={"goal": "给一个一句话的悬疑开头", "experiment": "assistant"},
                )
            ).json()
            approval_response = await client.post(
                f"/api/v1/agent/runs/{run['id']}/approvals",
                json={"action": "publish", "payload": {"chapter": 1}},
            )
            print("approval_http:", approval_response.status_code, approval_response.text[:300])
            approval = approval_response.json()
            print("approval_request:", approval["status"], len(approval["pending_approvals"]))
            if not approval["pending_approvals"]:
                raise SystemExit("no pending approval")
            approval_id = approval["pending_approvals"][0]["id"]
            decided = (
                await client.post(
                    f"/api/v1/agent/runs/{run['id']}/approvals/{approval_id}",
                    json={"decision": "approve"},
                )
            ).json()
            print("approval_decide:", decided["status"])
            for _ in range(240):
                current = (await client.get(f"/api/v1/agent/runs/{run['id']}")).json()
                if current["status"] in {"succeeded", "failed"}:
                    print("agent_status:", current["status"])
                    print("approval_status:", current["pending_approvals"][0]["status"])
                    if current["status"] == "failed":
                        raise SystemExit(1)
                    return
                await asyncio.sleep(0.5)
            raise RuntimeError("agent did not finish after approval")
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
        import shutil

        shutil.rmtree(pgdata, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
