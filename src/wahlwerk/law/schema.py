"""The law file as a JSON Schema: every step type, method and threshold, from the models.

:func:`law_schema` describes the document :func:`~wahlwerk.law.serialize.law_to_json`
writes, so an editor can be generated from it: a form per step type, a choice where a
field takes one of several types (an apportionment method, a threshold, a nested
protocol), and every field's description from the model it belongs to. pydantic writes
a field typed with an abstract base (``AllocationStep``, ``ApportionmentMethod``,
``Threshold``) as an empty object; here it is one of the concrete types, each told apart
by its ``type``, the tag the serializer writes.

The schema checks the shape of a law, not its order: whether a step reads a fact an
earlier step wrote is checked when the law is read (:func:`~wahlwerk.law.serialize.law_from_json`).

    schema = law_schema()
    schema["$defs"]["ApportionSeats"]["properties"]["method"]   # the methods to choose from
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from pydantic.json_schema import models_json_schema

from wahlwerk.law.base import Law
from wahlwerk.law.serialize import SCHEMA, TYPE
from wahlwerk.model import Model

__all__ = ["DIALECT", "law_schema", "types_of"]

DIALECT = "https://json-schema.org/draft/2020-12/schema"
"""The JSON Schema dialect :func:`law_schema` is written in."""

_PACKAGES = ("wahlwerk.apportionment", "wahlwerk.process", "wahlwerk.law")
"""Where the models a law can hold are defined; imported in full, so every type is known."""

_FRACTION = r"^-?[0-9]+(/[0-9]+)?$"
"""An exact fraction as the serializer writes it, ``"1/20"``, or a whole number."""


def _import_all() -> None:
    for name in _PACKAGES:
        package = importlib.import_module(name)
        for module in pkgutil.walk_packages(package.__path__, f"{name}."):
            importlib.import_module(module.name)


def _subclasses(cls: type[Model]) -> list[type[Model]]:
    found: list[type[Model]] = []
    for sub in cls.__subclasses__():
        found.append(sub)
        found.extend(_subclasses(sub))
    return found


def types_of(base: type[Model]) -> tuple[type[Model], ...]:
    """The concrete models defined in wahlwerk that a field typed ``base`` accepts, by name.

    ``types_of(AllocationStep)`` is every step type, the list an editor offers when a
    step is added.
    """
    _import_all()
    candidates = [base, *_subclasses(base)]
    concrete = {
        cls
        for cls in candidates
        if not inspect.isabstract(cls) and cls.__module__.startswith("wahlwerk.")
    }
    return tuple(sorted(concrete, key=lambda cls: cls.__name__))


def _tag(cls: type[Model]) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _ref(cls: type[Model]) -> dict[str, str]:
    return {"$ref": f"#/$defs/{cls.__name__}"}


def _fix_fractions(node: Any) -> None:
    """Give every fraction the pattern the serializer writes and drop pydantic's bounds,
    which are not JSON Schema keywords and would read as numbers."""
    if isinstance(node, dict):
        if node.get("format") == "fraction":
            node["pattern"] = _FRACTION
            node.pop("ge", None)
            node.pop("le", None)
        for value in node.values():
            _fix_fractions(value)
    elif isinstance(node, list):
        for item in node:
            _fix_fractions(item)


def law_schema() -> dict[str, Any]:
    """A JSON Schema (2020-12) for a law file: ``{"schema": 1, "law": {...}}``.

    Every model a law can hold has a definition under ``$defs``, by class name, with a
    required ``type`` naming its class; an abstract base is the ``oneOf`` its concrete
    types.
    """
    _import_all()
    by_name: dict[str, list[type[Model]]] = {}
    for cls in _subclasses(Model):
        if cls.__module__.startswith("wahlwerk."):
            by_name.setdefault(cls.__name__, []).append(cls)

    # A law reaches the abstract bases its fields name, each base its concrete types,
    # and those further bases (a nested protocol, a method inside a method): grow the
    # set of models until it holds every one reachable from Law.
    models: list[type[Model]] = [Law]
    while True:
        _, document = models_json_schema([(cls, "validation") for cls in models])
        defs: dict[str, Any] = document["$defs"]
        reached: list[type[Model]] = []
        for name in defs:
            classes = by_name.get(name, [])
            if len(classes) > 1:
                raise ValueError(f"{len(classes)} models are named {name!r}; their definitions would clash")
            reached.extend(classes)
            for cls in classes:
                if inspect.isabstract(cls):
                    reached.extend(types_of(cls))
        grown = [cls for cls in dict.fromkeys(reached) if cls not in models]
        if not grown:
            break
        models.extend(grown)

    used: dict[str, Any] = {}
    for name, definition in defs.items():
        cls = by_name[name][0]
        if inspect.isabstract(cls):
            used[name] = {
                "title": name,
                "description": inspect.getdoc(cls) or "",
                "oneOf": [_ref(sub) for sub in types_of(cls)],
            }
            continue
        definition["properties"] = {
            TYPE: {"const": _tag(cls), "description": "The model's class in the engine."},
            **definition.get("properties", {}),
        }
        definition["required"] = [TYPE, *definition.get("required", [])]
        used[name] = definition
    _fix_fractions(used)

    return {
        "$schema": DIALECT,
        "title": "wahlwerk law",
        "description": (
            "One version of an electoral law, as written by wahlwerk.law.serialize.law_to_json."
        ),
        "type": "object",
        "properties": {
            "schema": {"const": SCHEMA, "description": "The version of the law file format."},
            "law": _ref(Law),
        },
        "required": ["schema", "law"],
        "additionalProperties": False,
        "$defs": dict(sorted(used.items())),
    }
