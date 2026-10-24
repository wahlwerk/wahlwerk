r"""Divisor methods (highest averages): seats in proportion, by one common divisor.

A divisor method gives key :math:`i` the seats

.. math::

   s_i = \#\{\, k \ge 0 : v_i / D > \sigma(k) \,\}

for a divisor :math:`D` chosen so that :math:`\sum_i s_i = S`: each key's votes over the
divisor, rounded by the method's **signposts** :math:`\sigma(0) < \sigma(1) < \dots`
(:math:`\sigma(k)` lies between :math:`k` and :math:`k+1`; a quotient above it rounds up
to :math:`k+1`). Equivalently, seat :math:`k+1` of key :math:`i` is claimed by
:math:`v_i/\sigma(k)`, and the :math:`S` largest claims win
:cite:`Balinski.FairRepresentationMeeting.2001,Pukelsheim.ProportionalRepresentationApportionment.2017`.

The signposts name the method:

=========================  ================================================  ===========================
method                     :math:`\sigma(k)`                                 divisors (claims)
=========================  ================================================  ===========================
D'Hondt (Jefferson)        :math:`k+1`                                       1, 2, 3, ...
Sainte-Laguë (Webster)     :math:`k+\tfrac12`                                1, 3, 5, ... (scaled)
Adams                      :math:`k`                                         0, 1, 2, ...
Danish                     :math:`k+\tfrac13`                                1, 4, 7, ... (scaled)
Imperiali                  :math:`k+2`                                       2, 3, 4, ...
modified Sainte-Laguë      :math:`0.7`, then :math:`k+\tfrac12`              1.4, 3, 5, ... (scaled)
Dean                       :math:`k(k+1)/(k+\tfrac12)`                       harmonic mean
Huntington-Hill            :math:`\sqrt{k(k+1)}`                             geometric mean
=========================  ================================================  ===========================

Exact input is computed exactly, but fast: the claims are ranked in floating point to
find the last seat, and the last seat and the counts around it are then checked in exact
arithmetic, so a tie is found exactly as the law means it. Floating-point input stays
floating point. A 2-D input is apportioned row by row.

>>> d_hondt({"a": 4160, "b": 3380, "c": 2200}, 10)
SeatResult({'a': 4, 'b': 4, 'c': 2})
>>> sainte_lague([4160, 3380, 2200], 10).seats
array([4, 4, 2])
>>> divisor_range({"a": 4160, "b": 3380, "c": 2200}, 10, D_HONDT)
(832, 845)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal

import numpy as np

from wahlwerk.calc._input import Number, Values, div, prepare, to_number
from wahlwerk.calc._select import largest
from wahlwerk.calc.result import SeatResult

__all__ = [
    "ADAMS",
    "DANISH",
    "DEAN",
    "D_HONDT",
    "HUNTINGTON_HILL",
    "IMPERIALI",
    "MODIFIED_SAINTE_LAGUE",
    "SAINTE_LAGUE",
    "Signposts",
    "adams",
    "d_hondt",
    "danish",
    "dean",
    "divisor_range",
    "highest_averages",
    "huntington_hill",
    "imperiali",
    "modified_sainte_lague",
    "sainte_lague",
    "seats_at",
]


@dataclass(frozen=True)
class Signposts:
    r"""The rounding of a divisor method: :math:`\sigma(k)`, the point between :math:`k`
    and :math:`k+1` seats.

    ``kind="linear"`` is :math:`\sigma(k) = k + \delta` (with ``first`` replacing
    :math:`\sigma(0)` if given); ``"dean"`` and ``"huntington_hill"`` are the harmonic
    and geometric means of :math:`k` and :math:`k+1`. Build one with :meth:`linear` or
    use the constants (:data:`D_HONDT`, :data:`SAINTE_LAGUE`, ...).
    """

    kind: Literal["linear", "dean", "huntington_hill"] = "linear"
    delta: Fraction = Fraction(1)
    first: Fraction | None = None

    @classmethod
    def linear(cls, delta: Number | str, first: Number | str | None = None) -> Signposts:
        r""":math:`\sigma(k) = k + \delta`, and :math:`\sigma(0) =` ``first`` if given.

        A sequence of divisors ``first + step * k`` (D'Hondt 1, 2, 3, ...; Sainte-Laguë
        1, 3, 5, ...) is ``linear(first / step)``: scaling every divisor changes no seat.
        """
        d = Fraction(to_number(delta, name="delta"))
        f = None if first is None else Fraction(to_number(first, name="first"))
        if d < 0 or (f is not None and (f < 0 or f > 1 + d)):
            raise ValueError(f"signposts must increase from 0: delta {d}, first {f}")
        return cls(kind="linear", delta=d, first=f)

    @classmethod
    def from_divisors(cls, first: Number | str, step: Number | str) -> Signposts:
        """The signposts of the divisors ``first, first + step, first + 2 step, ...``."""
        f, s = Fraction(to_number(first, name="first")), Fraction(to_number(step, name="step"))
        if f <= 0 or s <= 0:
            raise ValueError(f"divisors must be positive and increasing: first {f}, step {s}")
        return cls.linear(f / s)

    @property
    def is_squared(self) -> bool:
        """Whether :meth:`exact` gives :math:`\\sigma(k)^2` (Huntington-Hill: irrational)."""
        return self.kind == "huntington_hill"

    def exact(self, k: int) -> Fraction:
        r""":math:`\sigma(k)` exactly, or :math:`\sigma(k)^2` when :attr:`is_squared`."""
        if self.kind == "dean":
            return Fraction(k * (k + 1)) / (k + Fraction(1, 2))
        if self.kind == "huntington_hill":
            return Fraction(k * (k + 1))
        if k == 0 and self.first is not None:
            return self.first
        return k + self.delta

    def floats(self, count: int) -> np.ndarray[Any, np.dtype[np.float64]]:
        r""":math:`\sigma(0), \dots, \sigma(count - 1)` as floats."""
        k = np.arange(count, dtype=np.float64)
        if self.kind == "dean":
            return k * (k + 1) / (k + 0.5)
        if self.kind == "huntington_hill":
            return np.sqrt(k * (k + 1))
        posts = k + float(self.delta)
        if self.first is not None and count:
            posts[0] = float(self.first)
        return posts

    def compare(self, a: Number, k: int, b: Number, m: int) -> int:
        r"""The sign of :math:`a/\sigma(k) - b/\sigma(m)`, exact for exact ``a`` and ``b``.

        A claim over a signpost of 0 is infinite for positive votes; a key without votes
        claims nothing."""
        if not a or not b:
            return (a > 0) - (b > 0) if (a or b) else 0
        sk, sm = self.exact(k), self.exact(m)
        if not sk or not sm:
            return (not sk) - (not sm)
        if self.is_squared:
            left, right = a * a * sm, b * b * sk
        else:
            left, right = a * sm, b * sk
        return (left > right) - (left < right)


D_HONDT = Signposts.linear(1)
"""D'Hondt (Jefferson): divisors 1, 2, 3, ...; rounding down."""
SAINTE_LAGUE = Signposts.linear(Fraction(1, 2))
"""Sainte-Laguë/Schepers (Webster): divisors 1, 3, 5, ...; standard rounding."""
ADAMS = Signposts.linear(0)
"""Adams: rounding up, so every key with votes gets a seat if there are enough."""
DANISH = Signposts.linear(Fraction(1, 3))
"""The Danish method: divisors 1, 4, 7, ..."""
IMPERIALI = Signposts.linear(2)
"""Imperiali (highest averages): divisors 2, 3, 4, ..."""
MODIFIED_SAINTE_LAGUE = Signposts.linear(Fraction(1, 2), first=Fraction(7, 10))
"""Modified Sainte-Laguë (Sweden, Norway): divisors 1.4, 3, 5, ..."""
DEAN = Signposts(kind="dean")
"""Dean: signposts at the harmonic mean of k and k + 1."""
HUNTINGTON_HILL = Signposts(kind="huntington_hill")
"""Huntington-Hill (US House): signposts at the geometric mean of k and k + 1."""


