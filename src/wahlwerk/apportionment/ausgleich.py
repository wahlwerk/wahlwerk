"""Überhang and Ausgleich: when options hold more seats than their proportional share.

In mixed systems an option (a party) may win more seats outright, in Wahlkreise, than an
apportionment of all the seats gives it. Those seats are its Überhang (:func:`overhang`).
Laws answer it in different ways: keep the Überhang and add it to the seats, or add
seats until the apportionment covers every option's seats (Ausgleich, :class:`Ausgleich`),
or a mixture, as Sec. 35 (8) LWG LSA does. The pieces here are law-free; a law's steps
combine them. Modelled on votelib's ``AllowOverhang`` and ``LevelOverhang``
(github.com/simberaj/votelib). The formulas are :mod:`wahlwerk.calc.compensation`.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import (
    ApportionmentMethod,
    _check_seats,
    _exact_weights,
)
from wahlwerk.apportionment.result import Apportionment
from wahlwerk.calc import compensation as calc
from wahlwerk.model import Model, Seats

__all__ = ["Ausgleich", "overhang"]


def overhang(apportionment: Apportionment, minimum: Mapping[str, int]) -> dict[str, int]:
    """The seats by which each option's ``minimum`` exceeds its decided seats, for the options
    where it does: its Überhang. Options missing from the apportionment have no seats."""
    needed = _check_minimum(minimum)
    if not needed:
        return {}
    excess = calc.overhang({option: apportionment.get(option) or 0 for option in needed}, needed)
    assert isinstance(excess, dict)
    return {option: seats for option, seats in excess.items() if seats > 0}


class Ausgleich(Model):
    """Add seats one at a time until the apportionment gives every option at least its
    ``minimum``: the smallest number of seats without Überhang.

    Each larger size is apportioned afresh by ``method``, so the result is proportional
    in the larger size. If ``limit`` is set and reached first, it raises.
    """

    method: SerializeAsAny[ApportionmentMethod] = Field(
        description="The method apportioning each size, e.g. ``SainteLague()``.",
    )
    limit: Seats | None = Field(
        default=None,
        description="The largest size to try; ``None`` for no limit.",
    )

    def apportion(
        self,
        weights: Mapping[str, int | Fraction],
        seats: int,
        minimum: Mapping[str, int],
    ) -> Apportionment:
        """The apportionment of the smallest size of at least ``seats`` seats in which
        each option gets at least ``minimum[option]``.

        A tie decides the size only if the lot could still cover every minimum: then
        the tied apportionment is returned, to be decided by
        :meth:`~wahlwerk.apportionment.result.Apportionment.with_lot`; if the lot
        leaves an Überhang, apportion again from one seat more. Raises ``ValueError``
        for a minimum on an option without weight, or when ``limit`` is passed.
        """
        exact = _exact_weights(weights)
        _check_seats(seats)
        needed = _check_minimum(minimum)
        for option, count in needed.items():
            if count and not exact.get(option):
                raise ValueError(
                    f"no size can give {option!r} its {count} seats: it has no weight"
                )
        minimum_of = {option: needed.get(option, 0) for option in exact}
        result = calc.smallest_size(
            exact, seats, minimum_of, self.method.calculate, limit=self.limit
        )
        return Apportionment.from_seat_result(result)


def _check_minimum(minimum: Mapping[str, int]) -> dict[str, int]:
    checked = {}
    for option, seats in minimum.items():
        if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
            raise TypeError(f"minimum of {option!r} must be a non-negative int, got {seats!r}")
        checked[option] = seats
    return checked
