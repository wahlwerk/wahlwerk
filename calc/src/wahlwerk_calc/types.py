"""The types every formula takes and returns, for annotating code that calls them."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from numpy.typing import ArrayLike, NDArray

__all__ = ["Exact", "Number", "PerKey", "Values"]

Number = int | float | Fraction
"""One number as this package returns it: ``int`` or ``Fraction`` when exact, else ``float``."""

Exact = int | Fraction
"""An exact number."""

Values = Mapping[str, Any] | ArrayLike
"""Per-key input: a mapping of key to number (or to a sequence, one per scenario), or an
array-like with the keys along the last axis."""

PerKey = dict[str, Any] | NDArray[Any]
"""Per-key output, shaped like the input: a ``dict`` for a mapping, an array otherwise."""