def highest_averages(votes: Values, seats: int, signposts: Signposts = SAINTE_LAGUE) -> SeatResult:
    r"""Apportion ``seats`` by the divisor method with ``signposts``.

    :math:`s_i = \#\{k < S : v_i/\sigma(k) \text{ among the } S \text{ largest claims}\}`.
    ``seats`` may be an ``int`` or, for 2-D input, one ``int`` per row. Raises
    ``ValueError`` for seats to give when every vote is 0.
    """
    prepared = prepare(votes)
    counts = _seat_counts(seats, prepared.values.shape[0] if prepared.is_batch else 1)
    rows = [
        _apportion_row(row, count, signposts)
        for row, count in zip(prepared.rows(), counts)
    ]
    return SeatResult.from_rows(rows, prepared.keys, prepared.is_batch)


def d_hondt(votes: Values, seats: int) -> SeatResult:
    r"""D'Hondt (Jefferson): :math:`\sigma(k) = k + 1`. Favours larger keys.

    >>> d_hondt({"a": 47, "b": 16, "c": 15, "d": 6}, 10).seats
    {'a': 6, 'b': 2, 'c': 2, 'd': 0}
    """
    return highest_averages(votes, seats, D_HONDT)


def sainte_lague(votes: Values, seats: int) -> SeatResult:
    r"""Sainte-Laguë/Schepers (Webster): :math:`\sigma(k) = k + \tfrac12`, standard
    rounding. Neutral between large and small keys.

    >>> sainte_lague({"a": 47, "b": 16, "c": 15, "d": 6}, 10).seats
    {'a': 5, 'b': 2, 'c': 2, 'd': 1}
    """
    return highest_averages(votes, seats, SAINTE_LAGUE)


