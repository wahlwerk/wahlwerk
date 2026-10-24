"""Deduction: seats won outright taken off a number of seats.

A core concept: given seats per option and the seats each already won outright, what
is left to fill (a party's list seats after its Wahlkreis seats, a chamber's seats after
those won outside the proportional allocation), and what was won beyond the seats (an
option's Überhang). The formulas are :func:`wahlwerk.calc.compensation.remaining` and
:func:`wahlwerk.calc.compensation.overhang`; this names them, so a law can store and
show them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, ClassVar

from wahlwerk.calc import compensation
from wahlwerk.model import Model

__all__ = ["Deduction"]


class Deduction(Model):
    """Seats won outright taken off seats: :meth:`left` gives what is left to fill,
    never below 0, and :meth:`excess` what was won beyond the seats."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (compensation.remaining, compensation.overhang)
    """The functions in ``wahlwerk.calc`` it computes with, called through this attribute."""

    def left(self, seats: Mapping[str, int], won: Mapping[str, int]) -> dict[str, int]:
        """Per option, ``seats`` less ``won``, at least 0; an option missing on one side
        counts 0."""
        remaining, _ = self.formulas
        return _ints(remaining(dict(seats), dict(won))) if seats else {}

    def excess(self, seats: Mapping[str, int], won: Mapping[str, int]) -> dict[str, int]:
        """Per option of ``seats``, how many seats it won beyond them, for the options
        that did."""
        _, overhang = self.formulas
        over = _ints(overhang(dict(seats), dict(won))) if seats else {}
        return {option: n for option, n in over.items() if n > 0}


def _ints(values: Any) -> dict[str, int]:
    assert isinstance(values, dict)
    return {option: int(n) for option, n in values.items()}
