from __future__ import annotations

from pathlib import Path
from typing import Any

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
def eval_suite(
    suite: str = "smoke",
    outputs: Path | None = None,
    prompt_id: str | None = None,
    prompt_version: int | None = None,
    run_model: bool = typer.Option(False, "--run/--no-run", help="直接调用模型生成输出"),
    limit: int | None = None,
    save_outputs: Path | None = None,
) -> None:
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

    if (prompt_id is None) != (prompt_version is None):
        typer.echo("--prompt-id and --prompt-version must be used together", err=True)
        raise typer.Exit(code=2)
    if run_model and outputs is not None:
        typer.echo("--run and --outputs cannot be used together", err=True)
        raise typer.Exit(code=2)
    if run_model and (prompt_id is None or prompt_version is None):
        typer.echo("--run requires --prompt-id and --prompt-version", err=True)
        raise typer.Exit(code=2)
    if save_outputs is not None and not run_model:
        typer.echo("--save-outputs is only valid with --run", err=True)
        raise typer.Exit(code=2)
    if limit is not None and limit < 1:
        typer.echo("--limit must be positive", err=True)
        raise typer.Exit(code=2)

    settings = get_settings()
    loaded = load_cases(settings.evals_dir, suite=suite)
    if prompt_id is not None:
        loaded = [case for case in loaded if f"{case.module}/{case.task}" == prompt_id]
        if not loaded:
            typer.echo(f"no eval cases found for prompt {prompt_id}", err=True)
            raise typer.Exit(code=1)
    if limit is not None:
        loaded = loaded[:limit]
    cases = [{"id": case.spec.id, "must_pass": case.spec.must_pass} for case in loaded]
    must_pass_ids = {case.spec.id for case in loaded if case.spec.must_pass}

    outputs_map: dict[str, str] = {}
    if outputs is not None:
        for line in outputs.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                outputs_map[str(row["id"])] = str(row.get("output", ""))

    async def record(results: list[dict[str, object]] | None) -> tuple[str, dict[str, object]]:
        async with session_factory() as session, session.begin():
            service = EvalService(SqlAlchemyEvalRepository(session))
            params = {
                "source": "cli",
                "suite": suite,
                "cases": len(cases),
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "run_model": run_model,
                "limit": limit,
            }
            run_id, metrics = await service.run(
                task=suite,
                cases=cases,
                prompt_name=prompt_id,
                prompt_version=prompt_version,
                params=params,
                results=results,
            )
            return str(run_id), metrics

    if run_model:
        from webnovel.evalkit.model_eval import ModelEvalResult, run_cases
        from webnovel.llm.gateway.factory import build_model_client
        from webnovel.llm.prompts.registry import PromptRegistry

        registry = PromptRegistry(settings.prompts_dir)
        try:
            prompt = registry.load_version(prompt_id or "", prompt_version or 0)
            includes = registry.load_includes(prompt)
        except (FileNotFoundError, ValueError) as exc:
            typer.echo(f"prompt load failed: {exc}", err=True)
            raise typer.Exit(code=2) from exc

        async def generate() -> list[ModelEvalResult]:
            client = build_model_client(settings, profile="batch")
            return await run_cases(
                loaded,
                client=client,
                model=settings.llm_model,
                prompt=prompt,
                includes=includes,
                limit=limit,
                progress=lambda index, total, case_id: typer.echo(
                    f"[{index}/{total}] {case_id}", err=True
                ),
            )

        generated = asyncio.run(generate())
        if save_outputs is not None:
            lines = [
                json.dumps({"id": item.case_id, "output": item.output}, ensure_ascii=False)
                for item in generated
            ]
            save_outputs.write_text("\n".join(lines) + "\n", encoding="utf-8")
        results = [item.result for item in generated]
        summary = summarize(results, must_pass_ids)
        run_id, metrics = asyncio.run(record([*results]))
        merged = {**metrics, **summary}
        typer.echo(
            f"eval run_id={run_id} total={merged['total']} passed={merged['passed']} "
            f"must_pass={merged['must_pass_passed']}/{merged['must_pass_total']} "
            f"gate={merged['gate']}"
        )
        if merged["gate"] == "failed":
            raise typer.Exit(code=1)
        return

    if outputs is None:
        run_id, metrics = asyncio.run(record(None))
        typer.echo(
            f"eval run_id={run_id} cases={metrics['total']} "
            f"must_pass={metrics['must_pass_total']} (inventory only; pass --outputs or --run)"
        )
        return

    results = [judge_output(case.spec, outputs_map.get(case.spec.id, "")) for case in loaded]
    summary = summarize(results, must_pass_ids)
    run_id, metrics = asyncio.run(record(results))
    merged = {**metrics, **summary}
    typer.echo(
        f"eval run_id={run_id} total={merged['total']} passed={merged['passed']} "
        f"must_pass={merged['must_pass_passed']}/{merged['must_pass_total']} "
        f"gate={merged['gate']}"
    )
    if merged["gate"] == "failed":
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


