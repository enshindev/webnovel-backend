from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from webnovel.modules.library.service import _parse_text


def test_chinese_image_ocr() -> None:
    pytest.importorskip("rapidocr_onnxruntime")
    from PIL import Image, ImageDraw, ImageFont

    font_path = Path("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc")
    if not font_path.is_file():
        pytest.skip("CJK font unavailable")
    image = Image.new("RGB", (600, 160), "white")
    ImageDraw.Draw(image).text(
        (20, 40), "雨夜追捕", fill="black", font=ImageFont.truetype(str(font_path), 48)
    )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    text = _parse_text(buffer.getvalue(), "png")
    assert "雨夜" in text
