"""wahlwerk.calc stands alone in the engine: it imports numpy and the standard library,
never another part of wahlwerk, and its modules import only from layers below their own.
The rest of wahlwerk computes through it, never the other way."""

import ast
from pathlib import Path

from wahlwerk import calc

SOURCE = Path(calc.__file__).parent
LAYER = {name: i for i, (_, names) in enumerate(calc.LAYERS) for name in names}


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            if node.module == "wahlwerk.calc":
                found |= {f"wahlwerk.calc.{alias.name}" for alias in node.names}
    return found


def test_imports_nothing_else_of_wahlwerk():
    for path in SOURCE.glob("*.py"):
        for name in _imports(path):
            parts = name.split(".")
            if parts[0] == "wahlwerk":
                assert parts[:2] == ["wahlwerk", "calc"], f"{path.name} imports {name}"


def test_layers_point_down():
    for path in SOURCE.glob("*.py"):
        own = LAYER.get(path.stem)
        if own is None:
            continue
        for name in _imports(path):
            parts = name.split(".")
            if parts[:2] == ["wahlwerk", "calc"] and len(parts) > 2 and parts[2] in LAYER:
                assert LAYER[parts[2]] <= own, f"{path.stem} (layer {own + 1}) imports {parts[2]}"


def test_every_module_is_in_a_layer():
    public = {p.stem for p in SOURCE.glob("*.py") if not p.stem.startswith("_")}
    assert public - set(LAYER) == {"notation", "types"}
