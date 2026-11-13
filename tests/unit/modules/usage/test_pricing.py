from __future__ import annotations

from webnovel.modules.usage.pricing import Price, Pricing


def test_cost_calculation() -> None:
    pricing = Pricing(
        models={
            "m": Price(input_per_million=2.0, output_per_million=8.0, cached_input_per_million=1.0)
        }
    )
    price = pricing.price_for("m")
    cost = (1_000_000 * price.input_per_million + 500_000 * price.output_per_million) / 1_000_000
    assert cost == 6.0


def test_unknown_model_falls_back_to_default() -> None:
    pricing = Pricing(models={"default": Price(input_per_million=1.0)})
    assert pricing.price_for("unknown").input_per_million == 1.0
