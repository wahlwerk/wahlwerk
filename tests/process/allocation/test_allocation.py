import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.plurality import Plurality
from wahlwerk.apportionment.tie import Tie
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    UnitResult,
    check_protocol,
)
from wahlwerk.process.allocation.count import SumGroupBy
from wahlwerk.process.allocation.elect import SingleMandatePerUnit
from wahlwerk.vote.popular.hierarchy import Hierarchy, HierarchyUnit
from wahlwerk.vote.popular.tally import Level, Tally, TallyRow

LEVELS = (
    Level(name="land", depth=2),
    Level(name="wahlkreis", depth=4),
    Level(name="wahlbezirk", depth=8),
    Level(name="briefwahlbezirk", depth=8),
)
WK1_A = "de.st.wk.001.gem.15081026.wbz.000001"
WK1_B = "de.st.wk.001.gem.15081026.wbz.000026"  # a Briefwahlbezirk
WK2 = "de.st.wk.002.gem.15081030.wbz.000001"
WK3 = "de.st.wk.003.gem.15081045.wbz.000001"


def vote(unit, count, *, section="erststimme", party=None, candidate=None, level="wahlbezirk"):
    channel = "brief" if level == "briefwahlbezirk" else "urne"
    return TallyRow(
        unit=unit,
        level=level,
        section=section,
        channel=channel,
        option=candidate or party,
        count=count,
    )


TALLY = Tally.from_rows(
    parties={p: p for p in ("afd", "cdu", "linke", "spd", "fdp")},
    levels=LEVELS,
    rows=(
        # Wahlkreis 1: AfD wins only once the Briefwahl is added (40 + 25 against 50 + 10).
        vote(WK1_A, 40, party="afd"),
        vote(WK1_A, 50, party="cdu"),
        vote(WK1_B, 25, party="afd", level="briefwahlbezirk"),
        vote(WK1_B, 10, party="cdu", level="briefwahlbezirk"),
        # Wahlkreis 2: an Einzelbewerber wins.
        vote(WK2, 30, party="linke"),
        vote(WK2, 31, candidate="de.st.wk.002.einzelbewerber"),
        # Wahlkreis 3: a tie.
        vote(WK3, 20, party="spd"),
        vote(WK3, 20, party="cdu"),
        # Zweitstimmen are not counted for the Wahlkreis.
        vote(WK3, 99, section="zweitstimme", party="fdp"),
    ),
)
START = Allocation(tally=TALLY)
ELECT = SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis")


# ===========================================================
# Allocation and facts
# ===========================================================
def test_start_has_only_the_tally():
    assert START.facts == {"tally"}
    assert START.unit_mandates is None
    with pytest.raises(KeyError, match="no table 'erststimme by wahlkreis × option'"):
        START.count("erststimme", "wahlkreis")


def test_sum_group_by_makes_a_table_of_counts():
    summed = SumGroupBy(section="erststimme", level="wahlkreis", by="option")(START)
    assert summed.facts == {"tally", "erststimme by wahlkreis × option"}
    table = summed.count("erststimme", "wahlkreis")
    # A row per unit, a counter per option, Urne and Brief summed; nothing else in it.
    assert table.per_unit()["de.st.wk.001"] == {"afd": 65, "cdu": 60}
    assert table.party_of("afd") == "afd"
    assert table.party_of("de.st.wk.002.einzelbewerber") is None
    assert "fdp" not in table.per_column()  # a Zweitstimme, not counted here
    assert START.facts == {"tally"}  # the input is untouched


def test_making_a_table_again_replaces_it():
    step = SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    twice = step(step(START))
    assert [t.fact for t in twice.counts] == ["erststimme by wahlkreis × option"]


def test_allocation_rejects_a_table_held_twice():
    table = SumGroupBy(section="erststimme", level="wahlkreis", by="option")(START).counts[0]
    with pytest.raises(ValidationError, match="more than once"):
        Allocation(tally=TALLY, counts=(table, table))


# ===========================================================
# SingleMandatePerUnit
# ===========================================================
def unit_mandates():
    return {d.unit: d for d in ELECT(SumGroupBy(section="erststimme", level="wahlkreis", by="option")(START)).unit_mandates}


def test_winner_counts_both_channels():
    wk1 = unit_mandates()["de.st.wk.001"]
    assert (wk1.option, wk1.party, wk1.votes) == ("afd", "afd", 65)
    assert wk1.is_decided


