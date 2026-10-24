"""The structure of a protocol, derived from what its steps read and write; and
sequences, several steps used as one."""

import pytest

from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.de.mv.lkwg import LKWG_2011
from wahlwerk.law.de.st.lwg import ALLOCATE, COUNT, LWG_2021, QUALIFY
from wahlwerk.process.allocation import flow
from wahlwerk.process.allocation.allocate import derive
from wahlwerk.process.allocation.base import check_protocol
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.elect import SingleMandatePerUnit
from wahlwerk.process.allocation.sequence import StepSequence

P = LWG_2021.protocol
GOLDEN = "tests/golden/de.landtag.st.2021"


def test_stages_follow_the_facts():
    # chamber size and counting -> winners and threshold -> the allocation loop -> the chamber
    assert flow.stages(P) == (0, 0, 1, 2, 3)
    assert flow.stages(LKWG_2011.protocol) == (0, 0, 1, 2, 3)
    # the laws are written in stage order, each stage one step or one sequence
    assert list(flow.stages(P)) == sorted(flow.stages(P))


def test_sources_name_the_last_writer():
    read = flow.sources(P)
    assert read[1] == {"tally": None}
    assert read[2] == {"total:land": 1, "total:wahlkreis": 1}
    assert read[3]["chamber_size"] == 0 and read[3]["unit_mandates"] == 2
    assert read[4] == {"unit_mandates": 2, "list_seats": 3, "minimum_mandates": 0}


def test_independent_steps_can_swap_and_dependent_ones_cannot():
    assert flow.can_swap(P, 0, 1)  # the chamber size and the counting need nothing of each other
    assert flow.can_swap(COUNT.steps, 0, 1)  # the two sums
    assert flow.can_swap(QUALIFY.steps, 0, 1)  # the Wahlkreis winners and the threshold
    assert not flow.can_swap(P, 1, 2)  # the winners read the Wahlkreis sums
    assert not flow.can_swap(P, 2, 3)  # the loop reads who takes part
    assert not flow.can_swap(P, 3, 4)


def test_a_swap_that_keeps_the_flow_keeps_the_result():
    vote = read_bundle(GOLDEN)
    swapped = (P[1], P[0], *P[2:])
    assert flow.can_swap(P, 0, 1)
    assert derive(vote, swapped).chamber == derive(vote, P).chamber


def test_two_writers_of_one_fact_cannot_trade_places():
    # Both write total:land; the later one is the one that counts.
    twice = (SumVotes(level="land"), SumVotes(level="land", citation="again"))
    assert not flow.can_swap(twice, 0, 1)


def test_movable_gives_the_range_a_step_can_go():
    assert list(flow.movable(P, 0)) == [0, 1, 2]  # the chamber size: any time before the loop
    assert list(flow.movable(P, 1)) == [0, 1]
    assert list(flow.movable(P, 3)) == [3]


def test_a_sequence_is_one_step():
    assert ALLOCATE.reads == {"chamber_size", "unit_mandates", "eligible", "total:land"}
    assert ALLOCATE.writes == {"seat_total", "entitlement", "list_seats", "overhang"}
    inline = (*P[:3], ALLOCATE, P[4])
    flat = (*P[:3], *ALLOCATE.steps, P[4])
    vote = read_bundle(GOLDEN)
    assert derive(vote, inline).chamber == derive(vote, flat).chamber
    assert check_protocol(inline) == check_protocol(flat)


def test_a_sequence_needs_its_steps_and_a_title():
    with pytest.raises(ValueError):
        StepSequence(name="DoNothing", steps=())
    with pytest.raises(ValueError):
        StepSequence(name="count the votes", steps=(SumVotes(level="land"),))  # named like a step


def test_a_sequence_in_the_wrong_place_is_refused():
    with pytest.raises(ValueError, match="reads"):
        check_protocol((ALLOCATE, *P))


