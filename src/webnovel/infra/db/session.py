from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from webnovel.infra.db.engine import create_engine

engine = create_engine()
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """请求级事务：正常结束提交，异常回滚。"""
    async with session_factory() as session, session.begin():
        yield session
