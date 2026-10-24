r"""wahlwerk.calc: the formulas of electoral systems, each written once.

Plain numbers or numpy arrays in, plain numbers or arrays out (:mod:`._input` has the
rules): a mapping ``{"spd": 312, "cdu": 278}`` gives a mapping back, an array gives an
array, a 2-D array is many scenarios at once. Exact input (``int``, ``Fraction``,
``"32.5"``) is computed exactly; float input in floating point. Equal claims are never
decided by order: a seat formula returns a :class:`~.result.SeatResult` that names the
tie.

The package depends on numpy alone and on nothing of wahlwerk; the wahlwerk engine does
all its arithmetic here. Modules build on each other in layers, lower never importing
higher:

1. ``share``, ``quota``, ``result``: shares, quotas, the seat result
2. ``divisor``, ``remainder``, ``plurality``: the seat formulas
3. ``majority``, ``threshold``, ``compensation``: clauses around them
4. ``proportionality``, ``fragmentation``: measures of a result
5. ``coalition``, ``power``: majorities and power in a chamber
6. ``notation``: the symbols all of them use; ``types``: the types they take and return

>>> import wahlwerk.calc as wc
>>> wc.divisor.sainte_lague({"a": 4160, "b": 3380, "c": 2200}, 10).seats
{'a': 4, 'b': 4, 'c': 2}
>>> wc.fragmentation.effective_number([40, 35, 15, 10])
Fraction(200, 63)
"""

from __future__ import annotations

from wahlwerk.calc import (
    coalition,
    compensation,
    divisor,
    fragmentation,
    majority,
    notation,
    plurality,
    power,
    proportionality,
    quota,
    remainder,
    result,
    share,
    threshold,
    types,
)

LAYERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Shares, quotas, the seat result", ("share", "quota", "result")),
    ("Seat formulas", ("divisor", "remainder", "plurality")),
    ("Clauses around them", ("majority", "threshold", "compensation")),
    ("Measures of a result", ("proportionality", "fragmentation")),
    ("Coalitions and power", ("coalition", "power")),
)
"""The modules in their layers, lowest first; a module imports only from layers below
its own. The API reference and the website list them in this order."""

__all__ = [
    "LAYERS",
    "coalition",
    "compensation",
    "divisor",
    "fragmentation",
    "majority",
    "notation",
    "plurality",
    "power",
    "proportionality",
    "quota",
    "remainder",
    "result",
    "share",
    "threshold",
    "types",
]
