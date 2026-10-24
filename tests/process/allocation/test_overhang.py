"""The Mehrsitze loop of Sec. 35 (8), (8a) LWG LSA on constructed tallies: 2021 balances
within the full rounds, so the rounds after them are only reached here. Then the
Ausgleich of Sec. 58 (6) LKWG M-V."""

from fractions import Fraction

from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.apportionment.quota import HareQuota
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.threshold import RelativeThreshold
from wahlwerk.process.allocation.base import Allocation, check_protocol
from wahlwerk.process.allocation.chamber import FillVacantSeatsFromLists
from wahlwerk.process.allocation.count import SumGroupBy
from wahlwerk.process.allocation.elect import SingleMandatePerUnit
from wahlwerk.process.allocation.eligibility import (
    ApplyThresholdToOptions,
    SetChamberSize,
    SetSeatTotal,
)
from wahlwerk.process.allocation.overhang import (
    RaiseByOverhang,
    RaiseChamberSize,
    RaiseUntilBalanced,
    SetCaucusSize,
)
from wahlwerk.process.allocation.seats import ApportionSeats, DeductUnitSeats
from wahlwerk.vote.popular.tally import Level, Tally, TallyRow

LEVELS = (Level(name="land", depth=2), Level(name="wahlkreis", depth=4))
FIVE = Fraction(5, 100)
CAUCUS = SetCaucusSize(share=FIVE, section="zweitstimme", level="land", quota=HareQuota())
ALLOCATE = (
    SetSeatTotal(section="zweitstimme"),
    ApportionSeats(method=HareNiemeyer(), section="zweitstimme", level="land"),
    DeductUnitSeats(),
)


def tally(winners, zweit):
    rows = []
    for number, winner in enumerate(winners, start=1):
        unit = f"de.st.wk.{number:03d}"
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", option=winner, party=winner, count=100))
        rows.append(TallyRow(unit=unit, level="wahlkreis", section="erststimme", option="spd", party="spd", count=1))
    for party, count in zweit.items():
        rows.append(
            TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", option=party, party=party, count=count)
        )
    return Tally(rows=tuple(rows), levels=LEVELS)


def law(base, repeat, *, is_measured=True):
    """A small law: count, decide, allocate once (and measure the caucus size), then the
    loop, which only runs while the allocation left overhang."""
    return (
        SumGroupBy(section="erststimme", level="wahlkreis"),
        SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis"),
        SumGroupBy(section="zweitstimme", level="land", by="party"),
        ApplyThresholdToOptions(threshold=RelativeThreshold(share=FIVE), section="zweitstimme", level="land"),
        SetChamberSize(seats=base),
        *ALLOCATE,
        *((CAUCUS,) if is_measured else ()),
        repeat,
        FillVacantSeatsFromLists(minimum_mandates=base),
    )


def run(protocol, winners, zweit):
    check_protocol(protocol)
    allocation = Allocation(tally=tally(winners, zweit))
    for step in protocol:
        allocation = step(allocation)
    return allocation


ZWEIT = {"afd": 500, "cdu": 300, "linke": 170, "fdp": 30}
TALLY_EMPTY = Tally(rows=(), levels=LEVELS)
LOOP = RaiseByOverhang(protocol=(RaiseChamberSize(factor=2), *ALLOCATE, CAUCUS), full_rounds=2)


def test_balanced_within_the_full_rounds():
    # Hare on 10: Linke 1.75 -> 2 against 3 Wahlkreise: 1 Mehrsitz, chamber size 12.
    # On 12 Linke gets 2 again (cdu takes the remainder seat): chamber size 14; on 14 Linke gets 3.
    result = run(law(10, LOOP), ["linke"] * 3, ZWEIT)
    assert result.chamber_size == 14
    assert result.overhang == ()
    assert result.entitlement.as_dict() == {"afd": 7, "cdu": 4, "linke": 3}
    assert result.chamber.size == 14


def test_no_mehrsitze_leaves_the_chamber_size():
    result = run(law(10, LOOP), ["afd"], ZWEIT)
    assert result.chamber_size == 10
    assert result.chamber.size == 10


# A small party winning many Wahlkreise keeps Mehrsitze past two rounds.
MANY = ["linke"] * 5
SMALL = {"afd": 540, "cdu": 400, "linke": 60}


def test_without_a_caucus_size_overhang_left_after_the_full_rounds_are_kept():
    loop = RaiseByOverhang(protocol=(RaiseChamberSize(factor=2), *ALLOCATE), full_rounds=2)
    result = run(law(10, loop, is_measured=False), MANY, SMALL)
    kept = sum(n for _, n in result.overhang)
    assert kept > 0
    assert result.chamber.size == result.chamber_size + kept
    assert dict(result.list_seats)["linke"] == 0


def test_further_rounds_run_while_overhang_exceeds_half_a_caucus():
    unlimited = run(law(10, RaiseByOverhang(protocol=(RaiseChamberSize(), *ALLOCATE)), is_measured=False), MANY, SMALL)
    limited = run(law(10, LOOP), MANY, SMALL)
    kept = sum(n for _, n in limited.overhang)
    assert 2 * kept <= limited.caucus_size  # measured in the last round
    assert limited.chamber_size > unlimited.chamber_size
    assert limited.chamber.size == limited.chamber_size + kept


