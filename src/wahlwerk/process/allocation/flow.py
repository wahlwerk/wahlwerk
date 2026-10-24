"""The structure of a protocol, derived from what its steps read and write.

Nothing here is declared. A step depends on the step that last wrote a fact it reads;
its **stage** is one more than the latest stage it depends on, so the steps that read
only the tally are stage 0, the steps that read their results stage 1, and so on. Two
steps can trade places exactly when the trade leaves every step reading its facts from
the same writers, and leaves the same writer last for every fact: then the protocol
computes the same thing, by construction. A step may feed several later ones and read
from several earlier ones, so the stages are a layering, not a partition into kinds.

Where steps belong together on purpose, the law groups them as a
:class:`~wahlwerk.process.allocation.sequence.StepSequence`, which is named, and a loop
holds the steps it repeats; both are steps, so their insides have stages of their own.

>>> from wahlwerk.law.de.st.lwg import LWG_2021
>>> stages(LWG_2021.protocol)
(0, 1, 0, 1, 0, 2, 3)
>>> can_swap(LWG_2021.protocol, 1, 2), can_swap(LWG_2021.protocol, 4, 5)
(True, False)
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Iterator
from fractions import Fraction
from html import escape
from typing import Any

from pydantic import BaseModel, Field

from wahlwerk.model import Model
from wahlwerk.process.allocation.base import (
    INPUT_FACTS,
    AllocationProtocol,
    AllocationStep,
)

__all__ = [
    "Call",
    "StepNode",
    "Use",
    "calls_of",
    "can_swap",
    "describe",
    "movable",
    "protocol_data",
    "protocol_html",
    "protocol_table",
    "sources",
    "stages",
    "uses",
]


def sources(
    protocol: AllocationProtocol, established: frozenset[str] = INPUT_FACTS
) -> tuple[dict[str, int | None], ...]:
    """For each step, each fact it reads (and each optional fact present) and the
    position of the step that last wrote it before; ``None`` for a fact from outside
    the protocol (``established``). A required fact nobody wrote is left out; the
    protocol then fails :func:`~wahlwerk.process.allocation.base.check_protocol`."""
    last: dict[str, int | None] = {fact: None for fact in established}
    result = []
    for position, step in enumerate(protocol):
        read = {fact: last[fact] for fact in step.reads | step.optional_reads if fact in last}
        result.append(read)
        for fact in step.writes:
            last[fact] = position
    return tuple(result)


def stages(protocol: AllocationProtocol, established: frozenset[str] = INPUT_FACTS) -> tuple[int, ...]:
    """Each step's stage: 0 if it reads only facts from outside, otherwise one more than
    the latest stage of the steps it reads from."""
    result: list[int] = []
    for read in sources(protocol, established):
        writers = [result[w] for w in read.values() if w is not None]
        result.append(max(writers) + 1 if writers else 0)
    return tuple(result)


def can_swap(
    protocol: AllocationProtocol, first: int, second: int, established: frozenset[str] = INPUT_FACTS
) -> bool:
    """Whether the steps at ``first`` and ``second`` can trade places with the protocol
    computing the same: every step still reads each fact from the same writer, and the
    same step writes each fact last."""
    order = list(range(len(protocol)))
    order[first], order[second] = order[second], order[first]
    return _same_flow(protocol, order, established)


def movable(
    protocol: AllocationProtocol, position: int, established: frozenset[str] = INPUT_FACTS
) -> range:
    """The positions the step at ``position`` can be moved to, keeping the others in
    order, with the protocol computing the same: a contiguous range around it."""
    def keeps(target: int) -> bool:
        order = list(range(len(protocol)))
        order.insert(target, order.pop(position))
        return _same_flow(protocol, order, established)

    low = position
    while low > 0 and keeps(low - 1):
        low -= 1
    high = position
    while high < len(protocol) - 1 and keeps(high + 1):
        high += 1
    return range(low, high + 1)


def _same_flow(protocol: AllocationProtocol, order: list[int], established: frozenset[str]) -> bool:
    """Whether ``protocol`` taken in ``order`` (positions of the original) reads and
    finally writes every fact from the same steps as the original."""
    reordered = tuple(protocol[i] for i in order)
    before = _flow(protocol, list(range(len(protocol))), established)
    after = _flow(reordered, order, established)
    return before == after


def _flow(
    protocol: AllocationProtocol, names: list[int], established: frozenset[str]
) -> tuple[dict[int, dict[str, int | None]], dict[str, int | None]]:
    """Who each step (by original position) reads from, and who writes each fact last;
    a required read that is missing counts as a different flow."""
    last: dict[str, int | None] = {fact: None for fact in established}
    reads: dict[int, dict[str, int | None]] = {}
    for name, step in zip(names, protocol):
        read: dict[str, int | None] = {}
        for fact in step.reads | step.optional_reads:
            if fact in last:
                read[fact] = last[fact]
            elif fact in step.reads:
                read[fact] = -1  # missing: no order with this is the same
        reads[name] = read
        for fact in step.writes:
            last[fact] = name
    return reads, last


# ===========================================================
# Describing a protocol: for tables, drawings and the site
# ===========================================================
class Call(Model):
    """One function in ``wahlwerk.calc`` and how it is called: the bottom of the chain
    from a step down to its arithmetic."""

    formula: str = Field(description="Its full name, e.g. ``wahlwerk.calc.plurality.plurality``.")
    call: str = Field(description="Its parameters as written, defaults included, e.g. ``plurality(votes, seats=1)``.")


class Use(Model):
    """A core concept a step uses: a law-free model (a method, a threshold) with its
    settings and the functions in ``wahlwerk.calc`` it computes with. One link of the
    chain from a step down to ``wahlwerk.calc``; a concept can hold another."""

    field: str = Field(description="Where it sits in the step, e.g. ``method`` or ``method.method``.")
    kind: str = Field(description="Its class, e.g. ``Plurality``.")
    arguments: tuple[tuple[str, str], ...] = Field(default_factory=tuple, description="What the step hands it, in words, e.g. ``(\"seats\", \"1\")``: the arguments it is called with besides its settings.")
    parameters: tuple[tuple[str, str], ...] = Field(default_factory=tuple, description="Its settings that are not concepts themselves, e.g. ``(\"share\", \"1/20\")``.")
    calls: tuple[Call, ...] = Field(default_factory=tuple, description="The functions it computes with.")


class StepNode(Model):
    """One step as a reader sees it: what it is, what it follows, what it reads and
    writes, its stage, and the steps it holds."""

    path: tuple[int | str, ...] = Field(description="Where it sits, as for :mod:`wahlwerk.law.edit`, e.g. ``(5, \"protocol\", 0)``.")
    kind: str = Field(description="The step's class, e.g. ``ApportionSeats``.")
    title: str = Field(description="What it does, in a few words: a sequence's title, else the first sentence of its class.")
    parameters: tuple[tuple[str, str], ...] = Field(default_factory=tuple, description="Its settings, each as (field, short value), e.g. ``(\"seats\", \"83\")``.")
    citation: str | None = Field(default=None, description="The provision it follows, if recorded.")
    reads: tuple[str, ...] = Field(default_factory=tuple, description="The facts it needs.")
    optional_reads: tuple[str, ...] = Field(default_factory=tuple, description="The facts it uses when present.")
    writes: tuple[str, ...] = Field(default_factory=tuple, description="The facts it establishes.")
    stage: int = Field(ge=0, description="Its stage among its siblings: 0 reads only what comes from outside.")
    depends_on: tuple[int, ...] = Field(default_factory=tuple, description="The positions of the siblings it reads from.")
    holds: str | None = Field(default=None, description="The field holding its own steps, e.g. ``steps`` or ``protocol``.")
    uses: tuple[Use, ...] = Field(default_factory=tuple, description="The core concepts it computes with, outermost first.")
    calls: tuple[Call, ...] = Field(default_factory=tuple, description="The functions in ``wahlwerk.calc`` it computes with itself.")
    children: tuple[StepNode, ...] = Field(default_factory=tuple, description="The steps it holds, described the same way.")


def describe(
    protocol: AllocationProtocol,
    *,
    prefix: tuple[int | str, ...] = (),
    established: frozenset[str] = INPUT_FACTS,
) -> tuple[StepNode, ...]:
    """Every step of ``protocol`` as a :class:`StepNode`, nested steps inside."""
    read_from = sources(protocol, established)
    stage = stages(protocol, established)
    nodes = []
    for position, step in enumerate(protocol):
        path = (*prefix, position)
        holds, inner = _held(step)
        children: tuple[StepNode, ...] = ()
        if inner is not None and holds is not None:
            outside = established | frozenset().union(*(s.writes for s in protocol[:position]))
            children = describe(inner, prefix=(*path, holds), established=frozenset(outside))
        nodes.append(
            StepNode(
                path=path,
                kind=type(step).__name__,
                title=_title(step),
                parameters=_parameters(step),
                citation=step.citation,
                reads=tuple(sorted(step.reads)),
                optional_reads=tuple(sorted(step.optional_reads)),
                writes=tuple(sorted(step.writes)),
                stage=stage[position],
                depends_on=tuple(sorted({w for w in read_from[position].values() if w is not None})),
                holds=holds,
                uses=uses(step),
                calls=calls_of(step),
                children=children,
            )
        )
    return tuple(nodes)


def calls_of(model: BaseModel) -> tuple[Call, ...]:
    """The functions in ``wahlwerk.calc`` ``model`` computes with itself: its class's
    ``formulas``, through which it calls them."""
    return tuple(
        Call(formula=f"{f.__module__}.{f.__qualname__}", call=_signature(f))
        for f in getattr(type(model), "formulas", ())
    )


def uses(model: BaseModel, prefix: str = "") -> tuple[Use, ...]:
    """Each core concept held by ``model`` (and by those, and so on), outermost first,
    with its settings and formulas: ``ElectPerUnit`` uses ``Plurality``, which computes
    with :func:`wahlwerk.calc.plurality.plurality`. Read from the objects, never declared."""
    found: list[Use] = []
    for name in type(model).model_fields:
        value = getattr(model, name)
        held = value if isinstance(value, tuple) else (value,)
        for index, item in enumerate(held):
            if not isinstance(item, BaseModel) or isinstance(item, AllocationStep):
                continue
            field = f"{prefix}{name}" + (f".{index}" if isinstance(value, tuple) else "")
            settings = tuple(
                (key, _short(getattr(item, key)))
                for key in _set_fields(item)
                if not _is_concept(getattr(item, key))
            )
            given = model.passes.get(name, ()) if isinstance(model, AllocationStep) else ()
            found.append(Use(field=field, kind=type(item).__name__, arguments=given, parameters=settings, calls=calls_of(item)))
            found.extend(uses(item, f"{field}."))
    return tuple(found)


def _is_concept(value: Any) -> bool:
    held = value if isinstance(value, tuple) else (value,)
    return any(isinstance(v, BaseModel) for v in held)


def _signature(function: Any) -> str:
    """``name(a, b=1, *, c=True)``: the parameters as written, without annotations."""
    parts = []
    star = False
    for parameter in inspect.signature(function).parameters.values():
        if parameter.kind is parameter.KEYWORD_ONLY and not star:
            parts.append("*")
            star = True
        text = parameter.name
        if parameter.default is not parameter.empty:
            default = parameter.default
            text += f"={default.__name__ if callable(default) else repr(default)}"
        parts.append(text)
    return f"{function.__name__}({', '.join(parts)})"


def protocol_data(protocol: AllocationProtocol) -> list[dict[str, Any]]:
    """The description as plain JSON-able data, for a drawing or a web page."""
    return [node.model_dump(mode="json") for node in describe(protocol)]


def protocol_table(protocol: AllocationProtocol) -> str:
    """A plain-text table of the protocol: one row per step, nested steps indented."""
    rows = [("", "step", "follows", "reads", "writes")]
    for node, depth in _walk(describe(protocol)):
        label = "  " * depth + node.kind
        if node.kind == "StepSequence":
            label += f' "{node.title}"'
        if node.parameters:
            label += " " + ", ".join(f"{k}={v}" for k, v in node.parameters)
        rows.append(
            (
                ".".join(str(p) for p in node.path if isinstance(p, int)),
                label,
                node.citation or "",
                ", ".join(node.reads),
                ", ".join(node.writes),
            )
        )
        for call in node.calls:
            rows.append(("", "  " * (depth + 1) + f"= {call.formula.removeprefix('wahlwerk.')}", "", "", ""))
        for use in node.uses:
            indent = "  " * (depth + 1 + use.field.count("."))
            needs = ", ".join(f"{k}={v}" for k, v in (*use.arguments, *use.parameters))
            rows.append(("", f"{indent}-> {use.kind}" + (f" ({needs})" if needs else ""), "", "", ""))
            for call in use.calls:
                rows.append(("", f"{indent}   = {call.formula.removeprefix('wahlwerk.')}", "", "", ""))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows]
    lines.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(lines)


def protocol_html(protocol: AllocationProtocol, caption: str = "") -> str:
    """The same table as :func:`protocol_table`, as plain HTML."""
    th = "padding:2px 10px;border-bottom:2px solid #555;text-align:left"
    td = "padding:1px 10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top"
    lines = ["<table style='border-collapse:collapse;font-family:monospace;font-size:12px'>"]
    if caption:
        lines.append(
            f"<caption style='text-align:left;font-weight:bold;padding-bottom:2px'>{escape(caption)}</caption>"
        )
    lines.append(
        "<thead><tr>"
        + "".join(f"<th style='{th}'>{h}</th>" for h in ("", "step", "follows", "reads", "writes"))
        + "</tr></thead><tbody>"
    )
    for node, depth in _walk(describe(protocol)):
        name = escape(node.kind) + (f" <i>{escape(node.title)}</i>" if node.kind == "StepSequence" else "")
        settings = ", ".join(f"{k}={v}" for k, v in node.parameters)
        cells = (
            ".".join(str(p) for p in node.path if isinstance(p, int)),
            f"<span style='padding-left:{depth * 1.5}em'>{name}</span>"
            + (f"<br><span style='padding-left:{depth * 1.5}em;color:#777'>{escape(settings)}</span>" if settings else ""),
            escape(node.citation or ""),
            escape(", ".join(node.reads)),
            escape(", ".join(node.writes)),
        )
        lines.append("<tr>" + "".join(f"<td style='{td}'>{cell}</td>" for cell in cells) + "</tr>")
    lines.append("</tbody></table>")
    return "\n".join(lines)


def _walk(nodes: tuple[StepNode, ...], depth: int = 0) -> Iterator[tuple[StepNode, int]]:
    for node in nodes:
        yield node, depth
        yield from _walk(node.children, depth + 1)


def _held(step: AllocationStep) -> tuple[str | None, AllocationProtocol | None]:
    for name in type(step).model_fields:
        value = getattr(step, name)
        if isinstance(value, tuple) and value and all(isinstance(v, AllocationStep) for v in value):
            return name, value
    return None, None


_HIDDEN = {"citation", "title", "steps", "protocol"}


def _parameters(step: AllocationStep) -> tuple[tuple[str, str], ...]:
    """The settings that differ from their defaults, the ones a reader needs."""
    return tuple(
        (name, _short(getattr(step, name)))
        for name in _set_fields(step)
        if name not in _HIDDEN
    )


def _set_fields(model: BaseModel) -> list[str]:
    fields = type(model).model_fields
    return [
        name
        for name, info in fields.items()
        if getattr(model, name) is not None
        and (info.is_required() or getattr(model, name) != info.get_default(call_default_factory=True))
    ]


def _short(value: Any) -> str:
    """A setting as a reader would write it: ``MajorityFirst(HareNiemeyer)``, ``1/20``."""
    if isinstance(value, BaseModel):
        inner = [_short(getattr(value, name)) for name in _set_fields(value)]
        return f"{type(value).__name__}({', '.join(inner)})" if inner else type(value).__name__
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, (frozenset, tuple)):
        return "{" + ", ".join(sorted(_short(v) for v in value)) + "}"
    return str(value)


def _title(step: AllocationStep) -> str:
    title = getattr(step, "title", None)
    if isinstance(title, str):
        return title
    doc = inspect.getdoc(type(step)) or type(step).__name__
    first = " ".join(doc.split("\n\n")[0].split())
    first = re.sub(r":[a-z]+:`~?([^`]+)`", lambda m: m.group(1).split(".")[-1], first)
    first = first.replace("``", "")
    return first.split(". ")[0].split(": ")[0].rstrip(".")
