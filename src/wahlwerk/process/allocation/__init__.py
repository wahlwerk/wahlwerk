"""Allocation: the external process that turns a popular vote into seats.

A law is an ordered protocol of steps over an :class:`~wahlwerk.process.allocation.base.Allocation`.
The package exposes its modules, never their names, grouped by what the steps decide:

- ``base``: the working record, the step base, protocols and :func:`check_protocol`
- ``count``: summing the tally to the levels the law counts at
- ``district``: who wins each single-seat unit
- ``eligibility``: which parties take part, and how many seats they share
- ``seats``: each party's entitlement, and its list seats after its Wahlkreis seats
- ``mehrsitze``: raising the house for Mehrsitze and allocating again
- ``chamber``: forming the chamber, one mandate per seat
- ``allocate``: the process, :func:`allocate` (vote and law to chamber) and :func:`derive`

The design and the plan are in ``README.md`` beside this file. The arithmetic the
steps need (apportionment, thresholds, Ausgleich) is in :mod:`wahlwerk.apportionment`.
"""

from __future__ import annotations

from wahlwerk.process.allocation import (
    allocate,
    base,
    chamber,
    count,
    district,
    eligibility,
    mehrsitze,
    seats,
)

__all__ = [
    "allocate",
    "base",
    "chamber",
    "count",
    "district",
    "eligibility",
    "mehrsitze",
    "seats",
]