def test_caucus_size_counts_a_fictitious_five_percent_party():
    # 5 % of 1000 = 50 fictitious votes beside 900 eligible: 20 * 50 / 950 = 1.05 -> 1.
    rows = tuple(
        TallyRow(unit="de.st.wk.001", level="wahlkreis", section="zweitstimme", option=p, party=p, count=n)
        for p, n in {"a": 450, "b": 450, "c": 100}.items()
    )
    allocation = SumGroupBy(section="zweitstimme", level="land", by="party")(Allocation(tally=Tally(rows=rows, levels=LEVELS)))
    allocation = allocation.with_values(eligible_parties=(("zweitstimme", frozenset({"a", "b"})),), seat_total=20)
    assert CAUCUS(allocation).caucus_size == 1
    assert CAUCUS(allocation.with_values(seat_total=97)).caucus_size == 5  # 97 * 50 / 950 = 5.1
    assert CAUCUS.reads == {"zweitstimme by land × party", "eligible parties of zweitstimme", "seat_total"}
    assert CAUCUS.writes == {"caucus_size"}


def test_loop_declares_what_it_reads_and_writes():
    # It checks the overhang the allocation before it left, before any round.
    assert {"chamber_size", "unit_mandates", "eligible parties of zweitstimme", "zweitstimme by land × party", "overhang"} <= LOOP.reads
    assert "caucus_size" in LOOP.optional_reads
    assert {"chamber_size", "seat_total", "entitlement", "list_seats", "overhang"} <= LOOP.writes


def test_no_overhang_no_round():
    before = run(law(10, LOOP)[:-2], ["afd"], ZWEIT)
    assert LOOP.rounds(before) == (before,)


def test_raise_chamber_size_by_twice_the_overhang():
    step = RaiseChamberSize(factor=2)
    allocation = Allocation(tally=TALLY_EMPTY).with_values(chamber_size=83, overhang=(("cdu", 6),))
    assert step(allocation).chamber_size == 95


# Sec. 58 (6) LKWG M-V: Ausgleich for Überhang, capped, and a raised chamber size made odd.
# The 2021 Landtag balances well within the cap, so the cap and a returning Überhang are
# only reached here. Hare on 10 seats among afd, cdu, linke gives linke 2 against its 3
# Wahlkreise: one seat of Überhang; linke first gets its third seat in a chamber size of 14.

LINKE = ["linke"] * 3


def raise_for_ausgleich(**fields):
    return RaiseUntilBalanced(protocol=ALLOCATE, **fields)


def test_without_a_limit_the_chamber_size_rises_until_the_ueberhang_is_balanced():
    result = run(law(10, raise_for_ausgleich()), LINKE, ZWEIT)
    assert result.chamber_size == 14
    assert result.overhang == ()
    assert result.entitlement.as_dict() == {"afd": 7, "cdu": 4, "linke": 3}
    assert result.chamber.size == 14


def test_the_limit_caps_the_ausgleichsmandate_and_keeps_the_ueberhang():
    # The chamber before Ausgleich is 10 + 1. Twice the Überhang allows a chamber of 13:
    # chamber size 12 with the Überhang kept; chamber size 13 would need 3 Ausgleichsmandate.
    result = run(law(10, raise_for_ausgleich(limit=2)), LINKE, ZWEIT)
    assert result.chamber_size == 12
    assert dict(result.overhang) == {"linke": 1}
    assert result.chamber.size == 13
    assert result.chamber.seats_by_party == {"afd": 6, "cdu": 4, "linke": 3}


def test_a_limit_of_zero_keeps_the_ueberhang_unbalanced():
    result = run(law(10, raise_for_ausgleich(limit=0)), LINKE, ZWEIT)
    assert result.chamber_size == 10
    assert result.chamber.size == 11


def test_an_even_raised_chamber_gains_one_seat():
    zweit = {"afd": 520, "cdu": 300, "linke": 180}
    even = run(law(11, raise_for_ausgleich()), LINKE, zweit)
    odd = run(law(11, raise_for_ausgleich(has_odd_size=True)), LINKE, zweit)
    assert even.chamber.size == 14
    assert odd.chamber_size == 15
    assert odd.overhang == ()
    assert odd.entitlement.as_dict() == {"afd": 8, "cdu": 4, "linke": 3}


def test_the_odd_seat_is_added_under_the_cap_too():
    # limit 1: chamber size 11, Überhang kept, chamber 12; the odd seat makes chamber size 12, chamber 13.
    result = run(law(10, raise_for_ausgleich(limit=1, has_odd_size=True)), LINKE, ZWEIT)
    assert result.chamber_size == 12
    assert result.chamber.size == 13


def test_an_ueberhang_brought_back_by_the_odd_seat_is_kept():
    # Balanced at 14; on 15 Hare gives linke 2 again, so its Überhang returns.
    result = run(law(10, raise_for_ausgleich(has_odd_size=True)), LINKE, ZWEIT)
    assert result.chamber_size == 15
    assert dict(result.overhang) == {"linke": 1}
    assert result.chamber.size == 16


def test_no_ueberhang_leaves_the_chamber_size_even_if_odd_is_required():
    result = run(law(10, raise_for_ausgleich(limit=2, has_odd_size=True)), ["afd"], ZWEIT)
    assert result.chamber_size == 10
    assert result.chamber.size == 10


def test_step_declares_what_it_reads_and_writes():
    step = raise_for_ausgleich(limit=2, has_odd_size=True)
    assert {"chamber_size", "unit_mandates", "eligible parties of zweitstimme", "zweitstimme by land × party"} <= step.reads
    assert "overhang" not in step.reads
    assert {"chamber_size", "seat_total", "entitlement", "list_seats", "overhang"} <= step.writes


def test_rounds_show_how_the_size_was_reached():
    before = run(law(10, LOOP)[:-2], ["linke"] * 3, ZWEIT)  # up to the loop, allocated once
    rounds = LOOP.rounds(before)
    assert [r.chamber_size for r in rounds] == [10, 12, 14]
    assert [sum(n for _, n in r.overhang) for r in rounds] == [1, 1, 0]
    assert rounds[-1] == LOOP(before)
