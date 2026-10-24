"""One law, changed one piece at a time, on the votes of one real election.

The Landtag of Sachsen-Anhalt 2021 under the LWG LSA as enacted, then with another
apportionment method, another threshold, without the Mehrsitze loop, and with steps
reordered: a reorder that keeps every fact's writer gives the same chamber, and one
that does not is refused before anything is counted.

Runs offline on the golden fixture:

    uv run python examples/swap_lwg_lsa_2021.py
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from wahlwerk.apportionment.divisor import DHondt, SainteLague
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.de.st.lwg import ALLOCATE, LWG_2021, QUALIFY
from wahlwerk.law.edit import find, replace
from wahlwerk.process.allocation.allocate import derive
from wahlwerk.process.allocation.base import AllocationProtocol, check_protocol
from wahlwerk.process.allocation.eligibility import ApplyThreshold
from wahlwerk.process.allocation.flow import can_swap
from wahlwerk.process.allocation.mehrsitze import RepeatForMehrsitze
from wahlwerk.process.allocation.seats import ApportionSeats

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden" / "de.landtag.st.2021"
PARTIES = ("cdu", "afd", "linke", "spd", "fdp", "gruene", "fw")


def row(name: str, protocol: AllocationProtocol) -> str:
    try:
        check_protocol(protocol)
    except ValueError as error:
        return f"{name:46} refused: {str(error).split(', which')[0]}"
    chamber = derive(VOTE, protocol).chamber
    assert chamber is not None
    seats = chamber.seats_by_party
    return f"{name:46} {chamber.size:4} " + " ".join(f"{seats.get(p, 0):4}" for p in PARTIES)


VOTE = read_bundle(GOLDEN)
P = LWG_2021.protocol
LOOP = find(P, RepeatForMehrsitze)[0][0]
QUAL = P.index(QUALIFY)

if __name__ == "__main__":
    print(f"{'':46} size " + " ".join(f"{p:>4}" for p in PARTIES))
    print(row("LWG LSA 2021 as enacted", P))
    print(row("method: Sainte-Lague", replace(P, ApportionSeats, method=SainteLague())))
    print(row("method: D'Hondt", replace(P, ApportionSeats, method=DHondt())))
    print(row("method: Hare/Niemeyer, no majority clause", replace(P, ApportionSeats, method=HareNiemeyer())))
    print(row("threshold 3 %", replace(P, ApplyThreshold, threshold=RelativeThreshold(share=Fraction(3, 100)))))
    # The loop holds the allocation, so dropping it means putting the sequence in its place.
    print(row("no Mehrsitze balancing", (*P[:LOOP], ALLOCATE, *P[LOOP + 1 :])))
    # Reorders: the chamber size and the counting need nothing of each other, nor do the
    # Wahlkreis winners and the threshold; what the counts decide needs the counts.
    print(f"can swap steps 1 and 2: {can_swap(P, 0, 1)}")
    print(row("order: count before setting the chamber size", (P[1], P[0], *P[2:])))
    swapped = QUALIFY.model_copy(update={"steps": QUALIFY.steps[::-1]})
    print(row("order: threshold before Wahlkreis winners", (*P[:QUAL], swapped, *P[QUAL + 1 :])))
    print(f"can swap steps 2 and 3: {can_swap(P, 1, 2)}")
    print(row("order: decide before counting", (P[0], P[2], P[1], *P[3:])))
