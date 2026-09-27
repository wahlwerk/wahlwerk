import pytest
from pydantic import ValidationError

from wahlwerk.vote.popular import Level, Tally, TallyKind, TallyRow

UNIT = {"unit": "de.st.wk.001", "level": "wahlkreis"}
VOTE = {**UNIT, "section": "zweitstimme"}


def test_valid_vote_row():
    row = TallyRow(**VOTE, party="spd", count=1234)
    assert row.kind is TallyKind.VOTES
    assert row.party == "spd"
    assert row.candidate is None
    assert row.channel is None
    assert row.count == 1234


def test_valid_vote_row_for_an_independent_candidate():
    row = TallyRow(**VOTE, candidate="de.st.wk.001.mueller", count=12)
    assert row.party is None


def test_referendum_row():
    row = TallyRow(**UNIT, section="frage-1", option="ja", count=5000)
    assert row.kind is TallyKind.VOTES
    assert row.party is None
    assert row.candidate is None


def test_invalid_vote_row():
    row = TallyRow(**VOTE, kind=TallyKind.INVALID, count=56)
    assert row.party is None
    assert row.candidate is None


@pytest.mark.parametrize("kind", [TallyKind.ELIGIBLE, TallyKind.VOTERS])
def test_people_row(kind):
    row = TallyRow(**UNIT, kind=kind, count=150000)
    assert row.section is None


def test_people_row_by_channel():
    """Briefwähler are voters counted in the postal channel."""
    row = TallyRow(**UNIT, kind=TallyKind.VOTERS, channel="brief", count=40000)
    assert row.channel == "brief"


def test_kind_from_string():
    assert TallyRow(**UNIT, kind="eligible", count=1).kind is TallyKind.ELIGIBLE


def test_valid_vote_row_without_recipient_is_rejected():
    with pytest.raises(ValidationError, match="neither a party, a candidate nor an option"):
        TallyRow(**VOTE, count=1)


@pytest.mark.parametrize(
    "recipient", [{"party": "spd"}, {"candidate": "de.st.wk.001.mueller"}]
)
def test_vote_row_with_recipient_and_option_is_rejected(recipient):
    with pytest.raises(ValidationError, match="both a recipient and an option"):
        TallyRow(**VOTE, **recipient, option="ja", count=1)


@pytest.mark.parametrize("kind", [TallyKind.VOTES, TallyKind.INVALID])
def test_vote_row_without_section_is_rejected(kind):
    with pytest.raises(ValidationError, match="names no section"):
        TallyRow(**UNIT, kind=kind, party="spd", count=1)


@pytest.mark.parametrize("kind", [TallyKind.ELIGIBLE, TallyKind.VOTERS])
def test_people_row_with_section_is_rejected(kind):
    with pytest.raises(ValidationError, match="must name no section"):
        TallyRow(**VOTE, kind=kind, count=1)


@pytest.mark.parametrize("kind", [TallyKind.INVALID, TallyKind.ELIGIBLE, TallyKind.VOTERS])
@pytest.mark.parametrize(
    "recipient",
    [{"party": "spd"}, {"candidate": "de.st.wk.001.mueller"}, {"option": "ja"}],
)
def test_non_vote_row_with_recipient_is_rejected(kind, recipient):
    section = {"section": "zweitstimme"} if kind is TallyKind.INVALID else {}
    with pytest.raises(ValidationError, match="must name no party, candidate or option"):
        TallyRow(**UNIT, **section, **recipient, kind=kind, count=1)


def test_negative_count_is_rejected():
    with pytest.raises(ValidationError):
        TallyRow(**VOTE, party="spd", count=-1)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        TallyRow(**VOTE, party="spd", count=1, Stimmart="zweitstimme")


# ===========================================================
# Tally
# ===========================================================
WBZ_1 = "de.st.wk.001.gem.15081026.wbz.000001"
WBZ_2 = "de.st.wk.001.gem.15081026.wbz.000002"
WBZ_3 = "de.st.wk.002.gem.15081030.wbz.000001"


def row(unit, count, *, party="afd", section="zweitstimme", channel="urne", **fields):
    return TallyRow(
        unit=unit,
        level="wahlbezirk",
        section=section,
        channel=channel,
        party=party,
        count=count,
        **fields,
    )


TALLY = Tally(
    rows=(
        row(WBZ_1, 209),
        row(WBZ_1, 61, party="cdu"),
        row(WBZ_1, 217, section="erststimme"),
        row(WBZ_2, 100),
        row(WBZ_2, 40, channel="brief"),
        row(WBZ_3, 50, party="cdu"),
        TallyRow(unit=WBZ_1, level="wahlbezirk", kind="eligible", count=590),
    )
)


def test_empty_tally():
    assert len(Tally()) == 0
    assert Tally().total() == 0


def test_duplicate_rows_are_rejected():
    with pytest.raises(ValidationError, match="more than once"):
        Tally(rows=(row(WBZ_1, 1), row(WBZ_1, 2)))


def test_rows_differing_in_one_field_are_not_duplicates():
    assert len(Tally(rows=(row(WBZ_1, 1), row(WBZ_1, 2, channel="brief")))) == 2


