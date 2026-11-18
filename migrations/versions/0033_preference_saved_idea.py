"""allow preference events without a candidate set for saved ideas.

Revision ID: 0033_preference_saved_idea
Revises: 0032_entity_state_changes
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0033_preference_saved_idea"
down_revision: str | None = "0032_entity_state_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("preference_events", "candidate_set_id", nullable=True)
