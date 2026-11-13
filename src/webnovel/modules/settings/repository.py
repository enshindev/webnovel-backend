from __future__ import annotations

from typing import Any, Protocol, cast

from sqlalchemy.ext.asyncio import AsyncSession

from webnovel.modules.settings.contract import AppSettings
from webnovel.modules.settings.models import SettingModel

SETTINGS_KEY = "app"


class SettingsRepository(Protocol):
    async def load(self) -> AppSettings: ...

    async def save(self, values: AppSettings) -> AppSettings: ...


class SqlAlchemySettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self) -> AppSettings:
        model = await self._session.get(SettingModel, SETTINGS_KEY)
        if model is None:
            return AppSettings()
        value = cast(dict[str, Any], model.value)
        return AppSettings(
            context_max_tokens=int(value.get("context_max_tokens", 16_000)),
            daily_budget=value.get("daily_budget"),
        )

    async def save(self, values: AppSettings) -> AppSettings:
        model = await self._session.get(SettingModel, SETTINGS_KEY)
        payload: dict[str, Any] = {
            "context_max_tokens": values.context_max_tokens,
            "daily_budget": values.daily_budget,
        }
        if model is None:
            model = SettingModel(key=SETTINGS_KEY, value=payload)
            self._session.add(model)
        else:
            model.value = payload
        await self._session.flush()
        return values
