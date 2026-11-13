from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class PricingStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, Any]:
        data = yaml.safe_load(self._path.read_text(encoding="utf-8")) if self._path.exists() else {}
        return dict(data or {})

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        for model, values in (data.get("models") or {}).items():
            for key in ("input_per_million", "output_per_million", "cached_input_per_million"):
                value = values.get(key, 0)
                if float(value) < 0:
                    raise ValueError(f"{model}.{key} must be >= 0")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        return data
