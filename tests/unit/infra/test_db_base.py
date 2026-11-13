from __future__ import annotations

from webnovel.infra.db.base import NAMING_CONVENTION, TimestampMixin, UUIDPrimaryKeyMixin


def test_naming_convention_keys() -> None:
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"
    assert NAMING_CONVENTION["fk"].startswith("fk_")


def test_mixins_are_not_mapped_tables() -> None:
    assert not hasattr(UUIDPrimaryKeyMixin, "__table__")
    assert not hasattr(TimestampMixin, "__table__")
