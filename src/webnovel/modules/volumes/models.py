from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from webnovel.infra.db.base import Base, UUIDPrimaryKeyMixin


class VolumeModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "volumes"
    __table_args__ = (UniqueConstraint("work_id", "number", name="uq_volumes_work_number"),)

    work_id: Mapped[UUID] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
