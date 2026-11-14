"""multi-candidate drafts.

Revision ID: 0030_multi_candidate
Revises: 0029_prompt_tables
Create Date: 2026-11-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_multi_candidate"
down_revision: str | None = "0029_prompt_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_drafts_generation_id", "drafts", type_="unique")
    op.add_column(
        "drafts",
        sa.Column("candidate_index", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_drafts_generation_id_candidate_index",
        "drafts",
        ["generation_id", "candidate_index"],
    )


def downgrade() -> None:
    op.drop_index("ix_drafts_generation_id_candidate_index", table_name="drafts")
    op.drop_column("drafts", "candidate_index")
    op.create_unique_constraint("uq_drafts_generation_id", "drafts", ["generation_id"])
