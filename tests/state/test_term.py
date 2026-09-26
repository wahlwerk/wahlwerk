from datetime import date

import pytest
from pydantic import ValidationError

from wahlwerk.state import Term

BT = "de.bund.bundestag"


def test_minimal_term():
    term = Term(body=BT)
    assert term.body == BT
    assert term.start is None
    assert not term.is_ended


def test_full_term():
    term = Term(
        body=BT,
        number=21,
        elected_on=date(2025, 2, 23),
        start=date(2025, 3, 25),
    )
    assert term.number == 21


def test_body_is_optional():
    assert Term().body is None


def test_order_error_without_body_names_term():
    with pytest.raises(ValidationError, match="term: term starts"):
        Term(elected_on=date(2025, 2, 23), start=date(2025, 2, 1))


def test_body_must_be_lowercase_dotted_key():
    with pytest.raises(ValidationError):
        Term(body="de.bund.Bundestag")


def test_number_counts_from_one():
    with pytest.raises(ValidationError):
        Term(body=BT, number=0)


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Term(body=BT, nummer=21)


def test_is_frozen():
    term = Term(body=BT)
    with pytest.raises(ValidationError):
        term.number = 2


def test_start_before_election_is_rejected():
    with pytest.raises(ValidationError, match="before the election"):
        Term(body=BT, elected_on=date(2025, 2, 23), start=date(2025, 2, 1))


@pytest.mark.parametrize("field", ["scheduled_end", "actual_end"])
def test_end_before_start_is_rejected(field):
    with pytest.raises(ValidationError, match=f"{field} .* precedes start"):
        Term(body=BT, start=date(2021, 10, 26), **{field: date(2021, 10, 1)})


def test_is_ended_early():
    term = Term(
        body=BT,
        start=date(2021, 10, 26),
        scheduled_end=date(2025, 10, 25),
        actual_end=date(2025, 3, 24),
    )
    assert term.is_ended
    assert term.is_ended_early


def test_ended_on_schedule_is_not_early():
    end = date(2025, 10, 25)
    term = Term(body=BT, start=date(2021, 10, 26), scheduled_end=end, actual_end=end)
    assert term.is_ended
    assert not term.is_ended_early
