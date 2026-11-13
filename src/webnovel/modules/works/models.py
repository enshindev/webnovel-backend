from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "works"

    owner_id: Mapped[str] = mapped_column(String(64), default="local")
    title: Mapped[str] = mapped_column(String(200))
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
