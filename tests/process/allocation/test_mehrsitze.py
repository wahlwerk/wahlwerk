"""The Mehrsitze loop of Sec. 35 (8), (8a) LWG LSA on constructed tallies: 2021 balances
within the full rounds, so the rounds after them are only reached here."""

from fractions import Fraction

from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.process.allocation.base import Allocation, check_protocol
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
from wahlwerk.vote.popular.tally import Level, Tally, TallyRow

LEVELS = (Level(name="land", depth=2), Level(name="wahlkreis", depth=4))
FIVE = Fraction(5, 100)
FRAKTION = FraktionSize(share=FIVE, section="zweitstimme", level="land")
ALLOCATE_HOUSE = (
    SetSeatTotal(),
    ApportionSeats(method=HareNiemeyer(), section="zweitstimme", level="land"),
    DeductDistrictSeats(),
)


def tally(winners, zweit):
    rows = []
    for number, winner in enumerate(winners, start=1):
        unit = f"de.st.wk.{number:03d}"
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", party=winner, count=100))
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", party="spd", count=1))
    for party, count in zweit.items():
        rows.append(
            TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", party=party, count=count)
        )
    return Tally(rows=tuple(rows), levels=LEVELS)


def law(base, repeat):
    return (
        SumVotes(level="wahlkreis"),
        ElectDistricts(section="erststimme", level="wahlkreis"),
        SumVotes(level="land"),
        ApplyThreshold(threshold=RelativeThreshold(share=FIVE), section="zweitstimme", level="land"),
        SetHouse(seats=base),
        *ALLOCATE_HOUSE,
        repeat,
        FormChamber(minimum_mandates=base),
    )


def run(protocol, winners, zweit):
    check_protocol(protocol)
    allocation = Allocation(tally=tally(winners, zweit))
    for step in protocol:
        allocation = step(allocation)
    return allocation


ZWEIT = {"afd": 500, "cdu": 300, "linke": 170, "fdp": 30}
LOOP = RepeatForMehrsitze(protocol=ALLOCATE_HOUSE, factor=2, full_rounds=2, fraktion=FRAKTION)


def test_balanced_within_the_full_rounds():
    # Hare on 10: Linke 1.75 -> 2 against 3 Wahlkreise: 1 Mehrsitz, house 12.
    # On 12 Linke gets 2 again (cdu takes the remainder seat): house 14; on 14 Linke gets 3.
    result = run(law(10, LOOP), ["linke"] * 3, ZWEIT)
    assert result.house == 14
    assert result.overhang == ()
    assert result.entitlement.as_dict() == {"afd": 7, "cdu": 4, "linke": 3}
    assert result.chamber.size == 14


def test_no_mehrsitze_leaves_the_house():
    result = run(law(10, LOOP), ["afd"], ZWEIT)
    assert result.house == 10
    assert result.chamber.size == 10


# A small party winning many Wahlkreise keeps Mehrsitze past two rounds.
MANY = ["linke"] * 5
SMALL = {"afd": 540, "cdu": 400, "linke": 60}


def test_without_a_fraktion_rule_mehrsitze_left_after_the_full_rounds_are_kept():
    loop = RepeatForMehrsitze(protocol=ALLOCATE_HOUSE, factor=2, full_rounds=2)
    result = run(law(10, loop), MANY, SMALL)
    kept = sum(n for _, n in result.overhang)
    assert kept > 0
    assert result.chamber.size == result.house + kept
    assert dict(result.list_seats)["linke"] == 0


def test_further_rounds_run_while_mehrsitze_exceed_half_a_fraktion():
    unlimited = run(law(10, RepeatForMehrsitze(protocol=ALLOCATE_HOUSE)), MANY, SMALL)
    limited = run(law(10, LOOP), MANY, SMALL)
    kept = sum(n for _, n in limited.overhang)
    assert 2 * kept <= FRAKTION.seats(limited)
    assert limited.house > unlimited.house
    assert limited.chamber.size == limited.house + kept


def test_fraktion_size_counts_a_fictitious_five_percent_party():
    # 5 % of 1000 = 50 fictitious votes beside 900 eligible: 20 * 50 / 950 = 1.05 -> 1.
    rows = tuple(
        TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", party=p, count=n)
        for p, n in {"a": 450, "b": 450, "c": 100}.items()
    )
    allocation = SumVotes(level="land")(Allocation(tally=Tally(rows=rows, levels=LEVELS)))
    allocation = allocation.with_values(eligible=frozenset({"a", "b"}), seat_total=20)
    assert FRAKTION.seats(allocation) == 1
    assert FRAKTION.seats(allocation.with_values(seat_total=97)) == 5  # 97 * 50 / 950 = 5.1


def test_loop_declares_what_it_reads_and_writes():
    assert {"house", "overhang", "districts", "eligible", "total:land"} <= LOOP.reads
    assert {"house", "seat_total", "entitlement", "list_seats", "overhang"} <= LOOP.writes
