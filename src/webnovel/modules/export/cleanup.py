from __future__ import annotations

from pathlib import Path

from webnovel.modules.export.repository import ExportRepository


async def cleanup_exports(repository: ExportRepository) -> int:
    paths = await repository.expire()
    removed = 0
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed
