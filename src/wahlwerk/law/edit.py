"""Editing laws: a new protocol from an existing one, with a value or a step changed.

A counterfactual is the same votes under another protocol; this module makes the other
protocol. Nothing is changed in place: every function returns a new protocol, its steps
validated like any other model, and :meth:`~wahlwerk.law.base.Law.revise` turns it into
a law, checked like any other law.

A step is addressed by its :data:`StepPath`: its position in the protocol, then, for a
step inside a step's own protocol (the loop of Sec. 35 (8) LWG LSA repeats Sec. 35 (4)
to (7)), the name of that field and the position in it: ``(9, "protocol", 1)`` is the
second step of the protocol of the tenth step. :func:`steps` lists every step with its
path, depth first.

    from fractions import Fraction
    from wahlwerk.apportionment.divisor import SainteLague
    from wahlwerk.apportionment.threshold import RelativeThreshold
    from wahlwerk.law.edit import replace
    from wahlwerk.process.allocation.eligibility import ApplyThreshold, SetHouse
    from wahlwerk.process.allocation.seats import ApportionSeats

    protocol = replace(LWG_2021.protocol, ApplyThreshold,
                       threshold=RelativeThreshold(share=Fraction(3, 100)))
    protocol = replace(protocol, SetHouse, seats=101)
    protocol = replace(protocol, ApportionSeats, method=SainteLague())
    law = LWG_2021.revise(id="example.st.lwg.sainte-lague", title="...", protocol=protocol)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, TypeVar

from wahlwerk.process.allocation.base import AllocationProtocol, AllocationStep

__all__ = [
    "StepPath",
    "find",
    "insert",
    "remove",
    "replace",
    "step_at",
    "steps",
    "substitute",
]

StepPath = tuple[int | str, ...]
"""Where a step sits: its position, then field name and position for each nested
protocol it is inside, e.g. ``(9, "protocol", 1)``."""

S = TypeVar("S", bound=AllocationStep)


def _nested(step: AllocationStep) -> Iterator[tuple[str, AllocationProtocol]]:
    """The fields of ``step`` that hold a protocol of their own, in field order."""
    for name in type(step).model_fields:
        value = getattr(step, name)
        if (
            isinstance(value, tuple)
            and value
            and all(isinstance(item, AllocationStep) for item in value)
        ):
            yield name, value


def steps(protocol: AllocationProtocol) -> Iterator[tuple[StepPath, AllocationStep]]:
    """Every step with its path, depth first: a step, then the steps it holds."""
    for position, step in enumerate(protocol):
        yield (position,), step
        for name, inner in _nested(step):
            for path, inner_step in steps(inner):
                yield (position, name, *path), inner_step


def find(protocol: AllocationProtocol, kind: type[AllocationStep]) -> list[StepPath]:
    """The paths of every step of type ``kind`` (subclasses included)."""
    return [path for path, step in steps(protocol) if isinstance(step, kind)]


def step_at(protocol: AllocationProtocol, path: StepPath) -> AllocationStep:
    """The step at ``path``; ``KeyError`` naming the path if there is none."""
    _check_path(path)
    try:
        step = protocol[int(path[0])]
        rest = path[1:]
        while rest:
            name, position, rest = str(rest[0]), int(rest[1]), rest[2:]
            step = getattr(step, name)[position]
    except (IndexError, AttributeError, TypeError) as error:
        raise KeyError(f"no step at {path}") from error
    return step


def _check_path(path: StepPath) -> None:
    if not path or len(path) % 2 == 0:
        raise KeyError(f"a step path is a position, then field and position pairs; got {path}")
    for i, part in enumerate(path):
        wanted = int if i % 2 == 0 else str
        if isinstance(part, bool) or not isinstance(part, wanted):
            raise KeyError(f"step path {path}: part {i} must be {wanted.__name__}, got {part!r}")


def _edit(
    protocol: AllocationProtocol, path: StepPath, change: Any
) -> AllocationProtocol:
    """``protocol`` with ``change(steps, position)`` applied where ``path`` points; the
    steps that hold the edited protocol are rebuilt, and validated, on the way out."""
    position = int(path[0])
    if len(path) == 1:
        return tuple(change(list(protocol), position))
    if not 0 <= position < len(protocol):
        raise KeyError(f"no step at {path}")
    outer = protocol[position]
    name = str(path[1])
    inner = getattr(outer, name, None)
    if not isinstance(inner, tuple):
        raise KeyError(f"step {outer!r} has no protocol field {name!r}")
    rebuilt = _rebuild(outer, **{name: _edit(inner, path[2:], change)})
    return (*protocol[:position], rebuilt, *protocol[position + 1 :])


def _rebuild(step: S, **changes: Any) -> S:
    """``step`` with ``changes``, validated: a value of the wrong type or out of range
    fails here, naming the step."""
    unknown = set(changes) - set(type(step).model_fields)
    if unknown:
        raise ValueError(
            f"{type(step).__name__} has no field {sorted(unknown)}; "
            f"its fields are {list(type(step).model_fields)}"
        )
    return type(step).model_validate({**dict(step), **changes})


def replace(
    protocol: AllocationProtocol,
    kind: type[AllocationStep],
    /,
    *,
    at: StepPath | None = None,
    **changes: Any,
) -> AllocationProtocol:
    """``protocol`` with ``changes`` made to every step of type ``kind``, nested ones
    included, or only to the one at ``at``.

    ``replace(protocol, SetHouse, seats=101)`` raises the legal size of the house;
    ``replace(protocol, ApportionSeats, method=SainteLague())`` swaps the method in every
    place the law apportions. Raises ``KeyError`` if no step of that type is there.
    """
    if not changes:
        raise ValueError("replace needs at least one field to change")
    paths = find(protocol, kind)
    if at is not None:
        if at not in paths:
            raise KeyError(f"no {kind.__name__} at {at}; there are at {paths}")
        paths = [at]
    if not paths:
        raise KeyError(f"the protocol has no {kind.__name__}")

    def change_one(items: list[AllocationStep], position: int) -> list[AllocationStep]:
        if not 0 <= position < len(items):
            raise KeyError(f"no step at position {position}")
        items[position] = _rebuild(items[position], **changes)
        return items

    # Deepest first, so editing an inner step never moves the path of one still to edit.
    for path in sorted(paths, key=len, reverse=True):
        protocol = _edit(protocol, path, change_one)
    return protocol


def substitute(
    protocol: AllocationProtocol, at: StepPath, step: AllocationStep
) -> AllocationProtocol:
    """``protocol`` with the step at ``at`` replaced by ``step``."""
    step_at(protocol, at)  # raises if there is none

    def put(items: list[AllocationStep], position: int) -> list[AllocationStep]:
        items[position] = step
        return items

    return _edit(protocol, at, put)


def insert(
    protocol: AllocationProtocol, at: StepPath, step: AllocationStep
) -> AllocationProtocol:
    """``protocol`` with ``step`` inserted before the step at ``at``; a position one past
    the last step appends."""
    _check_path(at)

    def put(items: list[AllocationStep], position: int) -> list[AllocationStep]:
        if not 0 <= position <= len(items):
            raise KeyError(f"cannot insert at position {position} of {len(items)} steps")
        items.insert(position, step)
        return items

    return _edit(protocol, at, put)


def remove(protocol: AllocationProtocol, at: StepPath) -> AllocationProtocol:
    """``protocol`` without the step at ``at``."""
    step_at(protocol, at)  # raises if there is none

    def drop(items: list[AllocationStep], position: int) -> list[AllocationStep]:
        del items[position]
        return items

    return _edit(protocol, at, drop)
