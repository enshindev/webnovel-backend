from __future__ import annotations

import typer
import uvicorn

app = typer.Typer(no_args_is_help=True, help="Webnovel backend CLI")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """启动 API。"""
    uvicorn.run(
        "webnovel.entrypoints.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def worker() -> None:
    """启动 arq worker。"""
    from webnovel.entrypoints.worker.main import main as run

    run()


@app.command("eval")
def eval_suite(suite: str = "smoke") -> None:
    """跑本地评测集并写入 eval_runs。"""
    import asyncio
    import json

    from webnovel.infra.config import get_settings
    from webnovel.infra.db.session import session_factory
    from webnovel.modules.quality.eval_repository import SqlAlchemyEvalRepository
    from webnovel.modules.quality.eval_service import EvalService

    async def run() -> None:
        settings = get_settings()
        cases: list[dict[str, object]] = []
        for path in settings.evals_dir.rglob("cases.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    case = json.loads(line)
                    case["id"] = str(case.get("id", f"{path.stem}-{len(cases)}"))
                    cases.append(case)
        async with session_factory() as session, session.begin():
            run_id = await EvalService(SqlAlchemyEvalRepository(session)).run(
                task=suite,
                cases=cases,
                params={"source": "cli", "cases": len(cases)},
            )
        typer.echo(f"eval run_id={run_id} cases={len(cases)}")

    asyncio.run(run())


@app.command("prompt-sync")
def prompt_sync() -> None:
    """把根级 prompts/ 同步到 prompt_versions / prompt_labels 目录表。"""
    import asyncio

    from webnovel.infra.config import get_settings
    from webnovel.infra.db.session import session_factory
    from webnovel.modules.prompts.repository import SqlAlchemyPromptCatalogRepository
    from webnovel.modules.prompts.service import PromptCatalogService

    async def run() -> None:
        async with session_factory() as session, session.begin():
            counts = await PromptCatalogService(SqlAlchemyPromptCatalogRepository(session)).sync(
                get_settings().prompts_dir
            )
        typer.echo(f"prompt-sync versions={counts['versions']} labels={counts['labels']}")

    asyncio.run(run())


@app.command()
def bench(model: str | None = None) -> None:
    """跑一次最小模型延迟基线；完整 TTFT/吞吐基准后续扩展。"""
    import asyncio
    import time

    from webnovel.infra.config import get_settings
    from webnovel.kernel.ports.llm import ChatMessage, ModelRequest
    from webnovel.llm.gateway.factory import build_model_client

    async def run() -> None:
        settings = get_settings()
        started = time.perf_counter()
        client = build_model_client(settings)
        text = await client.complete(
            ModelRequest(
                model=model or settings.llm_model,
                messages=[ChatMessage(role="user", content="用一句话说明你好。")],
                max_tokens=64,
            )
        )
        elapsed = time.perf_counter() - started
        typer.echo(
            f"model={model or settings.llm_model} "
            f"latency_seconds={elapsed:.3f} output={text[:80]!r}"
        )

    asyncio.run(run())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
