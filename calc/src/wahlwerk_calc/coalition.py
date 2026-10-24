r"""Coalitions: which groups of keys (caucuses) hold a majority of the seats.

A coalition :math:`C` of keys with seats :math:`s_i` weighs :math:`w(C) = \sum_{i\in C} s_i`
and is **winning** when :math:`w(C) \ge T`, the quota (by default the majority of all
seats, :math:`T = \lfloor S/2 \rfloor + 1`). It is **minimal winning** when every member
is needed, :math:`w(C) - s_i < T` for each :math:`i \in C`, and **minimum winning** when
no winning coalition weighs less :cite:`Riker.TheoryPoliticalCoalitions.1962`.

Coalitions come back as ``frozenset`` of keys (indices for array input), heaviest first,
then by their members. Every subset is checked, so this is for chambers of up to about
twenty caucuses.

>>> [sorted(c) for c in minimal_winning({"a": 40, "b": 35, "c": 15, "d": 10})]
[['a', 'b'], ['b', 'c', 'd'], ['a', 'c']]
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import numpy as np

from wahlwerk_calc._input import Number, Values, prepare, to_number
from wahlwerk_calc.majority import majority_of

__all__ = ["is_winning", "minimal_winning", "minimum_winning", "surplus", "weight", "winning"]

MAX_KEYS = 24
"""More keys than this would mean checking more than 16 million coalitions."""


def weight(seats: Values, coalition: Iterable[Any]) -> int:
    r""":math:`w(C) = \sum_{i \in C} s_i`."""
    keys, s = _seats(seats)
    return sum(int(s[i]) for i in _members(keys, coalition))


def is_winning(seats: Values, coalition: Iterable[Any], quota: Number | str | None = None) -> bool:
    r"""Whether :math:`w(C) \ge T`."""
    _, s = _seats(seats)
    return weight(seats, coalition) >= _quota(s, quota)


def surplus(seats: Values, coalition: Iterable[Any], quota: Number | str | None = None) -> Number:
    r"""The seats beyond the quota, :math:`w(C) - T`; negative when short."""
    _, s = _seats(seats)
    return weight(seats, coalition) - _quota(s, quota)


def winning(seats: Values, quota: Number | str | None = None) -> list[frozenset[Any]]:
    r"""Every winning coalition, :math:`w(C) \ge T`."""
    return _found(seats, quota, minimal=False)


def minimal_winning(seats: Values, quota: Number | str | None = None) -> list[frozenset[Any]]:
    r"""Every minimal winning coalition: winning, and losing without any one member."""
    return _found(seats, quota, minimal=True)


def minimum_winning(seats: Values, quota: Number | str | None = None) -> list[frozenset[Any]]:
    r"""The winning coalitions of the smallest weight (the size principle)."""
    keys, s = _seats(seats)
    found = minimal_winning(seats, quota)
    if not found:
        return []
    lightest = min(sum(int(s[i]) for i in _members(keys, c)) for c in found)
    return [c for c in found if sum(int(s[i]) for i in _members(keys, c)) == lightest]


def _found(seats: Values, quota: Number | str | None, *, minimal: bool) -> list[frozenset[Any]]:
    keys, s = _seats(seats)
    n = len(s)
    if n > MAX_KEYS:
        raise ValueError(f"{n} keys are too many to check every coalition (at most {MAX_KEYS})")
    t = _quota(s, quota)
    w = np.asarray(s, dtype=np.int64)
    masks = np.arange(1 << n, dtype=np.int64)
    bits = (masks[:, None] >> np.arange(n)) & 1
    totals = bits @ w
    win = totals >= math.ceil(t)
    if minimal:
        lightest = np.where(bits == 1, w[None, :], np.iinfo(np.int64).max).min(axis=1)
        win &= totals - lightest < math.ceil(t)
    picked = [(int(totals[m]), tuple(np.flatnonzero(bits[m]).tolist())) for m in np.flatnonzero(win)]
    names = [tuple(keys[i] for i in members) if keys else members for _, members in picked]
    order = sorted(range(len(picked)), key=lambda j: (-picked[j][0], sorted(map(str, names[j]))))
    return [frozenset(names[j]) for j in order]


def _seats(seats: Values) -> tuple[tuple[str, ...] | None, list[int]]:
    prepared = prepare(seats, name="seats", is_integer=True)
    if prepared.is_batch:
        raise ValueError("coalitions take one chamber at a time")
    return prepared.keys, [int(x) for x in prepared.rows()[0]]


def _quota(s: list[int], quota: Number | str | None) -> Number:
    return majority_of(sum(s)) if quota is None else to_number(quota, name="quota")


def _members(keys: tuple[str, ...] | None, coalition: Iterable[Any]) -> list[int]:
    members = list(coalition)
    if keys is None:
        return [int(i) for i in members]
    missing = [m for m in members if m not in keys]
    if missing:
        raise KeyError(f"not in the chamber: {missing}")
    return [keys.index(m) for m in members]
