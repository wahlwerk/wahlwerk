"""The synthetic bundles beside this file read cleanly, add up, and have the property
each scenario is made for (see ``README.md``), so a regenerated bundle cannot quietly
lose it.
"""

from fractions import Fraction
from pathlib import Path

import pytest

from wahlwerk.io.bundle import read_bundle
from wahlwerk.law.registry import LAWS
from wahlwerk.process.allocation.allocate import derive
from wahlwerk.vote.popular.popular_vote import PopularVote
from wahlwerk.vote.popular.tally import Tally

HERE = Path(__file__).parent
BUNDLES = sorted(path.name for path in HERE.iterdir() if (path / "tally.csv").is_file())
LANDTAG = [name for name in BUNDLES if name.startswith("landtag-")]
MINIMUM_SEATS = {"de.st.lwg.2021": 83, "de.mv.lkwg.2011": 71}
"""The Landtag laws the Landtag mocks run under, with the least seats each forms."""


def read(name: str) -> PopularVote:
    return read_bundle(HERE / name)


def votes(tally: Tally, section: str = "type1") -> dict[str, int]:
    """Valid votes per party (or option, or independent candidate) across all units."""
    rows = tally.filter(kind="votes", section=section).rows
    totals: dict[str, int] = {}
    for row in rows:
        key = row.party or row.option or row.candidate
        assert key is not None
        totals[key] = totals.get(key, 0) + row.count
    return totals


def mandate_winners_of(tally: Tally, section: str = "type1") -> dict[str, str]:
    """The recipient with the most votes per unit, over all channels."""
    per = tally.filter(kind="votes", section=section)
    totals: dict[tuple[str, str], int] = {}
    for row in per.rows:
        key = (row.unit, row.party or row.option or row.candidate or "")
        totals[key] = totals.get(key, 0) + row.count
    best: dict[str, tuple[int, str]] = {}
    for (unit, who), count in totals.items():
        if unit not in best or count > best[unit][0]:
            best[unit] = (count, who)
    return {unit: who for unit, (_, who) in best.items()}


def test_all_bundles_are_present():
    assert len(BUNDLES) == 27
    assert len(LANDTAG) == 9


@pytest.mark.parametrize("name", BUNDLES)
def test_bundle_adds_up(name):
    """Per unit, channel and section, valid and invalid votes equal the voters; per
    unit (Wahlkreis), the voters, Brief included, are at most the eligible."""
    tally = read(name).tally
    sections = {row.section for row in tally.filter(kind="votes").rows}
    for (unit, channel), voters in tally.filter(kind="voters").sum_by("unit", "channel").items():
        for section in sections:
            cast = tally.filter(unit=unit, section=section, channel=channel).total()
            assert cast == voters, (unit, section, channel)
    summed = tally.sum_to(tally.levels[1].name)
    eligible = summed.filter(kind="eligible").sum_by("unit")
    for unit, voters in summed.filter(kind="voters").sum_by("unit").items():
        assert voters <= eligible[unit], unit


def test_two_party_inverted_popular_loser_wins_most_units():
    tally = read("two-party-inverted").tally
    total = votes(tally)
    wins = list(mandate_winners_of(tally).values())
    assert total["party-a"] > total["party-b"]
    assert wins.count("party-b") > wins.count("party-a")


def test_electoral_college_popular_winner_wins_few_units():
    tally = read("electoral-college").tally
    total = votes(tally)
    wins = list(mandate_winners_of(tally).values())
    assert total["party-a"] > total["party-b"]
    assert wins.count("party-a") == 3


def test_fptp_regional_party_wins_seats_with_few_votes():
    tally = read("fptp-regional").tally
    total = votes(tally)
    share = Fraction(total["party-d"], sum(total.values()))
    assert share < Fraction(5, 100)
    assert list(mandate_winners_of(tally).values()).count("party-d") >= 2


def test_mixed_member_unit_strength_exceeds_list_share():
    tally = read("mixed-member").tally
    one, two = votes(tally, "type1"), votes(tally, "type2")
    wins = list(mandate_winners_of(tally, "type1").values())
    assert Fraction(two["party-a"], sum(two.values())) < Fraction(30, 100)
    assert wins.count("party-a") > len(wins) // 2
    assert one["party-a"] > two["party-a"]


def test_basic_mandate_party_below_five_percent_wins_three_units():
    tally = read("basic-mandate").tally
    two = votes(tally, "type2")
    assert Fraction(two["party-g"], sum(two.values())) < Fraction(5, 100)
    assert list(mandate_winners_of(tally, "type1").values()).count("party-g") == 3


def test_threshold_edge_shares_are_exact():
    total = votes(read("threshold-edge").tally)
    valid = sum(total.values())
    assert valid == 100_000
    assert Fraction(total["party-e"], valid) == Fraction(501, 10_000)
    assert Fraction(total["party-f"], valid) == Fraction(5, 100)
    assert Fraction(total["party-g"], valid) == Fraction(499, 10_000)
    assert Fraction(total["party-h"], valid) == Fraction(3, 100)


def test_fragmented_has_many_tiny_parties():
    total = votes(read("fragmented").tally)
    valid = sum(total.values())
    assert len(total) == 25
    assert max(total.values()) < valid * Fraction(15, 100)
    assert sum(1 for count in total.values() if count < valid / 100) >= 7


def test_dominant_party_has_a_bare_majority():
    total = votes(read("dominant").tally)
    assert Fraction(total["party-a"], sum(total.values())) == Fraction(502, 1000)


