from __future__ import annotations

from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from webnovel.entrypoints.worker.jobs import (
    run_agent,
    run_analysis,
    run_chapter_extraction,
    run_export,
    run_export_cleanup,
    run_extraction,
    run_generation,
    run_idempotency_cleanup,
    run_knowledge_index,
    run_outbox_dispatch,
    run_quality_review,
    run_workflow_all,
    run_workflow_stage,
)
from webnovel.infra.config import get_settings
from webnovel.infra.logging import configure_logging


class WorkerSettings:
    functions: ClassVar[list[object]] = [
        run_generation,
        run_extraction,
        run_quality_review,
        run_export,
        run_export_cleanup,
        run_chapter_extraction,
        run_agent,
        run_analysis,
        run_workflow_stage,
        run_workflow_all,
        run_outbox_dispatch,
        run_knowledge_index,
        run_idempotency_cleanup,
    ]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 600
    max_tries = 3
    health_check_interval = 30
    cron_jobs: ClassVar[list[object]] = [
        cron(run_export_cleanup, hour=3),
        cron(run_outbox_dispatch, minute=0),
        cron(run_knowledge_index, hour=2),
        cron(run_idempotency_cleanup, minute=17),
    ]


def main() -> None:
    from arq.worker import run_worker

    configure_logging(get_settings())
    run_worker(WorkerSettings)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