def test_einzelbewerber_wins_without_party():
    wk2 = unit_mandates()["de.st.wk.002"]
    assert wk2.option == "de.st.wk.002.einzelbewerber"
    assert wk2.party is None


def test_tie_is_a_result():
    wk3 = unit_mandates()["de.st.wk.003"]
    assert wk3.option is None
    assert wk3.tie == Tie(candidates=frozenset({"spd", "cdu"}), seats=1)
    assert wk3.votes == 20
    assert not wk3.is_decided


def test_elect_needs_its_total():
    with pytest.raises(ValueError, match=r"reads \['erststimme by wahlkreis × option'\], which are not established"):
        ELECT(START)


def test_elect_without_votes_in_section():
    other = SingleMandatePerUnit(method=Plurality(), section="stimme", level="wahlkreis")
    with pytest.raises(ValueError, match="no 'stimme by wahlkreis × option' votes"):
        other(SumGroupBy(section="stimme", level="wahlkreis", by="option")(START))  # an empty table
    with pytest.raises(ValueError, match=r"reads \['stimme by wahlkreis × option'\]"):
        other(SumGroupBy(section="erststimme", level="wahlkreis", by="option")(START))  # no table at all


def test_unit_result_needs_winner_xor_tie():
    with pytest.raises(ValidationError, match="not both or neither"):
        UnitResult(unit="de.st.wk.001", votes=1)
    with pytest.raises(ValidationError, match="one seat"):
        UnitResult(
            unit="de.st.wk.001",
            votes=1,
            tie=Tie(candidates=frozenset({"a", "b", "c"}), seats=2),
        )


# ===========================================================
# Protocols
# ===========================================================
def test_check_protocol_returns_the_facts_at_the_end():
    protocol = (SumGroupBy(section="erststimme", level="wahlkreis", by="option"), ELECT)
    assert check_protocol(protocol) == {"tally", "erststimme by wahlkreis × option", "unit_mandates"}


def test_check_protocol_refuses_a_misordered_law():
    with pytest.raises(ValueError, match=r"step 1 .*SingleMandatePerUnit.* reads \['erststimme by wahlkreis × option'\]"):
        check_protocol((ELECT, SumGroupBy(section="erststimme", level="wahlkreis", by="option")))


def test_check_protocol_sees_the_wrong_level():
    with pytest.raises(ValueError, match="erststimme by wahlkreis × option"):
        check_protocol((SumGroupBy(section="zweitstimme", level="land", by="party"), ELECT))


def test_steps_are_data():
    assert SumGroupBy(section="erststimme", level="wahlkreis", by="option") == SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    assert hash(ELECT) == hash(SingleMandatePerUnit(method=Plurality(), section="erststimme", level="wahlkreis"))
    assert "SingleMandatePerUnit" in repr(ELECT)


def test_a_step_must_write_what_it_declares():
    class Forgetful(AllocationStep):
        @property
        def reads(self):
            return frozenset({"tally"})

        @property
        def writes(self):
            return frozenset({"unit_mandates"})

        def _apply(self, allocation):
            return allocation

    with pytest.raises(ValueError, match=r"did not establish \['unit_mandates'\]"):
        Forgetful()(START)


def test_each_unit_is_a_contest_the_method_decides():
    # The step only turns the tally into contests; the method alone picks the winner.
    allocation = SumGroupBy(section="erststimme", level="wahlkreis", by="option")(START)
    per_unit = allocation.count("erststimme", "wahlkreis").per_unit()
    assert per_unit and all(isinstance(v, int) for unit in per_unit.values() for v in unit.values())
    assert per_unit["de.st.wk.001"] == {"afd": 65, "cdu": 60}  # options and votes, nothing else
    elected = ELECT(allocation)
    for result in elected.unit_mandates or ():
        assert result.votes == max(per_unit[result.unit].values())


def test_grouped_by_party_a_column_is_a_party_and_votes_for_no_party_drop_out():
    by_party = SumGroupBy(section="erststimme", level="wahlkreis", by="party")(START)
    table = by_party.count("erststimme", "wahlkreis", "party")
    assert table.fact == "erststimme by wahlkreis × party"
    assert "de.st.wk.002.einzelbewerber" not in table.per_column()
    assert table.per_unit()["de.st.wk.001"] == {"afd": 65, "cdu": 60}
    assert table.party_of("cdu") == "cdu"


