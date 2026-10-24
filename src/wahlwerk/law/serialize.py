"""Laws as data: a law, or any model in it, to plain JSON-ready values and back.

A protocol holds steps of many types, and steps hold methods and thresholds of many
types, so every model is written with its type, the name of its class in the engine:
``{"type": "wahlwerk.apportionment.remainder.HareNiemeyer"}``. Reading accepts only
models defined in ``wahlwerk``, so a law file can name no other code. Exact values stay
exact: a share is written ``"1/20"``, a date ``"2026-09-06"``.

    text = law_to_json(LWG_2021)
    assert law_from_json(text) == LWG_2021
"""

from __future__ import annotations

import importlib
import json
from datetime import date
from enum import Enum
from fractions import Fraction
from typing import Any

from wahlwerk.law.base import Law
from wahlwerk.model import Model

__all__ = ["SCHEMA", "from_data", "law_from_json", "law_to_json", "to_data"]

SCHEMA = 1
"""The version of the law file format; a change to it is a new number."""

TYPE = "type"
"""The key naming a model's class in its data."""


def _type_name(model: Model) -> str:
    cls = type(model)
    return f"{cls.__module__}.{cls.__qualname__}"


def _model_class(name: str) -> type[Model]:
    """The engine model ``name`` names; ``ValueError`` for anything else."""
    module_name, _, class_name = name.rpartition(".")
    if not (module_name == "wahlwerk" or module_name.startswith("wahlwerk.")):
        raise ValueError(f"type {name!r} is not a wahlwerk model")
    try:
        cls = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError) as error:
        raise ValueError(f"no model {name!r}") from error
    if not (isinstance(cls, type) and issubclass(cls, Model)):
        raise TypeError(f"{name!r} is not a wahlwerk model")
    return cls


def to_data(value: Any) -> Any:
    """``value`` as JSON-ready data: models with their type, tuples as lists,
    frozensets as sorted lists, fractions and dates as strings, enums as their value."""
    if isinstance(value, Model):
        data: dict[str, Any] = {TYPE: _type_name(value)}
        for name in type(value).model_fields:
            data[name] = to_data(getattr(value, name))
        return data
    if isinstance(value, (tuple, list)):
        return [to_data(item) for item in value]
    if isinstance(value, frozenset):
        return sorted((to_data(item) for item in value), key=json.dumps)
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int, str)):
        return value
    raise TypeError(f"cannot write {type(value).__name__} {value!r} as law data")


def from_data(data: Any) -> Any:
    """The values :func:`to_data` wrote: every dict with a ``type`` becomes that model,
    validated; everything else is left for the model it belongs to to validate."""
    if isinstance(data, dict):
        if TYPE not in data:
            return {key: from_data(item) for key, item in data.items()}
        cls = _model_class(str(data[TYPE]))
        fields = {key: from_data(item) for key, item in data.items() if key != TYPE}
        return cls.model_validate(fields)
    if isinstance(data, list):
        return [from_data(item) for item in data]
    return data


def law_to_json(law: Law, *, indent: int | None = 1) -> str:
    """``law`` as a JSON document, with the format's ``schema``."""
    return json.dumps(
        {"schema": SCHEMA, "law": to_data(law)}, ensure_ascii=False, indent=indent
    )


def law_from_json(text: str) -> Law:
    """The law in a JSON document written by :func:`law_to_json`, checked like any law.

    Raises ``ValueError`` for an unknown ``schema``, an unknown model or a law that
    fails its checks, and ``TypeError`` when the file names something that is not a
    wahlwerk model, or holds something that is not a law.
    """
    document = json.loads(text)
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ValueError(f"law file schema must be {SCHEMA}, got {document.get('schema')!r}")
    law = from_data(document.get("law"))
    if not isinstance(law, Law):
        raise TypeError(f"law file holds a {type(law).__name__}, not a Law")
    return law
