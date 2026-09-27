"""Apportionment: dividing a number of seats among keys in proportion to their weights.

The methods here know nothing about parties, votes or any law. They take opaque string
keys (party ids, Länder, caucuses), non-negative exact weights (votes, population,
seats) and a seat count, and return the seats per key. So the same method serves a
Landtag's list seats, the seats per Land in the Bundestag, committee seats per caucus
or anything else a law divides proportionally. What to divide, among whom and how often
is the caller's business (a law's steps); if a Land's quirk appears here, the
abstraction is broken.

Two families, each sharing one algorithm:

- :class:`DivisorMethod` (highest averages): each key's weight is divided by a
  sequence of divisors, and the seats go to the largest quotients. :class:`DHondt`
  (Jefferson), :class:`SainteLague` (Webster, Sainte-Laguë/Schepers) and any linear
  sequence via :class:`LinearDivisor`.
- :class:`LargestRemainder` (quota methods): each key gets the whole part of its weight
  over a quota, and the seats left go to the largest remainders. :class:`HareNiemeyer`
  (Hamilton) divides by the Hare quota.

Arithmetic is exact (:class:`~fractions.Fraction`); floats are refused, since they both
hide real ties and invent false ones. Where the claims for the last seats are exactly
equal, no seat is guessed: the result carries a :class:`~wahlwerk.apportionment.tie.Tie`,
resolved by :meth:`Apportionment.with_lot` from the lot actually drawn.

Modules, one per family or piece:

- ``method``: :class:`ApportionmentMethod`, the interface all methods share
- ``result``: :class:`Apportionment`, the seats per key and any tie
- ``tie``: :class:`Tie`, seats decided by lot
- ``divisor``: divisor methods; ``remainder``: largest remainder methods
- ``majority``: majority clauses around a method (:class:`MajorityFirst`)
- ``threshold``: which keys take part at all
- ``ausgleich``: Überhang, and growing the house until it is covered

The package exposes these modules, never their names, so the family stays visible:
``wahlwerk.apportionment.divisor.SainteLague``. Everything here depends only on the
foundation. Where an idea or a reference result
comes from outside, it is votelib (github.com/simberaj/votelib).
"""

from __future__ import annotations

from wahlwerk.apportionment import (
    ausgleich,
    divisor,
    majority,
    method,
    remainder,
    result,
    threshold,
    tie,
)
from wahlwerk.apportionment.result import Apportionment

__all__ = [
    "Apportionment",
    "ausgleich",
    "divisor",
    "majority",
    "method",
    "remainder",
    "result",
    "threshold",
    "tie",
]
