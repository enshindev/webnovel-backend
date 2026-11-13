from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "src" / "webnovel" / "modules"


def _source_files() -> list[Path]:
    return sorted(path for path in MODULES.rglob("*.py") if "__pycache__" not in path.parts)


def _module_name(path: Path) -> str:
    return path.relative_to(MODULES).parts[0]


def _imported_modules(tree: ast.AST) -> list[tuple[str, set[str]]]:
    imports: list[tuple[str, set[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, {alias.name for alias in node.names}))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, set()))
    return imports


def test_cross_module_imports_go_through_contract_only() -> None:
    violations: list[str] = []
    for path in _source_files():
        current = _module_name(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module, names in _imported_modules(tree):
            if module.startswith("webnovel.entrypoints") and path.name != "http.py":
                violations.append(f"{path.relative_to(ROOT)} -> {module} (only http.py may use DI)")
                continue
            if not module.startswith("webnovel.modules."):
                continue
            parts = module.split(".")
            target = parts[2]
            if target == current:
                continue
            # 允许：from webnovel.modules.other.contract import X
            if len(parts) >= 4 and parts[3] == "contract":
                continue
            # 允许：from webnovel.modules.other import contract
            if len(parts) == 3 and names and names <= {"contract"}:
                continue
            violations.append(f"{path.relative_to(ROOT)} -> {module}")
    assert not violations, "cross-module imports must use contract.py:\n" + "\n".join(violations)