def test_filter():
    zweit = TALLY.filter(kind="votes", section="zweitstimme")
    assert len(zweit) == 5
    assert TALLY.filter(kind=TallyKind.VOTES, section="zweitstimme") == zweit
    assert TALLY.filter(party="cdu").total() == 111


def test_filter_on_absent_field():
    assert TALLY.filter(section=None).total() == 590


def test_filter_rejects_unknown_field_and_count():
    with pytest.raises(ValueError, match="not tally fields"):
        TALLY.filter(partei="afd")
    with pytest.raises(ValueError, match="not tally fields"):
        TALLY.filter(count=1)


def test_sum_to_wahlkreis():
    wk = TALLY.filter(kind="votes", section="zweitstimme").sum_to("wahlkreis", depth=4)
    assert {(r.unit, r.party, r.channel): r.count for r in wk.rows} == {
        ("de.st.wk.001", "afd", "urne"): 309,
        ("de.st.wk.001", "cdu", "urne"): 61,
        ("de.st.wk.001", "afd", "brief"): 40,
        ("de.st.wk.002", "cdu", "urne"): 50,
    }
    assert {r.level for r in wk.rows} == {"wahlkreis"}


def test_sum_to_keeps_order_of_first_appearance():
    land = TALLY.filter(kind="votes", section="zweitstimme").sum_to("land", depth=2)
    assert [(r.party, r.channel) for r in land.rows] == [
        ("afd", "urne"),
        ("cdu", "urne"),
        ("afd", "brief"),
    ]


def test_sum_to_keeps_the_total():
    assert TALLY.sum_to("land", depth=2).total() == TALLY.total()


def test_sum_to_rejects_bad_depth():
    with pytest.raises(ValueError, match="fewer than depth 9"):
        TALLY.sum_to("x", depth=9)
    with pytest.raises(ValueError, match="below 1"):
        TALLY.sum_to("x", depth=0)
    with pytest.raises(TypeError):
        TALLY.sum_to("x", depth=True)


def test_sum_to_without_levels_needs_depth():
    with pytest.raises(ValueError, match="records no levels"):
        TALLY.sum_to("wahlkreis")


def test_sum_by_one_field_gives_plain_keys():
    assert TALLY.filter(kind="votes", section="zweitstimme").sum_by("party") == {
        "afd": 349,
        "cdu": 111,
    }


def test_sum_by_several_fields_gives_tuple_keys():
    by = TALLY.filter(kind="votes").sum_by("section", "party")
    assert by == {("zweitstimme", "afd"): 349, ("zweitstimme", "cdu"): 111, ("erststimme", "afd"): 217}


def test_sum_by_rejects_no_or_unknown_field():
    with pytest.raises(ValueError, match="at least one field"):
        TALLY.sum_by()
    with pytest.raises(ValueError, match="not tally fields"):
        TALLY.sum_by("partei")


# ===========================================================
# Levels
# ===========================================================
LEVELS = (
    Level(name="land", depth=2),
    Level(name="wahlkreis", depth=4),
    Level(name="wahlbezirk", depth=8),
)
LEVELLED = Tally(rows=TALLY.rows, levels=LEVELS)


def test_level_depth_is_strict():
    with pytest.raises(ValidationError):
        Level(name="wahlkreis", depth="4")
    with pytest.raises(ValidationError):
        Level(name="wahlkreis", depth=True)
    with pytest.raises(ValidationError):
        Level(name="wahlkreis", depth=0)


def test_levels_listed_twice_are_rejected():
    with pytest.raises(ValidationError, match="listed more than once"):
        Tally(levels=(Level(name="land", depth=2), Level(name="land", depth=3)))


def test_row_at_unlisted_level_is_rejected():
    with pytest.raises(ValidationError, match="not one of"):
        Tally(rows=TALLY.rows, levels=LEVELS[:2])


def test_row_at_wrong_depth_is_rejected():
    rows = (row("de.st.wk.001", 1),)  # level wahlbezirk, but 4 segments
    with pytest.raises(ValidationError, match="has 4 segments, but level 'wahlbezirk' is 8"):
        Tally(rows=rows, levels=LEVELS)


def test_sum_to_takes_depth_from_levels():
    zweit = LEVELLED.filter(kind="votes", section="zweitstimme")
    assert zweit.sum_to("wahlkreis") == zweit.sum_to("wahlkreis", depth=4)
    assert zweit.sum_to("wahlkreis").sum_by("unit") == {"de.st.wk.001": 410, "de.st.wk.002": 50}


def test_sum_to_and_filter_keep_levels():
    assert LEVELLED.filter(party="cdu").levels == LEVELS
    assert LEVELLED.sum_to("land").levels == LEVELS


def test_sum_to_can_go_on_from_a_sum():
    wk = LEVELLED.filter(kind="votes").sum_to("wahlkreis")
    assert wk.sum_to("land").total() == LEVELLED.filter(kind="votes").total()


def test_sum_to_unlisted_level_is_rejected():
    with pytest.raises(ValueError, match="'gemeinde' is not one of"):
        LEVELLED.sum_to("gemeinde")


def test_sum_to_contradicting_depth_is_rejected():
    with pytest.raises(ValueError, match="depth 5 contradicts level 'wahlkreis'"):
        LEVELLED.sum_to("wahlkreis", depth=5)
