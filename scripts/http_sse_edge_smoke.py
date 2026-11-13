from __future__ import annotations

import asyncio
import json
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


async def stream(client: httpx.AsyncClient, generation_id: str, last_event_id: int = 0) -> int:
    count = 0
    headers = {"Last-Event-ID": str(last_event_id)} if last_event_id else {}
    async with client.stream(
        "GET", f"/api/v1/generations/{generation_id}/stream", headers=headers
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "delta":
                    count += 1
                if payload.get("type") == "done":
                    break
    return count


async def wait_terminal(client: httpx.AsyncClient, generation_id: str) -> str:
    for _ in range(240):
        current = (await client.get(f"/api/v1/generations/{generation_id}")).json()
        if current["status"] in {"succeeded", "failed", "cancelled", "expired"}:
            return str(current["status"])
        await asyncio.sleep(0.5)
    raise RuntimeError("generation did not become terminal")


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-edge-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    api_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-edge-api-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-edge-worker-", suffix=".log"))
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
                await client.post("/api/v1/works", json={"title": "Edge", "genre": "悬疑"})
            ).json()
            chapter = (
                await client.post(
                    f"/api/v1/works/{work['id']}/chapters",
                    json={"number": 1, "title": "第一章", "content": "雨夜，旧巷。"},
                )
            ).json()
            first = (
                await client.post(
                    f"/api/v1/works/{work['id']}/generations",
                    headers={"Idempotency-Key": "edge-cancel"},
                    json={"chapter_id": chapter["id"], "task_type": "continue"},
                )
            ).json()
            cancelled = await client.post(f"/api/v1/generations/{first['id']}/cancel")
            print("cancel:", cancelled.status_code, cancelled.json().get("status"))
            terminal = await wait_terminal(client, first["id"])
            print("cancel_terminal:", terminal)
            if terminal != "cancelled":
                raise SystemExit(f"expected cancelled, got {terminal}")
            retry_response = await client.post(f"/api/v1/generations/{first['id']}/retry")
            print("retry_response:", retry_response.status_code, retry_response.text[:300])
            retried = retry_response.json()
            print("retry_generation:", retried.get("id"))
            retried_status = await wait_terminal(client, retried["id"])
            print("retry_terminal:", retried_status)
            if retried_status != "succeeded":
                raise SystemExit(f"expected retry succeeded, got {retried_status}")
            replay = await stream(client, retried["id"], last_event_id=10)
            print("reconnect_deltas_after_10:", replay)
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
