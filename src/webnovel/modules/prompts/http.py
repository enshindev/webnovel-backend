from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from webnovel.entrypoints.api.deps import SettingsDep
from webnovel.llm.prompts.registry import PromptRegistry

router = APIRouter(prefix="/prompt-catalog", tags=["prompts"])


class PromptVersionOut(BaseModel):
    id: str
    version: int
    variables: list[str]
    template: str
    labels: dict[str, int]


@router.get("/version/{prompt_id:path}/{version}")
async def get_prompt_version(
    prompt_id: str, version: int, settings: SettingsDep
) -> PromptVersionOut:
    try:
        spec = PromptRegistry(settings.prompts_dir).load_version(prompt_id, version)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    labels_path = settings.prompts_dir / prompt_id / "labels.yaml"
    labels_data = (
        yaml.safe_load(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    )
    return PromptVersionOut(
        id=spec.id,
        version=spec.version,
        variables=spec.variables,
        template=spec.template,
        labels=dict((labels_data or {}).get("labels", {})),
    )


@router.get("/list/{prompt_id:path}")
async def list_prompt_versions(prompt_id: str, settings: SettingsDep) -> dict[str, object]:
    directory = settings.prompts_dir / prompt_id
    if not directory.is_dir():
        raise HTTPException(status_code=404, detail="prompt not found")
    versions = []
    for path in sorted(directory.glob("v*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        versions.append(
            {
                "id": str(data.get("id", prompt_id)),
                "version": int(data.get("version", 0)),
                "variables": list(data.get("variables", [])),
                "template": str(data.get("template", "")),
            }
        )
    labels_path = directory / "labels.yaml"
    labels_data = (
        yaml.safe_load(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}
    )
    labels = dict((labels_data or {}).get("labels", {}))
    return {"prompt_id": prompt_id, "labels": labels, "versions": versions}
