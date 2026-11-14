from __future__ import annotations

from pathlib import Path

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
def eval_suite(suite: str = "smoke", outputs: Path | None = None) -> None:
    """跑本地评测集并写入 eval_runs。"""
    import asyncio
    import json

    from webnovel.evalkit.cases import load_cases
    from webnovel.evalkit.judge import judge_output
    from webnovel.evalkit.summary import summarize
    from webnovel.infra.config import get_settings
    from webnovel.infra.db.session import session_factory
    from webnovel.modules.quality.eval_repository import SqlAlchemyEvalRepository
    from webnovel.modules.quality.eval_service import EvalService

    settings = get_settings()
    loaded = load_cases(settings.evals_dir, suite=suite)
    cases = [{"id": case.spec.id, "must_pass": case.spec.must_pass} for case in loaded]
    must_pass_ids = {case.spec.id for case in loaded if case.spec.must_pass}

    outputs_map: dict[str, str] = {}
    if outputs is not None:
        for line in outputs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                outputs_map[str(row["id"])] = str(row.get("output", ""))

    async def run() -> tuple[str, dict[str, object]]:
        async with session_factory() as session, session.begin():
            service = EvalService(SqlAlchemyEvalRepository(session))
            params = {"source": "cli", "suite": suite, "cases": len(cases)}
            if outputs is None:
                run_id, metrics = await service.run(task=suite, cases=cases, params=params)
                return str(run_id), metrics
            results = [
                judge_output(case.spec, outputs_map.get(case.spec.id, "")) for case in loaded
            ]
            run_id, metrics = await service.run(
                task=suite, cases=cases, params=params, results=results
            )
            summary = summarize(results, must_pass_ids)
            return str(run_id), {**metrics, **summary}

    run_id, metrics = asyncio.run(run())
    if outputs is None:
        typer.echo(
            f"eval run_id={run_id} cases={metrics['total']} "
            f"must_pass={metrics['must_pass_total']} (inventory only; pass --outputs to score)"
        )
        return
    typer.echo(
        f"eval run_id={run_id} total={metrics['total']} passed={metrics['passed']} "
        f"must_pass={metrics['must_pass_passed']}/{metrics['must_pass_total']} "
        f"gate={metrics['gate']}"
    )
    if metrics["gate"] == "failed":
        raise typer.Exit(code=1)


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
