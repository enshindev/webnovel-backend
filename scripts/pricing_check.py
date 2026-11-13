from __future__ import annotations

import sys

from webnovel.infra.config import get_settings
from webnovel.modules.usage.pricing import load_pricing


def main() -> None:
    settings = get_settings()
    pricing = load_pricing(settings.pricing_config_path)
    model = settings.llm_model or "default"
    price = pricing.price_for(model)
    print(f"model: {model}")
    print(f"input_per_million: {price.input_per_million}")
    print(f"output_per_million: {price.output_per_million}")
    print(f"cached_input_per_million: {price.cached_input_per_million}")
    if price.input_per_million == 0 and price.output_per_million == 0:
        print("warning: model price is zero; fill config/pricing.yaml", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