@app.command("prompt-promote")
def prompt_promote(
    prompt_id: str,
    version: int,
    label: str = "production",
    eval_run_id: str | None = None,
    note: str = "",
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """跑过评测后把 label 指向新 prompt 版本。"""
    import asyncio
    import uuid

    from webnovel.infra.config import get_settings
    from webnovel.infra.db.session import session_factory
    from webnovel.llm.prompts.registry import PromptRegistry
    from webnovel.modules.audit.repository import SqlAlchemyAuditRepository
    from webnovel.modules.audit.service import AuditServiceImpl
    from webnovel.modules.prompts.promotion import promote_label
    from webnovel.modules.prompts.repository import SqlAlchemyPromptCatalogRepository
    from webnovel.modules.prompts.service import PromptCatalogService
    from webnovel.modules.quality.eval_repository import SqlAlchemyEvalRepository

    settings = get_settings()
    try:
        PromptRegistry(settings.prompts_dir).load_version(prompt_id, version)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"prompt version check failed: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    run_id: uuid.UUID | None = None
    if eval_run_id is not None:
        try:
            run_id = uuid.UUID(eval_run_id)
        except ValueError as exc:
            typer.echo(f"invalid eval run id: {eval_run_id}", err=True)
            raise typer.Exit(code=2) from exc

    run: dict[str, Any] | None = None
    if not force:

        async def load_run() -> dict[str, Any] | None:
            async with session_factory() as session:
                repository = SqlAlchemyEvalRepository(session)
                if run_id is not None:
                    return await repository.get_run(run_id)
                return await repository.latest_run(prompt_id, version)

        run = asyncio.run(load_run())
        if run is None:
            typer.echo(
                "no eval run found for this prompt version; run eval first or use --force",
                err=True,
            )
            raise typer.Exit(code=1)
        metrics = run.get("metrics") or {}
        if run.get("status") != "succeeded" or metrics.get("gate") != "passed":
            typer.echo(
                f"eval gate is not passed (status={run.get('status')}, metrics={metrics})",
                err=True,
            )
            raise typer.Exit(code=1)
        if run.get("prompt_name") != prompt_id or run.get("prompt_version") != version:
            typer.echo(
                "eval run does not match this prompt version; use --force if you are sure",
                err=True,
            )
            raise typer.Exit(code=1)

    previous = promote_label(settings.prompts_dir, prompt_id, version, label)
    if dry_run:
        typer.echo(f"would promote {prompt_id}@{label}: {previous or '-'} -> {version} (dry run)")
        return

    async def record() -> None:
        async with session_factory() as session, session.begin():
            await PromptCatalogService(SqlAlchemyPromptCatalogRepository(session)).sync(
                settings.prompts_dir
            )
            await AuditServiceImpl(SqlAlchemyAuditRepository(session)).record(
                "prompt.promote",
                target_type="prompt",
                target_id=f"{prompt_id}@{label}",
                metadata={
                    "from": previous,
                    "to": version,
                    "note": note,
                    "forced": force,
                    "eval_run_id": str(run_id) if run_id is not None else None,
                },
            )

    asyncio.run(record())
    typer.echo(f"promoted {prompt_id}@{label}: {previous or '-'} -> {version}")


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
