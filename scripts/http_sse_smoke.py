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
            response = await client.get("/health")
            if response.status_code == 200:
                return
        except Exception:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("API did not become healthy")


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-http-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
    }
    port = free_port()
    api_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-api-", suffix=".log"))
    worker_log = pathlib.Path(tempfile.mktemp(prefix="webnovel-worker-", suffix=".log"))
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
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=120) as client:
            await wait_health(client)
            work = (
                await client.post("/api/v1/works", json={"title": "HTTP SSE", "genre": "悬疑"})
            ).json()
            chapter = (
                await client.post(
                    f"/api/v1/works/{work['id']}/chapters",
                    json={"number": 1, "title": "雨夜", "content": "旧巷里第二声钟响。"},
                )
            ).json()
            generation = (
                await client.post(
                    f"/api/v1/works/{work['id']}/generations",
                    headers={"Idempotency-Key": "http-sse-1"},
                    json={"chapter_id": chapter["id"], "task_type": "continue"},
                )
            ).json()
            generation_id = generation["id"]
            print("generation:", generation_id)
            deltas: list[str] = []
            async with client.stream(
                "GET", f"/api/v1/generations/{generation_id}/stream"
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        payload = json.loads(line[6:])
                        if payload.get("type") == "delta":
                            deltas.append(str(payload.get("text", "")))
                        if payload.get("type") == "done":
                            break
            print("sse_deltas:", len(deltas), "chars:", sum(len(v) for v in deltas))
            final = (await client.get(f"/api/v1/generations/{generation_id}")).json()
            print("status:", final["status"], "draft:", final.get("draft_id"))
            if final["status"] != "succeeded":
                raise SystemExit(1)
            draft = (await client.get(f"/api/v1/drafts/{final['draft_id']}")).json()
            print("draft_prefix:", draft["content"][:60])
            prompt = (await client.get(f"/api/v1/generations/{generation_id}/prompt")).json()
            print("prompt_snapshot:", bool(prompt.get("snapshot")))
            print("context_snapshot:", bool(prompt.get("context_snapshot")))
            accepted = await client.post(
                f"/api/v1/drafts/{final['draft_id']}/accept",
                json={"base_version": chapter["lock_version"]},
            )
            print("accept:", accepted.status_code, accepted.text[:200])
            usage = (await client.get(f"/api/v1/works/{work['id']}/usage")).json()
            print("usage_entries:", len(usage["items"]))
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
