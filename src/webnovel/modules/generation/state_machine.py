from __future__ import annotations

from webnovel.kernel.errors import ConflictError
from webnovel.modules.generation.contract import TERMINAL, GenerationStatus

ALLOWED: dict[GenerationStatus, set[GenerationStatus]] = {
    GenerationStatus.QUEUED: {
        GenerationStatus.RUNNING,
        GenerationStatus.CANCELLED,
        GenerationStatus.EXPIRED,
    },
    GenerationStatus.RUNNING: {
        GenerationStatus.STREAMING,
        GenerationStatus.FAILED,
        GenerationStatus.CANCELLING,
    },
    GenerationStatus.STREAMING: {
        GenerationStatus.SUCCEEDED,
        GenerationStatus.FAILED,
        GenerationStatus.CANCELLING,
    },
    GenerationStatus.CANCELLING: {GenerationStatus.CANCELLED},
    GenerationStatus.CANCELLED: set(),
    GenerationStatus.SUCCEEDED: set(),
    GenerationStatus.FAILED: set(),
    GenerationStatus.EXPIRED: set(),
}


def transition(current: GenerationStatus, target: GenerationStatus) -> GenerationStatus:
    """纯函数：校验并返回新状态；非法迁移抛 ConflictError。"""
    if current in TERMINAL:
        raise ConflictError(f"generation is terminal: {current}", code="generation.terminal")
    if target not in ALLOWED[current]:
        raise ConflictError(
            f"illegal transition: {current} -> {target}",
            code="generation.illegal_transition",
        )
    return target
