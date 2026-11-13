from __future__ import annotations

import json
from pathlib import Path

from webnovel.entrypoints.api.app import create_app


def main() -> None:
    app = create_app()
    target = Path("docs/backend/openapi.generated.json")
    target.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(target)


if __name__ == "__main__":
    main()