# ===========================================================
# Several sections counted as one (Art. 42 (2) BayLWG)
# ===========================================================
GESAMT = SumGroupBy(section="gesamtstimme", sections=("erststimme", "zweitstimme"), level="land", by="party")


def test_sections_are_counted_together_under_one_name():
    table = GESAMT(START).count("gesamtstimme", "land", "party")
    assert table.fact == "gesamtstimme by land × party"
    assert table.per_column() == {"afd": 65, "cdu": 80, "linke": 30, "spd": 20, "fdp": 99}


def test_sections_by_option_keep_the_einzelbewerber():
    step = SumGroupBy(section="gesamtstimme", sections=("erststimme", "zweitstimme"), level="wahlkreis", by="option")
    per_unit = step(START).count("gesamtstimme", "wahlkreis").per_unit()
    assert per_unit["de.st.wk.002"] == {"linke": 30, "de.st.wk.002.einzelbewerber": 31}
    assert per_unit["de.st.wk.003"] == {"spd": 20, "cdu": 20, "fdp": 99}


@pytest.mark.parametrize("sections", [("erststimme",), ("erststimme", "erststimme")])
def test_sections_must_be_several_and_distinct(sections):
    with pytest.raises(ValidationError, match="sections"):
        SumGroupBy(section="gesamtstimme", sections=sections, level="land", by="party")


def test_a_count_is_named_as_its_operations():
    plain = SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    assert plain.counted == ("erststimme",)
    assert [name for name, _ in plain.operations] == ["RollUp", "Select", "Collapse"]
    assert [name for name, _ in GESAMT.operations] == ["RollUp", "Select", "Relabel", "Collapse", "Relabel"]
    assert ("Relabel", "erststimme + zweitstimme -> gesamtstimme") in GESAMT.operations


# ===========================================================
# Counting along a hierarchy (schema 4)
# ===========================================================

WBZ = "de.st.gem.15081026.wbz.000001"
ELECTORAL = Hierarchy(
    name="electoral",
    levels=("land", "wahlkreis"),
    units=(
        HierarchyUnit(unit="de.st", level="land"),
        HierarchyUnit(unit="de.st.wk.007", level="wahlkreis", parent="de.st"),
        HierarchyUnit(unit=WBZ, level="wahlbezirk", parent="de.st.wk.007"),
    ),
)
FREE = Tally.from_rows((vote(WBZ, 4, party="cdu"), vote(WBZ, 3, party="spd")), parties={"cdu": "cdu", "spd": "spd"})


def test_a_count_follows_the_hierarchy_its_law_names():
    step = SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    table = step(Allocation(tally=FREE, hierarchies=(ELECTORAL,))).count("erststimme", "wahlkreis")
    assert table.per_unit() == {"de.st.wk.007": {"cdu": 4, "spd": 3}}
    # Another law's Wahlkreise are another hierarchy, not other data.
    redrawn = ELECTORAL.model_copy(update={"name": "electoral-2016"})
    other = SumGroupBy(section="erststimme", level="wahlkreis", by="option", hierarchy="electoral-2016")
    assert other(Allocation(tally=FREE, hierarchies=(redrawn,))).count("erststimme", "wahlkreis").per_unit() == table.per_unit()


def test_a_count_needs_its_hierarchy_or_ids_that_spell_it():
    step = SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    with pytest.raises(ValueError, match="records no hierarchy 'electoral'"):
        step(Allocation(tally=FREE))


def test_an_allocation_from_a_vote_carries_its_hierarchies():
    from wahlwerk.vote.popular.popular_vote import PopularVote, Source

    source = Source(publisher="p", title="t", url="https://example.org", licence="l", attribution="a",
                    retrieved="2026-10-26", sha256="a" * 64)
    vote = PopularVote(source=source, tally=FREE, hierarchies=(ELECTORAL,))
    assert Allocation.from_vote(vote).hierarchies == (ELECTORAL,)
    step = SumGroupBy(section="erststimme", level="wahlkreis", by="option")
    assert step(Allocation.from_vote(vote)).count("erststimme", "wahlkreis").per_unit() == {"de.st.wk.007": {"cdu": 4, "spd": 3}}
