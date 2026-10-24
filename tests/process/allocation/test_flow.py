"""The structure of a protocol, derived from what its steps read and write; and
sequences, several steps used as one."""

import pytest

from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.de.mv.lkwg import LKWG_2011
from wahlwerk.law.de.st.lwg import ALLOCATE, LWG_2021
from wahlwerk.process.allocation import flow
from wahlwerk.process.allocation.allocate import derive
from wahlwerk.process.allocation.base import check_protocol
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.elect import ElectPerUnit
from wahlwerk.process.allocation.sequence import StepSequence

P = LWG_2021.protocol
GOLDEN = "tests/golden/de.landtag.st.2021"


def test_stages_follow_the_facts():
    # tally -> sums -> winners and threshold -> the allocation loop -> the chamber
    assert flow.stages(P) == (0, 1, 0, 1, 0, 2, 3)
    assert flow.stages(LKWG_2011.protocol) == (0, 1, 0, 1, 0, 2, 3)


def test_sources_name_the_last_writer():
    read = flow.sources(P)
    assert read[1] == {"total:wahlkreis": 0}
    assert read[5]["chamber_size"] == 4 and read[5]["districts"] == 1
    assert read[6] == {"districts": 1, "list_seats": 5, "minimum_mandates": 4}


def test_independent_steps_can_swap_and_dependent_ones_cannot():
    assert flow.can_swap(P, 1, 2)  # Wahlkreis winners and the Land sum need nothing of each other
    assert flow.can_swap(P, 3, 4)  # the threshold and the chamber size
    assert not flow.can_swap(P, 0, 1)  # the winners read the Wahlkreis sums
    assert not flow.can_swap(P, 4, 5)  # the loop reads the chamber size
    assert not flow.can_swap(P, 5, 6)


def test_a_swap_that_keeps_the_flow_keeps_the_result():
    vote = read_bundle(GOLDEN)
    swapped = (P[0], P[2], P[1], *P[3:])
    assert flow.can_swap(P, 1, 2)
    assert derive(vote, swapped).chamber == derive(vote, P).chamber


def test_two_writers_of_one_fact_cannot_trade_places():
    # Both write total:land; the later one is the one that counts.
    twice = (SumVotes(level="land"), SumVotes(level="land", citation="again"))
    assert not flow.can_swap(twice, 0, 1)


def test_movable_gives_the_range_a_step_can_go():
    assert list(flow.movable(P, 4)) == [0, 1, 2, 3, 4]  # the chamber size can come first
    assert list(flow.movable(P, 5)) == [5]
    assert list(flow.movable(P, 0)) == [0]


def test_a_sequence_is_one_step():
    assert ALLOCATE.reads == {"chamber_size", "districts", "eligible", "total:land"}
    assert ALLOCATE.writes == {"seat_total", "entitlement", "list_seats", "overhang"}
    inline = (*P[:5], ALLOCATE, P[6])
    flat = (*P[:5], *ALLOCATE.steps, P[6])
    vote = read_bundle(GOLDEN)
    assert derive(vote, inline).chamber == derive(vote, flat).chamber
    assert check_protocol(inline) == check_protocol(flat)


def test_a_sequence_needs_its_steps_and_a_title():
    with pytest.raises(ValueError):
        StepSequence(title="nothing", steps=())
    with pytest.raises(ValueError):
        StepSequence(title="", steps=(SumVotes(level="land"),))


def test_a_sequence_in_the_wrong_place_is_refused():
    with pytest.raises(ValueError, match="reads"):
        check_protocol((ALLOCATE, *P))


def test_describe_and_the_table():
    nodes = flow.describe(P)
    assert [n.kind for n in nodes] == [
        "SumVotes", "ElectPerUnit", "SumVotes", "ApplyThreshold",
        "SetChamberSize", "RepeatForMehrsitze", "FormChamber",
    ]
    loop = nodes[5]
    assert loop.citation == "Sec. 35 (8), (8a)"
    assert loop.depends_on == (1, 2, 3, 4)
    (sequence,) = loop.children
    assert sequence.title == "allocate the seats of one chamber size"
    assert [c.path for c in sequence.children] == [(5, "protocol", 0, "steps", i) for i in range(3)]
    assert nodes[4].parameters == (("seats", "83"),)  # defaults left out
    table = flow.protocol_table(P)
    assert "Sec. 35 (8), (8a)" in table and '"allocate the seats of one chamber size"' in table
    assert repr(LWG_2021).startswith("Law de.st.lwg.2021:")
    assert "<table" in LWG_2021._repr_html_()
    data = flow.protocol_data(P)
    assert data[5]["children"][0]["kind"] == "StepSequence"


def test_citations_are_data_and_survive_an_edit():
    assert [s.citation for s in P][:5] == ["Sec. 31, 32", "Sec. 33", "Sec. 35 (2)", "Sec. 35 (3)", "Sec. 1 (1)"]
    winners = ElectPerUnit(method=Plurality(), section="erststimme", level="wahlkreis")
    assert winners != P[1]  # the citation is part of the step


def test_fancy_html_draws_the_protocol():
    card = LWG_2021.fancy_html()
    assert "RepeatForMehrsitze (repeats)" in card
    assert "allocate the seats of one chamber size" in card
    assert "Sec. 35 (8), (8a)" in card


def test_a_step_leads_down_to_its_formula():
    elect = flow.describe(P)[1]
    assert [(u.field, u.kind, u.formula) for u in elect.uses] == [
        ("method", "Plurality", "wahlwerk.calc.plurality.plurality")
    ]
    apportion = flow.describe(P)[5].children[0].children[1]
    assert [u.formula for u in apportion.uses] == [
        "wahlwerk.calc.majority.majority_first",
        "wahlwerk.calc.remainder.largest_remainder",
    ]
    assert "-> Plurality: calc.plurality.plurality" in flow.protocol_table(P)


def test_the_formula_named_is_the_one_called(monkeypatch):
    # The link is the call: the method computes through the formula it names.
    from fractions import Fraction

    from wahlwerk.apportionment.plurality import Plurality
    from wahlwerk.calc import plurality as calc

    assert Plurality.formula is calc.plurality
    calls = []
    original = Plurality.formula
    monkeypatch.setattr(Plurality, "formula", staticmethod(lambda w, s: calls.append(dict(w)) or original(w, s)))
    Plurality().apportion({"a": 2, "b": 1}, 1)
    assert calls == [{"a": Fraction(2), "b": Fraction(1)}]
