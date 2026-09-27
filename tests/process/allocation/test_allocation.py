import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.tie import Tie
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    DistrictResult,
    check_protocol,
)
from wahlwerk.process.allocation.count import SumVotes
from wahlwerk.process.allocation.district import ElectDistricts
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
        party=party,
        candidate=candidate,
        count=count,
    )


TALLY = Tally(
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
ELECT = ElectDistricts(section="erststimme", level="wahlkreis")


# ===========================================================
# Allocation and facts
# ===========================================================
def test_start_has_only_the_tally():
    assert START.facts == {"tally"}
    assert START.districts is None
    with pytest.raises(KeyError, match="no total at level 'wahlkreis'"):
        START.total("wahlkreis")


def test_sum_votes_adds_a_total():
    summed = SumVotes(level="wahlkreis")(START)
    assert summed.facts == {"tally", "total:wahlkreis"}
    assert summed.total("wahlkreis").filter(party="afd").sum_by("unit") == {"de.st.wk.001": 65}
    assert START.facts == {"tally"}  # the input is untouched


def test_summing_a_level_again_replaces_it():
    twice = SumVotes(level="wahlkreis")(SumVotes(level="wahlkreis")(START))
    assert [level for level, _ in twice.totals] == ["wahlkreis"]


def test_allocation_rejects_a_level_summed_twice():
    total = TALLY.sum_to("land")
    with pytest.raises(ValidationError, match="more than once"):
        Allocation(tally=TALLY, totals=(("land", total), ("land", total)))


# ===========================================================
# ElectDistricts
# ===========================================================
def districts():
    return {d.unit: d for d in ELECT(SumVotes(level="wahlkreis")(START)).districts}


def test_winner_counts_both_channels():
    wk1 = districts()["de.st.wk.001"]
    assert (wk1.nominee, wk1.party, wk1.votes) == ("afd", "afd", 65)
    assert wk1.is_decided


def test_einzelbewerber_wins_without_party():
    wk2 = districts()["de.st.wk.002"]
    assert wk2.nominee == wk2.candidate == "de.st.wk.002.einzelbewerber"
    assert wk2.party is None


def test_tie_is_a_result():
    wk3 = districts()["de.st.wk.003"]
    assert wk3.nominee is None
    assert wk3.tie == Tie(candidates=frozenset({"spd", "cdu"}), seats=1)
    assert wk3.votes == 20
    assert not wk3.is_decided


def test_elect_needs_its_total():
    with pytest.raises(ValueError, match=r"reads \['total:wahlkreis'\], which are not established"):
        ELECT(START)


def test_elect_without_votes_in_section():
    other = ElectDistricts(section="stimme", level="wahlkreis")
    with pytest.raises(ValueError, match="no 'stimme' votes"):
        other(SumVotes(level="wahlkreis")(START))


def test_district_result_needs_winner_xor_tie():
    with pytest.raises(ValidationError, match="not both or neither"):
        DistrictResult(unit="de.st.wk.001", votes=1)
    with pytest.raises(ValidationError, match="one seat"):
        DistrictResult(
            unit="de.st.wk.001",
            votes=1,
            tie=Tie(candidates=frozenset({"a", "b", "c"}), seats=2),
        )


# ===========================================================
# Protocols
# ===========================================================
def test_check_protocol_returns_the_facts_at_the_end():
    protocol = (SumVotes(level="wahlkreis"), ELECT)
    assert check_protocol(protocol) == {"tally", "total:wahlkreis", "districts"}


def test_check_protocol_refuses_a_misordered_law():
    with pytest.raises(ValueError, match=r"step 1 .*ElectDistricts.* reads \['total:wahlkreis'\]"):
        check_protocol((ELECT, SumVotes(level="wahlkreis")))


def test_check_protocol_sees_the_wrong_level():
    with pytest.raises(ValueError, match="total:wahlkreis"):
        check_protocol((SumVotes(level="land"), ELECT))


def test_steps_are_data():
    assert SumVotes(level="wahlkreis") == SumVotes(level="wahlkreis")
    assert hash(ELECT) == hash(ElectDistricts(section="erststimme", level="wahlkreis"))
    assert "ElectDistricts" in repr(ELECT)


def test_a_step_must_write_what_it_declares():
    class Forgetful(AllocationStep):
        @property
        def reads(self):
            return frozenset({"tally"})

        @property
        def writes(self):
            return frozenset({"districts"})

        def _apply(self, allocation):
            return allocation

    with pytest.raises(ValueError, match=r"did not establish \['districts'\]"):
        Forgetful()(START)