def adams(votes: Values, seats: int) -> SeatResult:
    r"""Adams: :math:`\sigma(k) = k`, rounding up. Favours smaller keys."""
    return highest_averages(votes, seats, ADAMS)


def danish(votes: Values, seats: int) -> SeatResult:
    r"""The Danish method: :math:`\sigma(k) = k + \tfrac13`."""
    return highest_averages(votes, seats, DANISH)


def imperiali(votes: Values, seats: int) -> SeatResult:
    r"""Imperiali: :math:`\sigma(k) = k + 2`. Favours larger keys more than D'Hondt."""
    return highest_averages(votes, seats, IMPERIALI)


def modified_sainte_lague(votes: Values, seats: int) -> SeatResult:
    r"""Modified Sainte-Laguë: :math:`\sigma(0) = 0.7`, then :math:`k + \tfrac12`."""
    return highest_averages(votes, seats, MODIFIED_SAINTE_LAGUE)


def dean(votes: Values, seats: int) -> SeatResult:
    r"""Dean: :math:`\sigma(k) = k(k+1)/(k+\tfrac12)`, the harmonic mean."""
    return highest_averages(votes, seats, DEAN)


def huntington_hill(votes: Values, seats: int) -> SeatResult:
    r"""Huntington-Hill: :math:`\sigma(k) = \sqrt{k(k+1)}`, the geometric mean.

    >>> huntington_hill({"a": 47, "b": 16, "c": 15, "d": 6}, 10).seats
    {'a': 5, 'b': 2, 'c': 2, 'd': 1}
    """
    return highest_averages(votes, seats, HUNTINGTON_HILL)


def seats_at(votes: Values, divisor: Number | str, signposts: Signposts = SAINTE_LAGUE) -> SeatResult:
    r"""The seats a given divisor :math:`D` gives: :math:`s_i = \#\{k : v_i/D > \sigma(k)\}`.

    A quotient exactly on a signpost is a tie: the key is listed in ``tied`` with its
    seats rounded down, and ``open`` counts such keys. This is how a published
    Wahlschlüssel is checked.

    >>> seats_at({"a": 4160, "b": 3380, "c": 2200}, 840, D_HONDT).seats
    {'a': 4, 'b': 4, 'c': 2}
    """
    d = to_number(divisor, name="divisor")
    if d <= 0:
        raise ValueError(f"divisor must be positive, got {d}")
    prepared = prepare(votes)
    rows = []
    for row in prepared.rows():
        won, tied = [], []
        for v in row:
            q = v / Fraction(d) if prepared.is_exact and not isinstance(d, float) else float(v) / float(d)
            count = _count_below(signposts, q)
            on = bool(v) and _on_signpost(signposts, q, count)
            won.append(count)
            tied.append(on)
        rows.append((won, tied, sum(tied)))
    return SeatResult.from_rows(rows, prepared.keys, prepared.is_batch)


def divisor_range(
    votes: Values, seats: int, signposts: Signposts = SAINTE_LAGUE
) -> tuple[Number, Number]:
    r"""Every divisor strictly between the two numbers returned gives the apportionment
    of ``seats``: the claims of the last seat won and the first seat lost,
    :math:`(c_{S+1}, c_S)`.

    One scenario only. For Huntington-Hill the bounds are floats (square roots). Equal
    bounds mean a tie: no divisor decides the last seat.
    """
    prepared = prepare(votes)
    if prepared.is_batch:
        raise ValueError("divisor_range takes one scenario")
    row = prepared.rows()[0]
    claims = sorted(
        ((v, k) for v in row if v for k in range(seats + 1)),
        key=_ClaimKey.factory(signposts),
        reverse=True,
    )
    if len(claims) <= seats:
        raise ValueError("fewer claims than seats")
    return _claim_value(claims[seats], signposts), _claim_value(claims[seats - 1], signposts)


