from __future__ import annotations

import pytest

from webnovel.llm.prompts.renderer import render_prompt
from webnovel.llm.prompts.schema import PromptInclude, PromptSpec


def _spec(template: str, *, includes: list[PromptInclude] | None = None) -> PromptSpec:
    return PromptSpec(
        id="generation/continuation",
        version=1,
        template=template,
        variables=["chapter_outline", "instruction"],
        includes=includes or [],
    )


def test_render_variables_and_include() -> None:
    shared = PromptSpec(id="shared/style", version=1, template="文风：短句。", variables=[])
    spec = _spec(
        "{{> shared/style@v001}}\n{{chapter_outline}}\n{{instruction}}",
        includes=[PromptInclude(id="shared/style", version=1)],
    )
    rendered = render_prompt(
        spec,
        {"chapter_outline": "第 1 章", "instruction": "继续"},
        {"shared/style@v001": shared},
    )
    assert "文风：短句。" in rendered
    assert "第 1 章" in rendered
    assert "继续" in rendered


def test_missing_variable_fails() -> None:
    with pytest.raises(ValueError, match="prompt variable missing"):
        render_prompt(_spec("{{chapter_outline}}"), {}, {})


def test_include_cycle_fails() -> None:
    a = PromptSpec(id="a", version=1, template="{{> b@v001}}", variables=[])
    b = PromptSpec(id="b", version=1, template="{{> a@v001}}", variables=[])
    with pytest.raises(ValueError, match="include cycle"):
        render_prompt(a, {}, {"b@v001": b, "a@v001": a})
