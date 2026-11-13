from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardrailProfile(StrEnum):
    CREATIVE = "creative"
    PUBLISH = "publish"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class GuardrailPolicy:
    profile: GuardrailProfile = GuardrailProfile.CREATIVE
    allow_override: bool = True
    fail_open_on_outage: bool = True
