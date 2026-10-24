"""Landes- und Kommunalwahlgesetz (LKWG M-V): the Landtag of Mecklenburg-Vorpommern.

One object per version whose seat allocation differs. The allocation rules are Sec. 53,
54, 57 and 58, with the seat count from Art. 20 (2) of the Verfassung: at least 71 seats,
36 Wahlkreise, Hare/Niemeyer with a majority clause, Überhang balanced by Ausgleich up
to twice its number, and a raised chamber size made odd. Sec. 54 (2), 57 and 58 are unchanged
since the law came into force on 1 January 2011, up to the Fassung of 1 September 2026
(last amended 8 July 2026). The elections of 1994 to 2006 were held under the earlier
Landeswahlgesetz, not recorded yet.

Not modelled: Sec. 58 (2) S. 2 (the Zweitstimmen of voters who elected an Einzelbewerber,
or a candidate of a party without a Landesliste, are not counted), which the tally cannot
express; no such candidate won in 2011, 2016 or 2021. Nor Sec. 58 (5) S. 4 (a list with
fewer names than seats), which needs the nominations.
"""

from __future__ import annotations

from datetime import date
from fractions import Fraction

from wahlwerk.apportionment.majority import MajorityFirst
from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.law.base import Law
from wahlwerk.process.allocation.chamber import FillVacantSeatsFromLists
from wahlwerk.process.allocation.count import SumGroupBy
from wahlwerk.process.allocation.elect import SingleMandatePerUnit
from wahlwerk.process.allocation.eligibility import (
    ApplyThresholdTo,
    SetChamberSize,
    SetSeatTotal,
)
from wahlwerk.process.allocation.overhang import RaiseUntilBalanced
from wahlwerk.process.allocation.seats import ApportionSeats, DeductUnitSeats
from wahlwerk.process.allocation.sequence import StepSequence

__all__ = ["ALLOCATE", "COUNT", "LKWG_2011", "QUALIFY"]

_FIVE_PERCENT = Fraction(5, 100)

COUNT = StepSequence(
    name="CountVotes",
    citation="Sec. 57, 58 (2) S. 1",
    steps=(
        SumGroupBy(section="erststimme", level="wahlkreis", citation="Sec. 57"),
        SumGroupBy(section="zweitstimme", level="land", by="party", citation="Sec. 58 (2) S. 1"),
    ),
)
"""The counting: the Erststimmen per Wahlkreis and option, the Zweitstimmen in the Land per
option, two tables. Reads only the tally."""

QUALIFY = StepSequence(
    name="ElectAndQualify",
    citation="Sec. 57, 58 (1)",
    steps=(
        SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis", citation="Sec. 57"),
        ApplyThresholdTo(
            threshold=RelativeThreshold(share=_FIVE_PERCENT),
            section="zweitstimme",
            level="land",
            citation="Sec. 58 (1)",
        ),
    ),
)
"""What the counts decide before any seat is apportioned: the winner of each Wahlkreis,
and the parties past the threshold. Reads only the sums."""

ALLOCATE = StepSequence(
    name="AllocateSeats",
    citation="Sec. 58 (2) S. 3 to (5)",
    steps=(
        SetSeatTotal(section="zweitstimme", citation="Sec. 58 (2) S. 3"),
        ApportionSeats(
            method=MajorityFirst(method=HareNiemeyer()),
            section="zweitstimme",
            level="land",
            citation="Sec. 58 (3), (4)",
        ),
        DeductUnitSeats(citation="Sec. 58 (5)"),
    ),
)
"""Sec. 58 (2) S. 3 to (5): the seats of one chamber size, which Sec. 58 (6) repeats."""

LKWG_2011 = Law(
    id="de.mv.lkwg.2011",
    title=(
        "Gesetz über die Wahlen im Land Mecklenburg-Vorpommern "
        "(Landes- und Kommunalwahlgesetz - LKWG M-V)"
    ),
    citation=(
        "LKWG M-V vom 16. Dezember 2010 (GVOBl. M-V S. 690), Fassung gültig vom "
        "1. September 2026 bis 31. Dezember 2028, zuletzt geändert durch Artikel 12 des "
        "Gesetzes vom 8. Juli 2026 (GVOBl. M-V S. 719, 731); Sec. 54, 57, 58 unchanged "
        "since 1 January 2011"
    ),
    body="de.mv.landtag",
    source="https://www.landesrecht-mv.de/bsmv/document/jlr-LKWGMVrahmen",
    in_force_from=date(2011, 1, 1),
    # In stages: the chamber size and the counting, then what the counts decide, then
    # the seats, then the chamber.
    protocol=(
        SetChamberSize(seats=71, citation="Art. 20 (2) Verf. M-V"),  # "mindestens 71": also the minimum
        COUNT,
        QUALIFY,
        RaiseUntilBalanced(
            protocol=(ALLOCATE,), limit=2, has_odd_size=True, citation="Sec. 58 (6)"
        ),
        FillVacantSeatsFromLists(),
    ),
)
"""The LKWG as it has governed the Landtag elections since 2011 (2011, 2016, 2021, 2026)."""
