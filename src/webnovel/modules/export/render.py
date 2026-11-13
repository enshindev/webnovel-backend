from __future__ import annotations

from collections.abc import Sequence

from webnovel.modules.chapters_versions.contract import Chapter


def render_txt(
    *,
    work_title: str,
    chapters: Sequence[Chapter],
    contents: Sequence[str],
    disclosure: str,
) -> str:
    blocks = [f"《{work_title}》", ""]
    for chapter, content in zip(chapters, contents, strict=True):
        blocks.extend([f"第{chapter.number}章 {chapter.title}", "", content.strip(), ""])
    blocks.extend(["---", disclosure, ""])
    return "\n".join(blocks)


def render_docx(
    *,
    path: str,
    work_title: str,
    chapters: Sequence[Chapter],
    contents: Sequence[str],
    disclosure: str,
) -> None:
    from docx import Document

    document = Document()
    document.add_heading(f"《{work_title}》", level=0)
    for chapter, content in zip(chapters, contents, strict=True):
        document.add_heading(f"第{chapter.number}章 {chapter.title}", level=1)
        for paragraph in content.strip().split("\n\n"):
            if paragraph.strip():
                document.add_paragraph(paragraph.strip())
    document.add_page_break()  # type: ignore[no-untyped-call]
    document.add_paragraph(disclosure)
    document.save(path)
