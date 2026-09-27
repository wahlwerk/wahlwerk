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
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.law.base import Law
from wahlwerk.process.allocation.chamber import FormChamber
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.district import ElectDistricts
from wahlwerk.process.allocation.eligibility import (
    ApplyThreshold,
    SetHouse,
    SetSeatTotal,
)
from wahlwerk.process.allocation.mehrsitze import FraktionSize, RepeatForMehrsitze
from wahlwerk.process.allocation.seats import ApportionSeats, DeductDistrictSeats

__all__ = ["LWG_2021"]

_FIVE_PERCENT = Fraction(5, 100)

# Sec. 35 (4) to (7): the seats allocated for a house of a given size.
_ALLOCATE_HOUSE = (
    SetSeatTotal(),  # Sec. 35 (4)
    ApportionSeats(  # Sec. 35 (5), (6)
        method=MajorityFirst(method=HareNiemeyer()), section="zweitstimme", level="land"
    ),
    DeductDistrictSeats(),  # Sec. 35 (7)
)

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
    protocol=(
        SumVotes(level="wahlkreis"),  # Sec. 31, 32
        ElectDistricts(section="erststimme", level="wahlkreis"),  # Sec. 33
        SumVotes(level="land"),  # Sec. 35 (2)
        ApplyThreshold(  # Sec. 35 (3)
            threshold=RelativeThreshold(share=_FIVE_PERCENT), section="zweitstimme", level="land"
        ),
        SetHouse(seats=83),  # Sec. 1 (1)
        *_ALLOCATE_HOUSE,
        RepeatForMehrsitze(  # Sec. 35 (8), (8a)
            protocol=_ALLOCATE_HOUSE,
            factor=2,
            full_rounds=2,
            fraktion=FraktionSize(share=_FIVE_PERCENT, section="zweitstimme", level="land"),
        ),
        FormChamber(minimum_mandates=83),  # Sec. 1 (1): at least 83
    ),
)
"""The LWG as it governed the Landtag elections of 2021 and 2026. The day it first
applied is not on record here, so ``in_force_from`` is open; it is not the 2016 law."""
