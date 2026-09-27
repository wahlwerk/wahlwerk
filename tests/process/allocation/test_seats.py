"""The eligibility and seat steps, on small constructed tallies that reach the branches
Sachsen-Anhalt 2026 does not: Wahlkreise won outside the allocation, overhang, ties."""

from datetime import date
from fractions import Fraction

import pytest

from wahlwerk.apportionment.divisor import DHondt
from wahlwerk.apportionment.majority import MajorityFirst
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import (
    AlternativeThresholds,
    RelativeThreshold,
    SeatThreshold,
)
from wahlwerk.process.allocation.allocate import allocate
from wahlwerk.process.allocation.base import Allocation, check_protocol
from wahlwerk.process.allocation.chamber import FormChamber
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.district import ElectDistricts
from wahlwerk.process.allocation.eligibility import (
    ApplyThreshold,
    SetHouse,
    SetSeatTotal,
)
from wahlwerk.process.allocation.seats import ApportionSeats, DeductDistrictSeats
from wahlwerk.state.mandate_origin import MandateSource
from wahlwerk.state.term import Term
from wahlwerk.vote.popular.popular_vote import PopularVote, Source
from wahlwerk.vote.popular.tally import Level, Tally, TallyRow

LEVELS = (Level(name="land", depth=2), Level(name="wahlkreis", depth=4))
ZWEIT = {"afd": 500, "cdu": 300, "linke": 170, "fdp": 30}  # fdp: 3 %
FIVE_PERCENT = RelativeThreshold(share=Fraction(5, 100))
HARE = HareNiemeyer()
SOURCE = Source(
    publisher="p",
    title="t",
    url="https://example.org/x",
    licence="l",
    attribution="a",
    retrieved=date(2026, 9, 27),
    sha256="a" * 64,
)


def tally(winners, zweit=ZWEIT):
    """One row of Erststimmen per Wahlkreis winner (a party, or a candidate id for an
    Einzelbewerber), against a runner-up; Zweitstimmen spread over the first Wahlkreis."""
    rows = []
    for number, winner in enumerate(winners, start=1):
        unit = f"de.st.wk.{number:03d}"
        nominee = {"candidate": winner} if "." in winner else {"party": winner}
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", count=100, **nominee))
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", party="spd", count=1))
    for party, count in zweit.items():
        rows.append(
            TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", party=party, count=count)
        )
    return Tally(rows=tuple(rows), levels=LEVELS)


def law(base, threshold=FIVE_PERCENT, method=HARE):
    return (
        SumVotes(level="wahlkreis"),
        ElectDistricts(section="erststimme", level="wahlkreis"),
        SumVotes(level="land"),
        ApplyThreshold(threshold=threshold, section="zweitstimme", level="land"),
        SetHouse(seats=base),
        SetSeatTotal(),
        ApportionSeats(method=method, section="zweitstimme", level="land"),
        DeductDistrictSeats(),
    )


def run(protocol, allocation):
    check_protocol(protocol)
    for step in protocol:
        allocation = step(allocation)
    return allocation


def test_seats_won_outside_the_allocation_leave_the_total():
    # Wahlkreis 2 to an Einzelbewerber, 3 to the FDP under 5 %: 10 - 2 = 8 seats.
    # Hare on 8 among 970: afd 4.12, cdu 2.47, linke 1.40 -> 4, 3, 1.
    result = run(law(10), Allocation(tally=tally(["afd", "de.st.wk.002.eb", "fdp"])))
    assert result.eligible == {"afd", "cdu", "linke"}
    assert result.seat_total == 8
    assert result.entitlement.as_dict() == {"afd": 4, "cdu": 3, "linke": 1}
    assert dict(result.list_seats) == {"afd": 3, "cdu": 3, "linke": 1}
    assert result.overhang == ()


def test_overhang_when_a_party_wins_more_wahlkreise_than_it_is_entitled_to():
    # Hare on 10: afd 5.15, cdu 3.09, linke 1.75 -> 5, 3, 2; Linke won 3 Wahlkreise.
    result = run(law(10), Allocation(tally=tally(["linke", "linke", "linke"])))
    assert result.entitlement.as_dict() == {"afd": 5, "cdu": 3, "linke": 2}
    assert dict(result.list_seats) == {"afd": 5, "cdu": 3, "linke": 0}
    assert dict(result.overhang) == {"linke": 1}


def test_grundmandatsklausel_reads_the_wahlkreise():
    rule = AlternativeThresholds(thresholds=(FIVE_PERCENT, SeatThreshold(seats=3)))
    step = ApplyThreshold(threshold=rule, section="zweitstimme", level="land")
    assert "districts" in step.reads
    result = run(law(20, threshold=rule), Allocation(tally=tally(["fdp", "fdp", "fdp"])))
    assert "fdp" in result.eligible
    assert result.seat_total == 20


