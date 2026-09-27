"""How proportionally seats follow weights: indices of disproportionality.

Each function takes the weights (votes) and the seats per key, compares each key's share
of the weights with its share of the seats, and returns one number. A key missing from
one side has 0 there. The indices and their definitions follow votelib's
``crit.proportionality`` (github.com/simberaj/votelib), after Kalogirou, "Measures of
disproportionality"; unlike there, every result is an exact
:class:`~fractions.Fraction`. The Gallagher index is a square root, so it is given
squared (:func:`gallagher_squared`); take the root only to display it.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction

__all__ = [
    "d_hondt",
    "gallagher_squared",
    "lijphart",
    "loosemore_hanby",
    "rae",
    "regression",
    "rose",
    "sainte_lague",
]


def loosemore_hanby(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """Loosemore-Hanby: half the sum of the absolute differences between vote and seat
    shares; 0 when proportional, up to 1."""
    return sum((abs(v - s) for v, s in _shares(votes, seats)), Fraction(0)) / 2


def rose(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """Rose: 1 minus Loosemore-Hanby; 1 when proportional."""
    return 1 - loosemore_hanby(votes, seats)


def gallagher_squared(
    votes: Mapping[str, int | Fraction], seats: Mapping[str, int]
) -> Fraction:
    """The square of the Gallagher (least squares) index: half the sum of the squared
    differences between vote and seat shares. The index itself is its square root."""
    return sum(((v - s) ** 2 for v, s in _shares(votes, seats)), Fraction(0)) / 2


def rae(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """Rae: the mean absolute difference between vote and seat shares, over all keys."""
    pairs = _shares(votes, seats)
    return sum((abs(v - s) for v, s in pairs), Fraction(0)) / len(pairs)


def lijphart(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """Lijphart: the largest absolute difference between a vote and a seat share."""
    return max(abs(v - s) for v, s in _shares(votes, seats))


def sainte_lague(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """Sainte-Laguë: the sum of squared differences, each over the vote share; the index
    the Sainte-Laguë method minimises. Raises ``ValueError`` if a key without votes won
    seats, where it is infinite."""
    return sum((_over(s, v, (v - s) ** 2) for v, s in _shares(votes, seats)), Fraction(0))


def d_hondt(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """D'Hondt: the largest ratio of a seat share to its vote share; 1 when proportional,
    the index the D'Hondt method minimises. Raises ``ValueError`` if a key without votes
    won seats, where it is infinite."""
    return max(_over(s, v, s) for v, s in _shares(votes, seats))


def regression(votes: Mapping[str, int | Fraction], seats: Mapping[str, int]) -> Fraction:
    """The regression index: the slope of seat shares on vote shares through the origin.
    1 when proportional; above 1 favours large keys, below 1 small ones."""
    pairs = _shares(votes, seats)
    return sum((v * s for v, s in pairs), Fraction(0)) / sum((v * v for v, _ in pairs), Fraction(0))


def _over(seat_share: Fraction, vote_share: Fraction, value: Fraction) -> Fraction:
    """``value / vote_share``, which is 0 for a key with neither votes nor seats."""
    if vote_share:
        return value / vote_share
    if seat_share:
        raise ValueError("a key without votes won seats: the index is infinite")
    return Fraction(0)


def _shares(
    votes: Mapping[str, int | Fraction], seats: Mapping[str, int]
) -> list[tuple[Fraction, Fraction]]:
    """Each key's (vote share, seat share), over the keys of both."""
    for name, mapping, kinds in (("votes", votes, (int, Fraction)), ("seats", seats, (int,))):
        if not isinstance(mapping, Mapping):
            raise TypeError(f"{name} must be a mapping of key to number, got {type(mapping).__name__}")
        for key, value in mapping.items():
            if isinstance(value, bool) or not isinstance(value, kinds):
                raise TypeError(f"{name} of {key!r} must be exact, got {type(value).__name__}")
            if value < 0:
                raise ValueError(f"{name} of {key!r} is negative: {value}")
    total_votes = sum(votes.values(), Fraction(0))
    total_seats = sum(seats.values())
    if not total_votes or not total_seats:
        raise ValueError("needs some votes and some seats to compare")
    keys = list(votes) + [key for key in seats if key not in votes]
    return [
        (Fraction(votes.get(key, 0)) / total_votes, Fraction(seats.get(key, 0), total_seats))
        for key in keys
    ]
