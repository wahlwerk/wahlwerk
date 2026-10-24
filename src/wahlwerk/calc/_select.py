"""Picking the largest claims without letting order decide."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

__all__ = ["largest"]


def largest(claims: Sequence[tuple[Any, int]], count: int, n: int) -> tuple[list[int], list[bool], int]:
    """Seats won and the tie for the ``count`` largest of ``claims``.

    ``claims`` are ``(value, option index)`` pairs; an option may have several claims, but at
    most one at any value. Returns per option the seats won, whether it is tied, and the
    seats left open: every claim above the ``count``-th largest wins; those equal to it
    win if they all fit, and otherwise they are tied for the seats left.
    """
    won = [0] * n
    tied = [False] * n
    if count == 0:
        return won, tied, 0
    edge = sorted((value for value, _ in claims), reverse=True)[count - 1]
    above = [i for value, i in claims if value > edge]
    at = [i for value, i in claims if value == edge]
    for i in above:
        won[i] += 1
    if len(above) + len(at) == count:
        for i in at:
            won[i] += 1
        return won, tied, 0
    for i in at:
        tied[i] = True
    return won, tied, count - len(above)
