from fractions import Fraction

import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.threshold import (
    AbsoluteThreshold,
    AlternativeThresholds,
    Exempt,
    RelativeThreshold,
    SeatThreshold,
)

FIVE_PERCENT = RelativeThreshold(share=Fraction(5, 100))
VOTES = {"a": 50, "b": 5, "c": 4, "ssw": 1, "d": 40}


def test_relative_threshold_is_at_least_by_default():
    assert FIVE_PERCENT.select(VOTES) == {"a", "b", "d"}


def test_relative_threshold_more_than():
    strict = RelativeThreshold(share=Fraction(5, 100), accept_equal=False)
    assert strict.select(VOTES) == {"a", "d"}


def test_relative_threshold_on_sachsen_anhalt_2026():
    """Sec. 35 (3) LWG LSA: 5 % of the valid Zweitstimmen; FDP had 2.58 %."""
    votes = {
        "afd": 575971,
        "cdu": 226605,
        "spd": 122296,
        "gruene": 117494,
        "linke": 112558,
        "bsw": 69355,
        "fdp": 33986,
        "fw": 15391,
        "rest": 41626,
    }
    assert FIVE_PERCENT.select(votes) == {"afd", "cdu", "spd", "gruene", "linke", "bsw"}


def test_relative_threshold_is_exact_at_the_edge():
    # 1 of 20 is exactly 5 %; a float share would be at the mercy of rounding.
    assert FIVE_PERCENT.select({"a": 1, "b": 19}) == {"a", "b"}
    assert RelativeThreshold(share="1/20").share == Fraction(1, 20)


def test_relative_threshold_rejects_float_share():
    with pytest.raises(ValidationError, match="exact"):
        RelativeThreshold(share=0.05)


def test_absolute_threshold():
    assert AbsoluteThreshold(weight=5).select(VOTES) == {"a", "b", "d"}
    assert AbsoluteThreshold(weight=5, accept_equal=False).select(VOTES) == {"a", "d"}


def test_seat_threshold_counts_seats_won():
    assert SeatThreshold(seats=3).select(VOTES, won={"c": 3, "b": 2}) == {"c"}
    assert SeatThreshold(seats=3).select(VOTES) == frozenset()


def test_exempt_passes_only_named_keys_that_stand():
    assert Exempt(keys=frozenset({"ssw", "x"})).select(VOTES) == {"ssw"}


def test_alternative_thresholds_bundestag_shape():
    """5 % or three Wahlkreis seats, and a minority party exempt."""
    rule = AlternativeThresholds(
        thresholds=(FIVE_PERCENT, SeatThreshold(seats=3), Exempt(keys=frozenset({"ssw"})))
    )
    assert rule.select(VOTES, won={"c": 3}) == {"a", "b", "c", "d", "ssw"}


def test_alternative_thresholds_nest_and_print():
    rule = AlternativeThresholds(thresholds=(FIVE_PERCENT, SeatThreshold(seats=3)))
    assert rule == AlternativeThresholds(thresholds=(FIVE_PERCENT, SeatThreshold(seats=3)))
    assert "SeatThreshold" in repr(rule)
    assert rule.model_dump()["thresholds"][1] == {"seats": 3}


def test_alternative_thresholds_need_two():
    with pytest.raises(ValidationError):
        AlternativeThresholds(thresholds=(FIVE_PERCENT,))


def test_bad_input():
    with pytest.raises(TypeError, match="must be an int or a Fraction"):
        FIVE_PERCENT.select({"a": 0.5})
    with pytest.raises(TypeError, match="non-negative int"):
        SeatThreshold(seats=3).select(VOTES, won={"a": -1})
    with pytest.raises(ValidationError):
        SeatThreshold(seats=0)
    with pytest.raises(ValidationError):
        Exempt(keys=frozenset())


def test_uses_won():
    assert not FIVE_PERCENT.uses_won
    assert SeatThreshold(seats=3).uses_won
    assert AlternativeThresholds(thresholds=(FIVE_PERCENT, SeatThreshold(seats=3))).uses_won
    assert not AlternativeThresholds(thresholds=(FIVE_PERCENT, Exempt(keys=frozenset({"ssw"})))).uses_won
