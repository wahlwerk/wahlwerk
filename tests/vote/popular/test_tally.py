import pytest
from pydantic import ValidationError

from wahlwerk.vote.popular import TallyKind, TallyRow

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