@pytest.mark.parametrize(("name", "low", "high"), [
    ("low-turnout", Fraction(10, 100), Fraction(25, 100)),
    ("high-turnout", Fraction(88, 100), Fraction(97, 100)),
])
def test_turnout(name, low, high):
    tally = read(name).tally
    turnout = Fraction(tally.filter(kind="voters").total(), tally.filter(kind="eligible").total())
    assert low < turnout < high


def test_referendum_majority_misses_a_quarter_of_the_eligible():
    tally = read("referendum").tally
    total = votes(tally)
    assert total["option1"] > total["option2"]
    assert total["option1"] * 4 < tally.filter(kind="eligible").total()


def test_independent_wins_one_unit():
    winners = mandate_winners_of(read("independent-winner").tally)
    assert winners["mock.independent-winner.unit04"].endswith(".indep1")
    assert not winners["mock.independent-winner.unit09"].endswith(".indep1")


def test_two_round_second_holds_only_undecided_units():
    first = read("two-round-first").tally
    second = read("two-round-second").tally
    first_units = {row.unit.split(".")[-1] for row in first.rows}
    second_units = {row.unit.split(".")[-1] for row in second.rows}
    assert second_units < first_units
    assert "unit02" not in second_units
    assert "unit05" in second_units
    parties_in_08 = second.filter(unit="mock.two-round-second.unit08", kind="votes")
    assert len({row.party for row in parties_in_08.rows}) == 3


def test_pathological_edge_cases():
    tally = read("pathological").tally
    total = votes(tally)
    assert total == {"party-a": 6_000, "party-b": 6_000, "party-c": 3_000, "party-d": 0}
    unit01 = tally.filter(unit="mock.pathological.unit01", kind="votes").sum_by("party")
    assert unit01["party-a"] == unit01["party-b"]


# Landtag mocks: Erst- and Zweitstimme, Urne and Brief, run under the real Landtag laws.


def wahlkreis_winners(tally: Tally) -> dict[str, str]:
    return mandate_winners_of(tally.sum_to("wahlkreis"), "erststimme")


def zweitstimmen(tally: Tally) -> dict[str, Fraction]:
    total = votes(tally, "zweitstimme")
    valid = sum(total.values())
    return {party: Fraction(count, valid) for party, count in total.items()}


@pytest.mark.parametrize("law_id", sorted(MINIMUM_SEATS))
@pytest.mark.parametrize("name", LANDTAG)
def test_landtag_laws_allocate(name, law_id):
    law = LAWS[law_id]
    allocation = derive(read(name), law.protocol)
    chamber = allocation.chamber
    assert chamber.size >= MINIMUM_SEATS[law_id]
    assert sum(allocation.unit_wins().values()) + chamber.seats_by_party.get(None, 0) == 40


def test_landtag_has_briefwahlbezirke():
    tally = read("landtag-typical").tally
    brief = tally.filter(kind="voters", channel="brief")
    assert {row.level for row in brief.rows} == {"briefwahlbezirk"}
    assert not tally.filter(kind="eligible", level="briefwahlbezirk").rows


def test_landtag_overhang_one_party_wins_nearly_every_wahlkreis():
    tally = read("landtag-overhang").tally
    wins = list(wahlkreis_winners(tally).values())
    assert wins.count("party-a") >= 38
    assert zweitstimmen(tally)["party-a"] < Fraction(35, 100)


def test_landtag_split_wins_two_parties_share_the_wahlkreise():
    wins = list(wahlkreis_winners(read("landtag-split-wins").tally).values())
    assert wins.count("party-a") >= 15
    assert wins.count("party-b") >= 15


def test_landtag_threshold_edge_is_exact():
    share = zweitstimmen(read("landtag-threshold-edge").tally)
    assert share["party-e"] == Fraction(501, 10_000)
    assert share["party-f"] == Fraction(5, 100)
    assert share["party-g"] == Fraction(499, 10_000)


def test_landtag_bare_majority_of_counted_votes():
    share = zweitstimmen(read("landtag-bare-majority").tally)
    counted = sum(value for value in share.values() if value >= Fraction(5, 100))
    assert share["party-a"] == Fraction(462, 1000)
    assert share["party-a"] / counted > Fraction(1, 2)
    assert share["party-a"] / counted < Fraction(501, 1000) + Fraction(1, 10_000)


def test_landtag_grundmandat_party_below_threshold_wins_three():
    tally = read("landtag-grundmandat").tally
    assert zweitstimmen(tally)["party-g"] < Fraction(5, 100)
    assert list(wahlkreis_winners(tally).values()).count("party-g") == 3


def test_landtag_einzelbewerber_wins_one_wahlkreis():
    winners = wahlkreis_winners(read("landtag-einzelbewerber").tally)
    assert winners["mock.landtag-einzelbewerber.wk.017"].endswith(".einzelbewerber")
    assert not winners["mock.landtag-einzelbewerber.wk.030"].endswith(".einzelbewerber")


def test_landtag_fragmented_has_seven_parties_above_threshold():
    share = zweitstimmen(read("landtag-fragmented").tally)
    assert len(share) == 12
    assert max(share.values()) < Fraction(1, 5)
    assert sum(1 for value in share.values() if value >= Fraction(5, 100)) == 7


def test_landtag_briefwahl_decides_wahlkreise():
    tally = read("landtag-briefwahl-heavy").tally
    assert tally.filter(kind="voters", channel="brief").total() > tally.filter(kind="voters", channel="urne").total()
    everyone = wahlkreis_winners(tally)
    urne = wahlkreis_winners(tally.filter(channel="urne"))
    assert sum(everyone[unit] != urne[unit] for unit in everyone) >= 10
