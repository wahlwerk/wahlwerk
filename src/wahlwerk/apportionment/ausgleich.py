"""Überhang and Ausgleich: when keys hold more seats than their proportional share.

In mixed systems a key (a party) may win more seats outright, in Wahlkreise, than an
apportionment of the house gives it. Those seats are its Überhang (:func:`overhang`).
Laws answer it in different ways: keep the Überhang and grow the house by it, or grow
the house until the apportionment covers every key's seats (Ausgleich, :class:`Ausgleich`),
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
    """The seats by which each key's ``minimum`` exceeds its decided seats, for the keys
    where it does: its Überhang. Keys missing from the apportionment have no seats."""
    needed = _check_minimum(minimum)
    if not needed:
        return {}
    excess = calc.overhang({key: apportionment.get(key) or 0 for key in needed}, needed)
    assert isinstance(excess, dict)
    return {key: seats for key, seats in excess.items() if seats > 0}


class Ausgleich(Model):
    """Grow the house one seat at a time until the apportionment gives every key at
    least its ``minimum``: the smallest house without Überhang.

    Each larger house is apportioned afresh by ``method``, so the result is proportional
    in the enlarged house. If ``limit`` is set and reached first, it raises.
    """

    method: SerializeAsAny[ApportionmentMethod] = Field(
        description="The method apportioning each house, e.g. ``SainteLague()``.",
    )
    limit: Seats | None = Field(
        default=None,
        description="The largest house to try; ``None`` for no limit.",
    )

    def apportion(
        self,
        weights: Mapping[str, int | Fraction],
        seats: int,
        minimum: Mapping[str, int],
    ) -> Apportionment:
        """The apportionment of the smallest house of at least ``seats`` seats in which
        each key gets at least ``minimum[key]``.

        A tie decides the house only if the lot could still cover every minimum: then
        the tied apportionment is returned, to be decided by
        :meth:`~wahlwerk.apportionment.result.Apportionment.with_lot`; if the lot
        leaves an Überhang, apportion again from one seat more. Raises ``ValueError``
        for a minimum on a key without weight, or when ``limit`` is passed.
        """
        exact = _exact_weights(weights)
        _check_seats(seats)
        needed = _check_minimum(minimum)
        for key, count in needed.items():
            if count and not exact.get(key):
                raise ValueError(
                    f"no house can give {key!r} its {count} seats: it has no weight"
                )
        minimum_of = {key: needed.get(key, 0) for key in exact}
        result = calc.smallest_house(
            exact, seats, minimum_of, self.method.calculate, limit=self.limit
        )
        return Apportionment.from_seat_result(result)


def _check_minimum(minimum: Mapping[str, int]) -> dict[str, int]:
    checked = {}
    for key, seats in minimum.items():
        if isinstance(seats, bool) or not isinstance(seats, int) or seats < 0:
            raise TypeError(f"minimum of {key!r} must be a non-negative int, got {seats!r}")
        checked[key] = seats
    return checked
