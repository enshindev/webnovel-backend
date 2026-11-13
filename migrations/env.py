from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from webnovel.infra.config import get_settings
from webnovel.infra.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata

# 导入所有 models，供 autogenerate 使用；新增模块时在这里登记。
from webnovel.modules.agent import models as agent_models  # noqa: F401,E402
from webnovel.modules.analysis import models as analysis_models  # noqa: F401,E402
from webnovel.modules.assistant import knowledge_models as knowledge_models  # noqa: E402
from webnovel.modules.assistant import models as assistant_models  # noqa: F401,E402
from webnovel.modules.audit import models as audit_models  # noqa: F401,E402
from webnovel.modules.chapters_versions import models as chapters_models  # noqa: F401,E402
from webnovel.modules.export import models as export_models  # noqa: F401,E402
from webnovel.modules.generation import models as generation_models  # noqa: F401,E402
from webnovel.modules.library import models as library_models  # noqa: F401,E402
from webnovel.modules.memory import models as memory_models  # noqa: F401,E402
from webnovel.modules.outbox import models as outbox_models  # noqa: F401,E402
from webnovel.modules.prompts import models as prompt_models  # noqa: F401,E402
from webnovel.modules.quality import models as quality_models  # noqa: F401,E402
from webnovel.modules.settings import models as settings_models  # noqa: F401,E402
from webnovel.modules.style import models as style_models  # noqa: F401,E402
from webnovel.modules.usage import alert_models as budget_alert_models  # noqa: F401,E402
from webnovel.modules.usage import models as usage_models  # noqa: F401,E402
from webnovel.modules.volumes import models as volume_models  # noqa: F401,E402
from webnovel.modules.workflow import models as workflow_models  # noqa: F401,E402
from webnovel.modules.works import models as works_models  # noqa: F401,E402


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
