from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class PlatformRules:
    min_words: int = 1_800
    max_words: int = 2_600
    thin_words: int = 2_000


def load_platform_rules(path: Path) -> PlatformRules:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        words = data["platforms"]["fanqie"]["chapter_words"]
        return PlatformRules(
            min_words=int(words.get("min", 1_800)),
            max_words=int(words.get("max", 2_600)),
            thin_words=int(words.get("thin", 2_000)),
        )
    except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError):
        return PlatformRules()
