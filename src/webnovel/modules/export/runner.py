from __future__ import annotations

from uuid import UUID

from webnovel.infra.config import Settings
from webnovel.kernel.errors import UnavailableError
from webnovel.modules.chapters_versions.contract import ChapterService
from webnovel.modules.export.contract import ExportStatus
from webnovel.modules.export.render import render_docx, render_txt
from webnovel.modules.export.repository import ExportRepository
from webnovel.modules.multimodal.contract import CoverProvider, SpeechProvider
from webnovel.modules.works.contract import WorkService

DISCLOSURE = (
    "AI 使用说明：本作品的部分章节使用了 AI 辅助生成或润色。"
    "作者已对最终内容进行确认与修改；具体来源可在创作溯源中查看。"
)


class ExportRunner:
    def __init__(
        self,
        *,
        repository: ExportRepository,
        chapter_service: ChapterService,
        work_service: WorkService,
        settings: Settings,
        speech: SpeechProvider | None = None,
        cover: CoverProvider | None = None,
    ) -> None:
        self._repository = repository
        self._chapter_service = chapter_service
        self._work_service = work_service
        self._settings = settings
        self._speech = speech
        self._cover = cover

    async def run(self, job_id: UUID) -> None:
        job = await self._repository.get(job_id)
        if job is None or job.status is not ExportStatus.QUEUED:
            return
        try:
            work = await self._work_service.get(job.work_id)
            chapters = await self._chapter_service.list(job.work_id)
            contents: list[str] = []
            for chapter in chapters:
                if chapter.current_version_id is None:
                    contents.append("")
                    continue
                version = await self._chapter_service.get_version(
                    chapter.id, chapter.current_version_id
                )
                contents.append(version.content)
            text = render_txt(
                work_title=work.title,
                chapters=chapters,
                contents=contents,
                disclosure=DISCLOSURE,
            )
            self._settings.export_dir.mkdir(parents=True, exist_ok=True)
            if job.format == "mp3":
                if self._speech is None:
                    raise UnavailableError("TTS is not configured", code="export.tts_unavailable")
                path = self._settings.export_dir / f"{job.id}.mp3"
                audio = bytearray()
                for start in range(0, len(text), 3_000):
                    audio.extend(await self._speech.synthesize(text[start : start + 3_000]))
                path.write_bytes(bytes(audio))
            elif job.format == "cover":
                if self._cover is None:
                    raise UnavailableError(
                        "image provider is not configured", code="export.cover_unavailable"
                    )
                prompt = (
                    f"中文网文封面，竖版，标题《{work.title}》，题材：{work.genre or '未设'}，"
                    "氛围克制，留出标题空间"
                )
                image = await self._cover.generate(prompt, "1024x1536")
                path = self._settings.export_dir / f"{job.id}.png"
                path.write_bytes(image)
            elif job.format == "docx":
                path = self._settings.export_dir / f"{job.id}.docx"
                render_docx(
                    path=str(path),
                    work_title=work.title,
                    chapters=chapters,
                    contents=contents,
                    disclosure=DISCLOSURE,
                )
            else:
                path = self._settings.export_dir / f"{job.id}.txt"
                path.write_text(text, encoding="utf-8")
            await self._repository.finish(job.id, ExportStatus.SUCCEEDED, str(path))
        except Exception:
            await self._repository.finish(job.id, ExportStatus.FAILED)
            raise
