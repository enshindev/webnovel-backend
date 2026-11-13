from __future__ import annotations

from webnovel.kernel.errors import ValidationError
from webnovel.modules.settings.contract import AppSettings
from webnovel.modules.settings.repository import SettingsRepository


class SettingsServiceImpl:
    def __init__(self, repository: SettingsRepository) -> None:
        self._repository = repository

    async def get(self) -> AppSettings:
        return await self._repository.load()

    async def update(self, values: AppSettings) -> AppSettings:
        if not 1_000 <= values.context_max_tokens <= 200_000:
            raise ValidationError(
                "context_max_tokens must be between 1000 and 200000",
                code="settings.invalid_context_max_tokens",
            )
        if values.daily_budget is not None and values.daily_budget < 0:
            raise ValidationError("daily_budget must be >= 0", code="settings.invalid_daily_budget")
        return await self._repository.save(values)
