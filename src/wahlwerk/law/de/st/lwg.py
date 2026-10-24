"""Wahlgesetz des Landes Sachsen-Anhalt (LWG): the Landtag of Sachsen-Anhalt.

One object per version whose seat allocation differs. The allocation rules are Sec. 1
(1), 32, 33 and 35. Their text is the same in the Fassung that governed the election of
6 June 2021 (last amended 19 March 2021) and in the one current in 2026 (last amended
7 February 2025): at least 83 seats, 41 Wahlkreise, Hare/Niemeyer with a majority
clause, Mehrsitze balanced twice and then only beyond half a Fraktion. The Landtag of
2016 was elected under an earlier version (87 seats, 43 Wahlkreise), not recorded yet.

Not modelled: Sec. 32 S. 2 (the Zweitstimmen of voters who elected an Einzelbewerber
are not counted), which the tally cannot express; no Einzelbewerber won in 2021 or
2026.
"""

from __future__ import annotations

from fractions import Fraction

from wahlwerk.apportionment.majority import MajorityFirst
from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.apportionment.quota import HareQuota
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
from wahlwerk.process.allocation.overhang import (
    RaiseByOverhang,
    RaiseChamberSize,
    SetCaucusSize,
)
from wahlwerk.process.allocation.seats import ApportionSeats, DeductUnitSeats
from wahlwerk.process.allocation.sequence import StepSequence

__all__ = ["ALLOCATE", "CAUCUS", "COUNT", "LWG_2021", "QUALIFY"]

_FIVE_PERCENT = Fraction(5, 100)

COUNT = StepSequence(
    name="CountVotes",
    citation="Sec. 31, 32, 35 (2)",
    steps=(
        SumGroupBy(section="erststimme", level="wahlkreis", citation="Sec. 31, 32"),
        SumGroupBy(section="zweitstimme", level="land", by="party", citation="Sec. 35 (2)"),
    ),
)
"""The counting: the Erststimmen per Wahlkreis and option, the Zweitstimmen in the Land per
option, two tables. Reads only the tally."""

QUALIFY = StepSequence(
    name="ElectAndQualify",
    citation="Sec. 33, 35 (3)",
    steps=(
        SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis", citation="Sec. 33"),
        ApplyThresholdTo(
            threshold=RelativeThreshold(share=_FIVE_PERCENT),
            section="zweitstimme",
            level="land",
            citation="Sec. 35 (3)",
        ),
    ),
)
"""What the counts decide before any seat is apportioned: the winner of each Wahlkreis,
and the parties past the threshold. Reads only the sums."""

ALLOCATE = StepSequence(
    name="AllocateSeats",
    citation="Sec. 35 (4) to (7)",
    steps=(
        SetSeatTotal(section="zweitstimme", citation="Sec. 35 (4)"),
        ApportionSeats(
            method=MajorityFirst(method=HareNiemeyer()),
            section="zweitstimme",
            level="land",
            citation="Sec. 35 (5), (6)",
        ),
        DeductUnitSeats(citation="Sec. 35 (7)"),
    ),
)
"""Sec. 35 (4) to (7): the seats of one chamber size, which Sec. 35 (8) repeats."""

CAUCUS = SetCaucusSize(
    share=_FIVE_PERCENT,
    section="zweitstimme",
    level="land",
    quota=HareQuota(),
    citation="Sec. 35 (8a)",
)
"""Sec. 35 (8a): the seats needed for a Fraktion, measured after each round of Sec. 35 (8)."""

LWG_2021 = Law(
    id="de.st.lwg.2021",
    title="Wahlgesetz des Landes Sachsen-Anhalt (LWG)",
    citation=(
        "LWG in der Fassung der Bekanntmachung vom 18. Februar 2010 (GVBl. LSA S. 80), "
        "zuletzt geändert durch Artikel 2 des Gesetzes vom 19. März 2021 (GVBl. LSA "
        "S. 98); Sec. 1, 32, 33, 35 unchanged in substance up to the Gesetz vom "
        "7. Februar 2025 (GVBl. LSA S. 316)"
    ),
    body="de.st.landtag",
    source=(
        "https://www.landtag.sachsen-anhalt.de/fileadmin/Downloads/Rechtsgrundlagen/"
        "Gesetze_8.WP/2021_Wahlgesetz_LWG.pdf"
    ),
    # In stages: what needs nothing but the law and the tally first (the chamber size,
    # the counting), then what the counts decide, then the seats, then the chamber.
    protocol=(
        SetChamberSize(seats=83, citation="Sec. 1 (1)"),  # "mindestens 83": also the minimum
        COUNT,
        QUALIFY,
        ALLOCATE,
        CAUCUS,
        RaiseByOverhang(  # only while ALLOCATE left overhang to balance
            protocol=(RaiseChamberSize(factor=2, citation="Sec. 35 (8)"), ALLOCATE, CAUCUS),
            full_rounds=2,
            citation="Sec. 35 (8), (8a)",
        ),
        FillVacantSeatsFromLists(),
    ),
)
"""The LWG as it governed the Landtag elections of 2021 and 2026. The day it first
applied is not on record here, so ``in_force_from`` is open; it is not the 2016 law."""
