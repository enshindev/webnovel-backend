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


async def main() -> None:
    pgdata = pathlib.Path(tempfile.mkdtemp(prefix="webnovel-assistant-pg-"))
    server = pgserver.get_server(pgdata)
    redis_client = redislite.Redis()
    redis_path = redis_client.connection_pool.connection_kwargs["path"]
    env = {
        **os.environ,
        "DATABASE_URL": server.get_uri().replace("postgresql://", "postgresql+asyncpg://"),
        "REDIS_URL": f"unix://{redis_path}",
        "ASSISTANT_ENABLED": "true",
    }
    port = free_port()
    log = pathlib.Path(tempfile.mktemp(prefix="webnovel-assistant-", suffix=".log"))
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
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=180) as client:
            for _ in range(120):
                try:
                    if (await client.get("/health")).status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            conversation = (
                await client.post(
                    "/api/v1/experiments/assistant/conversations",
                    json={"scope": "ideation", "mode": "world", "title": "真实模型测试"},
                )
            ).json()
            print("conversation:", conversation["id"])
            deltas: list[str] = []
            async with client.stream(
                "POST",
                f"/api/v1/experiments/assistant/conversations/{conversation['id']}/messages/stream",
                json={"content": "用一句话给我一个悬疑小说的开场。"},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        payload = json.loads(line[6:])
                        if "text" in payload:
                            deltas.append(str(payload["text"]))
            print("assistant_deltas:", len(deltas), "chars:", sum(len(v) for v in deltas))
            print("assistant_prefix:", "".join(deltas)[:80])
            messages = (
                await client.get(
                    f"/api/v1/experiments/assistant/conversations/{conversation['id']}/messages"
                )
            ).json()
            print("message_count:", len(messages["items"]))
            if not deltas or len(messages["items"]) < 2:
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
