from __future__ import annotations

from webnovel.kernel.errors import ValidationError
from webnovel.modules.settings.contract import AppSettings
from webnovel.modules.settings.service import SettingsServiceImpl


class FakeSettingsRepository:
    def __init__(self) -> None:
        self.values = AppSettings()

    async def load(self) -> AppSettings:
        return self.values

    async def save(self, values: AppSettings) -> AppSettings:
        self.values = values
        return values


async def test_get_returns_defaults() -> None:
    service = SettingsServiceImpl(FakeSettingsRepository())
    values = await service.get()
    assert values.context_max_tokens == 16_000


async def test_update_validates_context_tokens() -> None:
    service = SettingsServiceImpl(FakeSettingsRepository())
    try:
        await service.update(AppSettings(context_max_tokens=10))
    except ValidationError as exc:
        assert exc.code == "settings.invalid_context_max_tokens"
    else:
        raise AssertionError("expected ValidationError")


async def test_update_persists_values() -> None:
    repo = FakeSettingsRepository()
    service = SettingsServiceImpl(repo)
    updated = await service.update(AppSettings(context_max_tokens=8_000, daily_budget=5.0))
    assert updated.context_max_tokens == 8_000
    assert repo.values.daily_budget == 5.0
