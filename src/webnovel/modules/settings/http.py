from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from webnovel.entrypoints.api.deps import SettingsDep, SettingsServiceDep
from webnovel.modules.settings.contract import AppSettings
from webnovel.modules.settings.pricing import PricingStore

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsOut(BaseModel):
    context_max_tokens: int
    daily_budget: float | None


class PricingModel(BaseModel):
    input_per_million: float = Field(default=0, ge=0)
    output_per_million: float = Field(default=0, ge=0)
    cached_input_per_million: float = Field(default=0, ge=0)


class PricingPatch(BaseModel):
    currency: str = "CNY"
    models: dict[str, PricingModel] = Field(default_factory=dict)


class SettingsPatch(BaseModel):
    context_max_tokens: int | None = Field(default=None, ge=1_000, le=200_000)
    daily_budget: float | None = Field(default=None, ge=0)


@router.get("", response_model=SettingsOut)
async def get_settings(service: SettingsServiceDep) -> SettingsOut:
    values = await service.get()
    return SettingsOut(
        context_max_tokens=values.context_max_tokens, daily_budget=values.daily_budget
    )


@router.get("/pricing")
async def get_pricing(settings: SettingsDep) -> dict[str, object]:
    return PricingStore(settings.pricing_config_path).load()


@router.put("/pricing")
async def put_pricing(body: PricingPatch, settings: SettingsDep) -> dict[str, object]:
    return PricingStore(settings.pricing_config_path).save(body.model_dump())


@router.patch("", response_model=SettingsOut)
async def patch_settings(body: SettingsPatch, service: SettingsServiceDep) -> SettingsOut:
    current = await service.get()
    values = await service.update(
        AppSettings(
            context_max_tokens=body.context_max_tokens
            if body.context_max_tokens is not None
            else current.context_max_tokens,
            daily_budget=body.daily_budget
            if body.daily_budget is not None
            else current.daily_budget,
        )
    )
    return SettingsOut(
        context_max_tokens=values.context_max_tokens, daily_budget=values.daily_budget
    )
