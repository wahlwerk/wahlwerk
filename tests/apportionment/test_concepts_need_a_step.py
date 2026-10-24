"""A core concept (a method, a threshold, a quota) is never applied to the tally
directly: it is always held by a step, which reads the allocation and hands the concept
plain numbers. So nothing in wahlwerk.apportionment imports the vote, the process or the
law, and no concept has an apply of its own."""

import ast
from pathlib import Path

import pytest

from wahlwerk.apportionment.deduction import Deduction
from wahlwerk.apportionment.increment import Increment
from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.apportionment.quota import Quota
from wahlwerk.apportionment.threshold import Threshold
from wahlwerk.law.edit import steps
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation import flow
from wahlwerk.process.allocation.base import AllocationStep

PACKAGE = Path(__file__).parents[2] / "src" / "wahlwerk" / "apportionment"
ALLOWED = ("wahlwerk.apportionment", "wahlwerk.calc", "wahlwerk.model", "wahlwerk.ids")


@pytest.mark.parametrize("module", sorted(PACKAGE.glob("*.py")), ids=lambda p: p.name)
def test_a_concept_never_sees_the_tally(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("wahlwerk")
    ]
    assert all(name.startswith(ALLOWED) for name in imported), imported


def test_concepts_are_not_steps() -> None:
    for base in (ApportionmentMethod, Threshold, Quota, Deduction, Increment):
        assert not issubclass(base, AllocationStep)
        assert not hasattr(base, "apply")


def test_every_concept_in_a_law_sits_in_a_step() -> None:
    # describe finds each concept through the step that holds it; none stands alone.
    for law in LAWS.laws:
        for _, step in steps(law.protocol):
            assert isinstance(step, AllocationStep)
            for use in flow.uses(step):
                assert use.kind not in {type(s).__name__ for _, s in steps(law.protocol)}
