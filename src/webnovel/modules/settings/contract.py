from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AppSettings:
    context_max_tokens: int = 16_000
    daily_budget: float | None = None


class SettingsService(Protocol):
    async def get(self) -> AppSettings: ...

    async def update(self, values: AppSettings) -> AppSettings: ...
