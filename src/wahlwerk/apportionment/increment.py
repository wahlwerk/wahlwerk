"""Increment: a size raised for seats won beyond it.

A core concept: a number of seats grows by ``factor`` seats for each seat of
overhang, as a chamber is raised to balance Überhang (twice the Mehrsitze in
Sec. 35 (8) LWG LSA). The formula is :func:`wahlwerk.calc.compensation.raised`; this
names it and its factor, so a law can store and show them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from pydantic import Field

from wahlwerk.calc import compensation
from wahlwerk.model import Model

__all__ = ["Increment"]


class Increment(Model):
    """Raise a size by ``factor`` seats per seat of overhang."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (compensation.raised,)
    """The functions in ``wahlwerk.calc`` it computes with, called through this attribute."""

    factor: int = Field(
        default=1,
        ge=1,
        description="How many seats the size grows by per seat of overhang, e.g. 2.",
    )

    def of(self, size: int, overhang: Mapping[str, int]) -> int:
        """``size`` raised by ``factor`` times the overhang summed over the options."""
        (raised,) = self.formulas
        return int(raised(size, dict(overhang), self.factor))
