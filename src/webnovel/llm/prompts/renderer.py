from __future__ import annotations

import re
from collections.abc import Mapping

from webnovel.llm.prompts.schema import PromptSpec

_INCLUDE = re.compile(r"{{\s*>\s*([^}]+?)\s*}}")
_VARIABLE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_./-]*)\s*}}")


def render_prompt(
    spec: PromptSpec,
    values: Mapping[str, str],
    includes: Mapping[str, PromptSpec],
) -> str:
    """渲染 prompt：先展开 {{> id@vNNN}}，再替换 {{variable}}。

    缺变量或 include 时直接报错，避免把占位符发给模型。
    """
    return _render(spec.template, values, includes, stack=())


def _render(
    template: str,
    values: Mapping[str, str],
    includes: Mapping[str, PromptSpec],
    *,
    stack: tuple[str, ...],
) -> str:
    def replace_include(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key in stack:
            raise ValueError(f"prompt include cycle: {' -> '.join((*stack, key))}")
        include = includes.get(key)
        if include is None:
            raise ValueError(f"prompt include not loaded: {key}")
        return _render(include.template, values, includes, stack=(*stack, key))

    expanded = _INCLUDE.sub(replace_include, template)

    def replace_variable(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        if name not in values:
            raise ValueError(f"prompt variable missing: {name}")
        return str(values[name])

    return _VARIABLE.sub(replace_variable, expanded)
