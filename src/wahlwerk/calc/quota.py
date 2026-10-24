r"""Quotas: the votes one seat is worth, given :math:`V` votes and :math:`S` seats.

========================  ==========================================
quota                     :math:`Q`
========================  ==========================================
Hare                      :math:`V / S`
Hagenbach-Bischoff        :math:`V / (S + 1)`
Droop                     :math:`\lfloor V / (S + 1) \rfloor + 1`
Imperiali                 :math:`V / (S + 2)`
========================  ==========================================

Each is a plain function of two numbers, ``quota(V, S)``, exact for exact input; the
largest remainder methods (:mod:`wahlwerk.calc.remainder`) take any of them.

>>> hare(100, 8), droop(100, 8)
(Fraction(25, 2), 12)

:func:`whole_seats` is the first step of every quota method, :math:`\lfloor v_i / Q \rfloor`.
"""

from __future__ import annotations

import math

from wahlwerk.calc._input import Number, div, to_number

__all__ = ["droop", "hagenbach_bischoff", "hare", "imperiali", "whole_seats"]


def hare(votes: Number, seats: int) -> Number:
    r"""Hare: :math:`Q = V / S`."""
    return div(to_number(votes, name="votes"), _seats(seats))


def hagenbach_bischoff(votes: Number, seats: int) -> Number:
    r"""Hagenbach-Bischoff: :math:`Q = V / (S + 1)`."""
    return div(to_number(votes, name="votes"), _seats(seats, allow_zero=True) + 1)


def droop(votes: Number, seats: int) -> Number:
    r"""Droop: :math:`Q = \lfloor V / (S + 1) \rfloor + 1`, the smallest whole number of
    votes that only :math:`S` keys can reach."""
    return math.floor(hagenbach_bischoff(votes, seats)) + 1


def imperiali(votes: Number, seats: int) -> Number:
    r"""Imperiali (quota): :math:`Q = V / (S + 2)`."""
    return div(to_number(votes, name="votes"), _seats(seats, allow_zero=True) + 2)


def whole_seats(votes: Number, quota: Number) -> int:
    r"""The whole seats a quota gives: :math:`\lfloor v / Q \rfloor`.

    >>> whole_seats(100, hare(250, 8))
    3
    """
    q = to_number(quota, name="quota")
    if q <= 0:
        raise ValueError(f"quota must be positive, got {q}")
    return math.floor(div(to_number(votes, name="votes"), q))


def _seats(seats: int, *, allow_zero: bool = False) -> int:
    if isinstance(seats, bool) or not isinstance(seats, int):
        raise TypeError(f"seats must be an int, got {type(seats).__name__}")
    if seats < (0 if allow_zero else 1):
        raise ValueError(f"seats must be {'non-negative' if allow_zero else 'positive'}, got {seats}")
    return seats
