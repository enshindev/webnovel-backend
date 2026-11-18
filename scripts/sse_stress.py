from __future__ import annotations

import asyncio
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time

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


async def stream(client: httpx.AsyncClient, generation_id: str) -> int:
    chunks = 0
    async with client.stream("GET", f"/api/v1/generations/{generation_id}/stream") as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "delta":
                    chunks += 1
                if payload.get("type") == "done":
                    break
    return chunks


async def wait_visible(client: httpx.AsyncClient, path: str, label: str) -> None:
    for _ in range(40):
        response = await client.get(path)
        if response.status_code == 200:
            return
        await asyncio.sleep(0.05)
    raise RuntimeError(f"{label} not visible after create: {response.status_code}")


async def main() -> None:
    total = 8
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-stress-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
        "LLM_PROVIDER": "fake",
        "LLM_MODEL": "fake",
    }
    port = free_port()
    api_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-stress-api-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-stress-worker-", suffix=".log"))
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
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=300) as client:
            await wait_health(client)

            def payload(response: httpx.Response, action: str) -> dict[str, object]:
                if response.status_code >= 400:
                    raise RuntimeError(f"{action} failed: {response.status_code} {response.text}")
                return response.json()

            work = payload(
                await client.post("/api/v1/works", json={"title": "Stress", "genre": "悬疑"}),
                "create work",
            )
            await wait_visible(client, f"/api/v1/works/{work['id']}", "work")
            generation_ids: list[str] = []
            for index in range(total):
                chapter = payload(
                    await client.post(
                        f"/api/v1/works/{work['id']}/chapters",
                        json={
                            "number": index + 1,
                            "title": f"第{index + 1}章",
                            "content": "旧巷。",
                        },
                    ),
                    f"create chapter {index + 1}",
                )
                await wait_visible(client, f"/api/v1/chapters/{chapter['id']}", "chapter")
                generation = payload(
                    await client.post(
                        f"/api/v1/works/{work['id']}/generations",
                        headers={"Idempotency-Key": f"stress-{index}"},
                        json={"chapter_id": chapter["id"], "task_type": "continue"},
                    ),
                    f"create generation {index + 1}",
                )
                generation_ids.append(str(generation["id"]))
            started = time.monotonic()
            results = await asyncio.gather(
                *(stream(client, generation_id) for generation_id in generation_ids)
            )
            elapsed = time.monotonic() - started
            statuses = []
            for generation_id in generation_ids:
                statuses.append(
                    (await client.get(f"/api/v1/generations/{generation_id}")).json()["status"]
                )
            print("generations:", total)
            print("deltas:", sum(results), "min:", min(results), "max:", max(results))
            print("elapsed_seconds:", round(elapsed, 2))
            print("statuses:", statuses)
            if set(statuses) != {"succeeded"}:
                raise SystemExit(1)
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