def test_a_grundmandatsklausel_before_the_wahlkreise_is_refused():
    rule = AlternativeThresholds(thresholds=(FIVE_PERCENT, SeatThreshold(seats=3)))
    misordered = (
        SumVotes(level="land"),
        ApplyThreshold(threshold=rule, section="zweitstimme", level="land"),
    )
    with pytest.raises(ValueError, match=r"reads \['districts'\]"):
        check_protocol(misordered)


def test_majority_clause_in_the_allocation():
    # afd 510 of 1000, 10 seats: Hare gives 5, the clause a sixth (Sec. 35 (6)).
    zweit = {"afd": 510, "cdu": 250, "linke": 240}
    plain = run(law(10), Allocation(tally=tally(["afd"], zweit)))
    clause = run(law(10, method=MajorityFirst(method=HareNiemeyer())), Allocation(tally=tally(["afd"], zweit)))
    assert plain.entitlement["afd"] == 5
    assert clause.entitlement.as_dict() == {"afd": 6, "cdu": 2, "linke": 2}


def test_counterfactual_is_one_field():
    # 8 seats on 100, 80, 30, 20: Hare 3, 3, 1, 1; D'Hondt 4, 3, 1, 0.
    zweit = {"afd": 100, "cdu": 80, "linke": 30, "gruene": 20}
    hare = run(law(8), Allocation(tally=tally(["afd"], zweit)))
    dhondt = run(law(8, method=DHondt()), Allocation(tally=tally(["afd"], zweit)))
    assert hare.entitlement.as_dict() == {"afd": 3, "cdu": 3, "linke": 1, "gruene": 1}
    assert dhondt.entitlement.as_dict() == {"afd": 4, "cdu": 3, "linke": 1, "gruene": 0}


def test_a_tied_wahlkreis_stops_the_seat_total():
    rows = [
        TallyRow(unit="de.st.wk.001", level="wahlkreis", section="erststimme", party=party, count=5)
        for party in ("afd", "cdu")
    ] + [
        TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", party=p, count=n)
        for p, n in ZWEIT.items()
    ]
    tied = Allocation(tally=Tally(rows=tuple(rows), levels=LEVELS))
    with pytest.raises(ValueError, match=r"\['de.st.wk.001'\] are tied"):
        run(law(10), tied)


def test_a_tied_entitlement_stops_the_deduction():
    zweit = {"afd": 1, "cdu": 1, "linke": 1}
    with pytest.raises(ValueError, match="entitlement has a tie"):
        run(law(2, threshold=FIVE_PERCENT), Allocation(tally=tally(["de.st.wk.001.eb"], zweit)))


def test_seat_total_cannot_go_below_zero():
    with pytest.raises(ValueError, match="more than the 1 seats"):
        run(law(1), Allocation(tally=tally(["fdp", "de.st.wk.002.eb"])))


# ===========================================================
# FormChamber and allocate
# ===========================================================
def test_form_chamber_names_seats_by_how_they_were_won():
    protocol = (*law(10), FormChamber(minimum_mandates=10))
    result = run(protocol, Allocation(tally=tally(["afd", "de.st.wk.002.eb", "fdp"])))
    chamber = result.chamber
    ids = [m.id for m in chamber.mandates]
    assert ids[:3] == ["wk.001", "wk.002", "wk.003"]
    assert ids[3:6] == ["list.afd.001", "list.afd.002", "list.afd.003"]
    assert chamber.mandates[1].party is None  # the Einzelbewerber
    assert chamber.mandates[2].party == "fdp"  # won its Wahlkreis under 5 %
    assert all(m.origin.source is MandateSource.ELECTION for m in chamber.mandates)
    assert chamber.size == 10
    assert chamber.seats_by_party == {"afd": 4, "fdp": 1, "cdu": 3, "linke": 1, None: 1}


def test_overhang_seats_stay_in_the_chamber():
    protocol = (*law(10), FormChamber(minimum_mandates=10))
    chamber = run(protocol, Allocation(tally=tally(["linke", "linke", "linke"]))).chamber
    assert chamber.size == 11  # 10 + Linke's one Mehrsitz, not yet balanced
    assert chamber.is_above_minimum


def test_allocate_needs_a_chamber_forming_step():
    vote = PopularVote(source=SOURCE, tally=tally(["afd"]))
    with pytest.raises(ValueError, match="forms no chamber"):
        allocate(vote, law(10))


def test_allocate_sets_the_term():
    vote = PopularVote(source=SOURCE, tally=tally(["afd"]))
    term = Term(body="de.st.landtag")
    chamber = allocate(vote, (*law(10), FormChamber()), term=term)
    assert chamber.body == "de.st.landtag"
    assert chamber.minimum_mandates is None
    assert allocate(vote, (*law(10), FormChamber())).term is None
