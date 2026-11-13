from __future__ import annotations

import json
from typing import Any, cast
from uuid import UUID

import structlog

from webnovel.infra.config import Settings
from webnovel.kernel.ports.llm import ChatMessage, ModelClient, ModelRequest
from webnovel.llm.prompts.registry import PromptRegistry
from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.usage import estimate_tokens
from webnovel.modules.agent.repository import AgentRepository
from webnovel.modules.assistant.contract import ToolExecutor
from webnovel.modules.usage.contract import UsageService

logger = structlog.get_logger(__name__)


class AgentExecutor:
    def __init__(
        self,
        *,
        repository: AgentRepository,
        model_client: ModelClient,
        settings: Settings,
        usage: UsageService | None = None,
        tools: ToolExecutor | None = None,
    ) -> None:
        self._repository = repository
        self._model_client = model_client
        self._settings = settings
        self._usage = usage
        self._tools = tools

    async def run(self, run_id: UUID) -> None:
        run = await self._repository.get(run_id)
        if run is None or run.status not in {"queued", "running"}:
            return
        if run.status == "queued":
            await self._repository.save(run.id, status="running")
        history: list[str] = list(cast(list[str], run.state.get("history", [])))
        approved = [
            f"已批准：{approval.action} {approval.payload}"
            for approval in run.pending_approvals
            if approval.status == "approved"
        ]
        if approved:
            history.extend(approved)
        tokens = run.tokens
        steps = run.steps
        try:
            for step in range(1, 4):
                prompt = PromptRegistry(self._settings.prompts_dir).resolve("agent/run")
                includes = PromptRegistry(self._settings.prompts_dir).load_includes(prompt)
                rendered = render_prompt(
                    prompt,
                    {
                        "goal": run.goal,
                        "experiment": run.experiment,
                        "work_context": f"work_id={run.work_id}" if run.work_id else "无绑定作品",
                        "history": "\n".join(history[-6:]) or "无",
                        "step": str(step),
                    },
                    includes,
                )
                result = await self._model_client.complete(
                    ModelRequest(
                        model=self._settings.llm_model,
                        messages=[ChatMessage(role="user", content=rendered)],
                        max_tokens=2_000,
                    )
                )
                prompt_tokens = estimate_tokens(rendered)
                completion_tokens = estimate_tokens(result)
                tokens += prompt_tokens + completion_tokens
                steps += 1
                if self._usage is not None:
                    await self._usage.record_llm(
                        work_id=run.work_id,
                        generation_id=None,
                        provider=self._settings.llm_provider,
                        model=self._settings.llm_model,
                        task_type="agent",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        estimated=True,
                    )

                parsed = _parse(result)
                if parsed is not None and parsed.get("tool"):
                    tool = cast(dict[str, Any], parsed["tool"])
                    if self._tools is not None and run.work_id is not None:
                        execution = await self._tools.execute(
                            str(tool.get("name", "")),
                            run.work_id,
                            str(tool.get("arguments", "{}")),
                        )
                        history.append(f"tool:{tool.get('name')} {execution.text}")
                        await self._repository.save(
                            run.id,
                            state={"history": history},
                            steps=steps,
                            tokens=tokens,
                        )
                        continue
                if parsed is not None and parsed.get("approval"):
                    approval = cast(dict[str, Any], parsed["approval"])
                    await self._repository.add_approval(
                        run.id,
                        str(approval.get("action", "agent.action")),
                        cast(dict[str, Any], approval.get("payload", {})),
                    )
                    await self._repository.save(
                        run.id,
                        status="waiting_approval",
                        state={"history": history},
                        steps=steps,
                        tokens=tokens,
                    )
                    logger.info("agent.waiting_approval", run_id=str(run.id))
                    return

                final = parsed is None or bool(parsed.get("final", True))
                text = str(parsed.get("result", result)) if parsed is not None else result
                history.append(text)
                if final:
                    await self._repository.save(
                        run.id,
                        status="succeeded",
                        state={"result": text, "history": history},
                        steps=steps,
                        tokens=tokens,
                    )
                    logger.info("agent.succeeded", run_id=str(run.id), steps=steps)
                    return
                await self._repository.save(
                    run.id,
                    state={"history": history},
                    steps=steps,
                    tokens=tokens,
                )

            await self._repository.save(
                run.id,
                status="failed",
                error="agent reached max steps",
                state={"history": history},
                steps=steps,
                tokens=tokens,
            )
        except Exception as exc:
            logger.exception("agent.failed", run_id=str(run.id))
            await self._repository.save(
                run.id, status="failed", error=str(exc), steps=steps, tokens=tokens
            )


def _parse(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.splitlines()[1:-1]).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None
