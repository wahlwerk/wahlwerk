"""Reading inputs and shaping outputs, the same way for every formula.

Every function in this package takes its per-key numbers (votes, seats, weights) as
either

- a **mapping** of key to number, ``{"spd": 312, "cdu": 278}``, which gives a mapping
  back, keys in the same order; or a mapping of key to a sequence of numbers, one per
  scenario, which gives a mapping of key to array back; or
- an **array-like** (a list, a tuple, a numpy array) of numbers, the keys along the last
  axis, which gives an array back. A 2-D array is several scenarios at once, one per row.

Numbers keep their kind, so an exact input gives an exact output:

- ``int``, :class:`~fractions.Fraction`, a decimal or ratio string (``"32.5"``,
  ``"1/3"``) and numpy integer arrays are **exact**: the arithmetic is done on Python
  integers and fractions, and a result that is not whole is a ``Fraction``;
- ``float`` and numpy float arrays are **floating point**: fast, and every result is a
  ``float``. Equal claims (a tie) are then claims equal as floats.

A mapping with one float in it is floating point as a whole. ``bool`` is refused
everywhere, as is a negative count, ``nan`` and infinity.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from numbers import Integral, Real
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from wahlwerk_calc.types import Exact, Number, PerKey, Values

__all__ = [
    "Exact",
    "Number",
    "PerKey",
    "Prepared",
    "Values",
    "as_float_or_exact",
    "div",
    "prepare",
    "prepare_pair",
    "to_number",
]

@dataclass(frozen=True)
class Prepared:
    """Checked per-key input: ``values`` with the keys on the last axis, as a numpy
    array of Python ``int``/``Fraction`` objects (exact) or of ``float64``."""

    values: NDArray[Any]
    keys: tuple[str, ...] | None
    is_exact: bool

    @property
    def is_batch(self) -> bool:
        """Whether there are several scenarios (rows)."""
        return self.values.ndim == 2

    def rows(self) -> list[list[Any]]:
        """The scenarios as lists of Python numbers; one row for a single scenario."""
        if self.is_batch:
            return [list(row) for row in self.values]
        return [list(self.values)]

    def wrap(self, values: ArrayLike) -> PerKey:
        """Per-key results shaped like this input: a dict for keyed input, else an array.

        ``values`` has the same shape as :attr:`values`; exact results stay Python
        objects in a dict and are kept as an object array (or ``int64`` when whole)."""
        array = np.asarray(values)
        if array.dtype == object and all(_is_whole(x) for x in array.ravel()):
            array = array.astype(np.int64)
        if self.keys is None:
            return array
        if array.ndim == 1:
            return {key: _plain(array[i]) for i, key in enumerate(self.keys)}
        return {key: array[..., i] for i, key in enumerate(self.keys)}

    def scalar(self, values: list[Any]) -> Any:
        """One number per scenario: the number itself, or an array over the rows."""
        if self.is_batch:
            return np.asarray(values, dtype=object if self.is_exact else np.float64)
        return values[0]


def to_number(value: Any, *, name: str = "value") -> Number:
    """One input number as ``int``, ``Fraction`` or ``float``; raises ``TypeError`` for
    ``bool`` and anything that is not a number, ``ValueError`` for nan and infinity."""
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a number, got bool {value!r}")
    if isinstance(value, str):
        try:
            return _normal(Fraction(value.strip()))
        except (ValueError, ZeroDivisionError):
            raise ValueError(f"{name} is not a number: {value!r}") from None
    if isinstance(value, Fraction):
        return _normal(value)
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite, got {number}")
        return number
    raise TypeError(f"{name} must be a number, got {type(value).__name__}")


def prepare(
    values: Values,
    *,
    name: str = "votes",
    is_integer: bool = False,
    allow_negative: bool = False,
    keys: Sequence[str] | None = None,
) -> Prepared:
    """Check per-key input and read it into a :class:`Prepared`.

    ``is_integer`` refuses fractions, and floats that are not whole (whole floats become
    ``int``): for formulas that count, such as power indices. ``keys`` orders a mapping
    by these keys, a missing key counting 0 (to compare votes and seats over one set of
    keys).
    """
    if isinstance(values, Mapping):
        found = tuple(values)
        for key in found:
            if not isinstance(key, str) or not key:
                raise TypeError(f"{name} keys must be non-empty strings, got {key!r}")
        order = tuple(keys) if keys is not None else found
        raw = [values.get(key, 0) for key in order]
        if any(_is_sequence(item) for item in raw):
            columns = [np.asarray(item if _is_sequence(item) else [item]) for item in raw]
            length = max(len(column) for column in columns)
            columns = [np.broadcast_to(column, (length,)) for column in columns]
            array = np.stack(columns, axis=-1)
        else:
            array = np.empty(len(raw), dtype=object)
            array[:] = raw
        return _checked(array, order, name, is_integer, allow_negative)
    if keys is not None:
        raise TypeError(f"{name}: keys can only order a mapping")
    array = np.asarray(values)
    if array.ndim == 0:
        array = array.reshape(1)
    if array.ndim > 2:
        raise ValueError(f"{name} must be 1-D (keys) or 2-D (scenarios, keys), got {array.ndim}-D")
    return _checked(array, None, name, is_integer, allow_negative)


def prepare_pair(
    first: Values, second: Values, *, names: tuple[str, str] = ("votes", "seats")
) -> tuple[Prepared, Prepared]:
    """Two per-key inputs over one set of keys: for mappings, the keys of both, a key
    missing on one side counting 0; arrays must have the same shape."""
    if isinstance(first, Mapping) != isinstance(second, Mapping):
        raise TypeError(f"{names[0]} and {names[1]} must both be mappings or both arrays")
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        keys = list(first) + [key for key in second if key not in first]
        return (
            prepare(first, name=names[0], keys=keys),
            prepare(second, name=names[1], keys=keys),
        )
    a, b = prepare(first, name=names[0]), prepare(second, name=names[1])
    if a.values.shape != b.values.shape:
        raise ValueError(
            f"{names[0]} and {names[1]} must have the same shape, "
            f"got {a.values.shape} and {b.values.shape}"
        )
    return a, b


def div(numerator: Number, denominator: Number) -> Number:
    """``numerator / denominator``, exact when both are exact."""
    if isinstance(numerator, float) or isinstance(denominator, float):
        return float(numerator) / float(denominator)
    return _normal(Fraction(numerator) / Fraction(denominator))


def as_float_or_exact(values: Iterable[Any], is_exact: bool) -> NDArray[Any]:
    """Numbers as an object array (exact) or a float64 array."""
    items = list(values)
    if is_exact:
        array = np.empty(len(items), dtype=object)
        array[:] = items
        return array
    return np.asarray(items, dtype=np.float64)


def _checked(
    array: NDArray[Any],
    keys: tuple[str, ...] | None,
    name: str,
    is_integer: bool,
    allow_negative: bool,
) -> Prepared:
    kind = array.dtype.kind
    if kind == "b":
        raise TypeError(f"{name} must be numbers, got booleans")
    if kind in "iu":
        exact = array.astype(object)
        is_exact = True
        converted = exact
    elif kind == "f":
        converted = array.astype(np.float64)
        is_exact = False
        if not np.all(np.isfinite(converted)):
            raise ValueError(f"{name} must be finite, got nan or infinity")
    elif kind in "OUS":
        flat = [to_number(x, name=name) for x in array.ravel()]
        is_exact = not any(isinstance(x, float) for x in flat)
        if is_exact:
            converted = np.empty(array.shape, dtype=object)
            converted.ravel()[:] = flat
        else:
            converted = np.asarray([float(x) for x in flat], dtype=np.float64).reshape(array.shape)
    else:
        raise TypeError(f"{name} must be numbers, got dtype {array.dtype}")
    if is_integer:
        converted, is_exact = _integers(converted, is_exact, name)
    if not allow_negative and converted.size and np.any(converted < 0):
        raise ValueError(f"{name} must not be negative")
    return Prepared(values=converted, keys=keys, is_exact=is_exact)


def _integers(values: NDArray[Any], is_exact: bool, name: str) -> tuple[NDArray[Any], bool]:
    flat = list(values.ravel())
    if not all(_is_whole(x) for x in flat):
        raise TypeError(f"{name} must be whole numbers")
    ints = np.empty(values.shape, dtype=object)
    ints.ravel()[:] = [int(x) for x in flat]
    return ints, True


def _is_whole(value: Any) -> bool:
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return True
    if isinstance(value, Fraction):
        return value.denominator == 1
    if isinstance(value, (float, np.floating)):
        return float(value).is_integer()
    return False


def _is_sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple, np.ndarray)) and np.ndim(value) > 0


def _normal(value: Fraction) -> Exact:
    """A whole Fraction as ``int``."""
    return value.numerator if value.denominator == 1 else value


def _plain(value: Any) -> Any:
    """A numpy scalar as the Python number it holds."""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Fraction):
        return _normal(value)
    return value
