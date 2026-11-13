from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class Price:
    input_per_million: float = 0.0
    output_per_million: float = 0.0
    cached_input_per_million: float = 0.0


@dataclass(frozen=True, slots=True)
class Pricing:
    currency: str = "CNY"
    models: dict[str, Price] | None = None

    def price_for(self, model: str) -> Price:
        if self.models:
            return self.models.get(model) or self.models.get("default") or Price()
        return Price()


def load_pricing(path: Path) -> Pricing:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_models = data.get("models", {})
        models = {
            str(name): Price(
                input_per_million=float(value.get("input_per_million", 0)),
                output_per_million=float(value.get("output_per_million", 0)),
                cached_input_per_million=float(value.get("cached_input_per_million", 0)),
            )
            for name, value in raw_models.items()
        }
        return Pricing(currency=str(data.get("currency", "CNY")), models=models)
    except (OSError, TypeError, ValueError, yaml.YAMLError):
        return Pricing()
