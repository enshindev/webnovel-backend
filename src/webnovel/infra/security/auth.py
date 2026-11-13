from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str = "local"
    display_name: str = "本地作者"


class Auth(Protocol):
    async def authenticate(self) -> Principal: ...


class NoAuth:
    async def authenticate(self) -> Principal:
        return Principal()