def test_describe_and_the_table():
    nodes = flow.describe(P)
    assert [n.kind for n in nodes] == [
        "SetChamberSize", "CountVotes", "ElectAndQualify", "RaiseByOverhang", "FormChamber",
    ]
    assert [c.kind for c in nodes[1].children] == ["SumVotes", "SumVotes"]
    assert [c.kind for c in nodes[2].children] == ["SingleMandatePerUnit", "ApplyThreshold"]
    loop = nodes[3]
    assert loop.citation == "Sec. 35 (8), (8a)"
    assert loop.depends_on == (0, 1, 2)
    sequence, caucus = loop.children
    assert caucus.kind == "SetCaucusSize" and caucus.writes == ("caucus_size",)
    assert sequence.kind == "AllocateSeats"
    assert [c.path for c in sequence.children] == [(3, "protocol", 0, "steps", i) for i in range(3)]
    assert nodes[0].parameters == (("seats", "83"),)  # defaults left out
    table = flow.protocol_table(P)
    assert "Sec. 35 (8), (8a)" in table and "AllocateSeats" in table
    assert repr(LWG_2021).startswith("Law de.st.lwg.2021:")
    assert "<table" in LWG_2021._repr_html_()
    data = flow.protocol_data(P)
    assert data[3]["children"][0]["kind"] == "AllocateSeats"


def test_citations_are_data_and_survive_an_edit():
    assert [s.citation for s in P] == ["Sec. 1 (1)", "Sec. 31, 32, 35 (2)", "Sec. 33, 35 (3)", "Sec. 35 (8), (8a)", None]
    assert [s.citation for s in QUALIFY.steps] == ["Sec. 33", "Sec. 35 (3)"]
    winners = SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis")
    assert winners != QUALIFY.steps[0]  # the citation is part of the step


def test_fancy_html_draws_the_protocol():
    card = LWG_2021.fancy_html()
    assert "RaiseByOverhang (repeats)" in card
    assert "AllocateSeats" in card
    assert "Sec. 35 (8), (8a)" in card


def test_a_step_leads_down_to_its_formula():
    elect = flow.describe(P)[2].children[0]
    assert [(u.field, u.kind) for u in elect.uses] == [("method", "Plurality")]
    (call,) = elect.uses[0].calls
    assert call.formula == "wahlwerk.calc.plurality.plurality"
    assert call.call == "plurality(votes, seats=1)"  # the concept, here for one seat
    apportion = flow.describe(P)[3].children[0].children[1]
    assert [(u.field, [c.formula for c in u.calls]) for u in apportion.uses] == [
        ("method", ["wahlwerk.calc.majority.majority_first"]),
        ("method.method", ["wahlwerk.calc.remainder.largest_remainder", "wahlwerk.calc.quota.hare"]),
    ]
    threshold = flow.describe(P)[2].children[1].uses[0]
    assert threshold.parameters == (("share", "1/20"),)
    deduct = flow.describe(P)[3].children[0].children[2]
    assert [c.formula for c in deduct.calls] == [
        "wahlwerk.calc.compensation.remaining",
        "wahlwerk.calc.compensation.overhang",
    ]
    table = flow.protocol_table(P)
    assert "-> Plurality" in table and "= calc.plurality.plurality" in table


def test_the_formula_named_is_the_one_called(monkeypatch):
    # The link is the call: the method computes through the formulas it names.
    from fractions import Fraction

    from wahlwerk.apportionment.plurality import Plurality
    from wahlwerk.calc import plurality as calc

    assert Plurality.formulas == (calc.plurality,)
    calls = []
    (original,) = Plurality.formulas
    monkeypatch.setattr(Plurality, "formulas", (lambda w, s: calls.append(dict(w)) or original(w, s),))
    Plurality().apportion({"a": 2, "b": 1}, 1)
    assert calls == [{"a": Fraction(2), "b": Fraction(1)}]


def test_a_concept_shows_what_the_step_hands_it():
    elect = flow.describe(P)[2].children[0]
    assert elect.uses[0].arguments == (("votes", "erststimme per nominee"), ("seats", "1"))
    threshold = flow.describe(P)[2].children[1].uses[0]
    assert threshold.arguments == (("votes", "zweitstimme per party"),)
    assert threshold.parameters == (("share", "1/20"),)
    caucus = flow.describe(P)[3].children[1]  # a step of its own, in the repeated block
    (quota,) = caucus.uses
    assert quota.kind == "HareQuota" and dict(quota.arguments)["seats"] == "seat_total"
    assert [c.formula for c in quota.calls] == ["wahlwerk.calc.quota.hare"]
    assert [c.formula for c in caucus.calls] == ["wahlwerk.calc.quota.whole_seats"]