def _apportion_row(row: list[Any], seats: int, sp: Signposts) -> tuple[list[int], list[bool], int]:
    n = len(row)
    if isinstance(seats, bool) or not isinstance(seats, (int, np.integer)):
        raise TypeError(f"seats must be an int, got {type(seats).__name__}")
    seats = int(seats)
    if seats < 0:
        raise ValueError(f"seats is negative: {seats}")
    if seats == 0:
        return [0] * n, [False] * n, 0
    if not any(row):
        raise ValueError(f"cannot apportion {seats} seats: every weight is 0")
    # Rank in floating point to find the claim of the last seat ...
    vf = np.asarray([float(v) for v in row])
    posts = sp.floats(seats)
    with np.errstate(divide="ignore", invalid="ignore"):
        grid = vf[:, None] / posts[None, :]
    grid[vf == 0, :] = 0.0
    flat = grid.ravel()
    pick = int(np.argpartition(-flat, seats - 1)[seats - 1])
    edge_key, edge_k = divmod(pick, seats)
    edge = (row[edge_key], edge_k)
    # ... then count around it exactly.
    above, at = [], []
    for v in row:
        a = _claims_above(sp, v, edge, seats)
        above.append(a)
        at.append(a < seats and bool(v) and sp.compare(v, a, edge[0], edge[1]) == 0)
    total_above = sum(above)
    if not total_above < seats <= total_above + sum(at):
        # The float ranking was off (claims closer than float precision): rank exactly.
        claims = [(_ClaimKey(sp, v, k), i) for i, v in enumerate(row) if v for k in range(seats)]
        return largest(claims, seats, n)
    left = seats - total_above
    if left == sum(at):
        return [a + t for a, t in zip(above, at)], [False] * n, 0
    return above, at, left


def _claims_above(sp: Signposts, v: Any, edge: tuple[Any, int], seats: int) -> int:
    """How many of the first ``seats`` claims of ``v`` exceed the edge claim: the claims
    fall with k, so the first k not above it, by bisection."""
    if not v:
        return 0
    lo, hi = 0, seats
    while lo < hi:
        mid = (lo + hi) // 2
        if sp.compare(v, mid, edge[0], edge[1]) > 0:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _count_below(sp: Signposts, q: Any) -> int:
    """The number of signposts strictly below ``q``."""
    if not q:
        return 0
    lo, hi = 0, 1
    while _post_below(sp, hi, q):
        hi *= 2
    while lo < hi:
        mid = (lo + hi) // 2
        if _post_below(sp, mid, q):
            lo = mid + 1
        else:
            hi = mid
    return lo


def _post_below(sp: Signposts, k: int, q: Any) -> bool:
    post = sp.exact(k)
    if isinstance(q, float):
        return bool((math.sqrt(post) if sp.is_squared else float(post)) < q)
    return bool(post < q * q if sp.is_squared else post < q)


def _on_signpost(sp: Signposts, q: Any, k: int) -> bool:
    post = sp.exact(k)
    if isinstance(q, float):
        return bool((math.sqrt(post) if sp.is_squared else float(post)) == q)
    return bool(post == q * q if sp.is_squared else post == q)


def _claim_value(claim: tuple[Any, int], sp: Signposts) -> Number:
    v, k = claim
    post = sp.exact(k)
    if not post:
        return math.inf
    if sp.is_squared:
        return float(v) / math.sqrt(post)
    if isinstance(v, float):
        return v / float(post)
    return div(v, post)


@dataclass(frozen=True)
class _ClaimKey:
    """A claim ``v / sigma(k)``, ordered exactly."""

    sp: Signposts
    v: Any
    k: int

    @staticmethod
    def factory(sp: Signposts) -> Any:
        return lambda claim: _ClaimKey(sp, claim[0], claim[1])

    def __lt__(self, other: _ClaimKey) -> bool:
        return self.sp.compare(self.v, self.k, other.v, other.k) < 0

    def __gt__(self, other: _ClaimKey) -> bool:
        return self.sp.compare(self.v, self.k, other.v, other.k) > 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _ClaimKey):
            return NotImplemented
        return self.sp.compare(self.v, self.k, other.v, other.k) == 0

    def __hash__(self) -> int:
        return 0


def _seat_counts(seats: Any, rows: int) -> list[int]:
    if np.ndim(seats) == 0:
        return [seats] * rows
    counts = list(np.asarray(seats).tolist())
    if len(counts) != rows:
        raise ValueError(f"one seat count per scenario: {rows} rows, {len(counts)} counts")
    return counts
