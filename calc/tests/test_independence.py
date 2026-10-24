"""wahlwerk-calc stands alone: it imports numpy and the standard library, never wahlwerk,
and its modules import only from layers below their own."""

import ast
from pathlib import Path

import wahlwerk_calc

SOURCE = Path(wahlwerk_calc.__file__).parent
LAYER = {name: i for i, (_, names) in enumerate(wahlwerk_calc.LAYERS) for name in names}


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            if node.module == "wahlwerk_calc":
                found |= {f"wahlwerk_calc.{alias.name}" for alias in node.names}
    return found


def test_never_imports_wahlwerk():
    for path in SOURCE.glob("*.py"):
        for name in _imports(path):
            assert name.split(".")[0] != "wahlwerk", f"{path.name} imports {name}"


def test_layers_point_down():
    for path in SOURCE.glob("*.py"):
        own = LAYER.get(path.stem)
        if own is None:
            continue
        for name in _imports(path):
            parts = name.split(".")
            if parts[0] == "wahlwerk_calc" and len(parts) > 1 and parts[1] in LAYER:
                assert LAYER[parts[1]] <= own, f"{path.stem} (layer {own + 1}) imports {parts[1]}"


def test_every_module_is_in_a_layer():
    public = {p.stem for p in SOURCE.glob("*.py") if not p.stem.startswith("_")}
    assert public - set(LAYER) == {"notation", "types"}
