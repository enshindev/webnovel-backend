from __future__ import annotations

import pytest

from webnovel.kernel.errors import ConflictError
from webnovel.modules.generation.contract import GenerationStatus
from webnovel.modules.generation.state_machine import transition


def test_queued_to_running() -> None:
    assert transition(GenerationStatus.QUEUED, GenerationStatus.RUNNING) is GenerationStatus.RUNNING


def test_streaming_to_succeeded() -> None:
    assert (
        transition(GenerationStatus.STREAMING, GenerationStatus.SUCCEEDED)
        is GenerationStatus.SUCCEEDED
    )


def test_illegal_transition() -> None:
    with pytest.raises(ConflictError):
        transition(GenerationStatus.QUEUED, GenerationStatus.SUCCEEDED)


def test_terminal_is_final() -> None:
    with pytest.raises(ConflictError):
        transition(GenerationStatus.SUCCEEDED, GenerationStatus.RUNNING)
