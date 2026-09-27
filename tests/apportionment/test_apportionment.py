import random
from fractions import Fraction

import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.divisor import DHondt, LinearDivisor, SainteLague
from wahlwerk.apportionment.remainder import HareNiemeyer
from wahlwerk.apportionment.result import Apportionment
from wahlwerk.apportionment.tie import Tie

METHODS = [DHondt(), SainteLague(), HareNiemeyer()]

# Worked by hand for 8 seats:
#   D'Hondt      a 100 50 33.3 25 | b 80 40 26.7 | c 30 | d 20       -> 4 3 1 0
#   Sainte-Laguë a 100 33.3 20    | b 80 26.7 16 | c 30 | d 20       -> 3 3 1 1
#   Hare 230/8   a 3.48 b 2.78 c 1.04 d 0.70; floors 3 2 1 0, rest to b, d -> 3 3 1 1
WEIGHTS = {"a": 100, "b": 80, "c": 30, "d": 20}


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        (DHondt(), {"a": 4, "b": 3, "c": 1, "d": 0}),
        (SainteLague(), {"a": 3, "b": 3, "c": 1, "d": 1}),
        (HareNiemeyer(), {"a": 3, "b": 3, "c": 1, "d": 1}),
    ],
)
def test_worked_example(method, expected):
    result = method.apportion(WEIGHTS, 8)
    assert result.as_dict() == expected
    assert result.is_decided
    assert result.total == 8


def test_sachsen_anhalt_2026_hare_niemeyer():
    """Sec. 35 (5) LWG LSA on the 2026 Zweitstimmen of the parties past 5 %."""
    votes = {
        "afd": 575971,
        "cdu": 226605,
        "spd": 122296,
        "gruene": 117494,
        "linke": 112558,
        "bsw": 69355,
    }
    result = HareNiemeyer().apportion(votes, 83)
    assert result.as_dict() == {"afd": 39, "cdu": 15, "spd": 8, "gruene": 8, "linke": 8, "bsw": 5}


def test_order_of_keys_is_kept():
    weights = {"z": 1, "a": 5, "m": 3}
    for method in METHODS:
        assert [key for key, _ in method.apportion(weights, 4).seats] == ["z", "a", "m"]


def test_zero_weight_wins_nothing():
    for method in METHODS:
        result = method.apportion({"a": 10, "b": 0}, 3)
        assert result.as_dict() == {"a": 3, "b": 0}


def test_zero_seats():
    for method in METHODS:
        assert DHondt().apportion({"a": 0, "b": 0}, 0).as_dict() == {"a": 0, "b": 0}
        assert method.apportion({"a": 5}, 0).total == 0


def test_fraction_weights():
    result = HareNiemeyer().apportion({"a": Fraction(1, 3), "b": Fraction(2, 3)}, 3)
    assert result.as_dict() == {"a": 1, "b": 2}


# ===========================================================
# Ties
# ===========================================================
def test_exact_tie_is_a_result():
    # D'Hondt: a 3, 1.5, 1 | b 1, 0.5 -> 3 and 1.5 decided; a's 1 and b's 1 tie.
    result = DHondt().apportion({"a": 3, "b": 1}, 3)
    assert result.as_dict() == {"a": 2, "b": 0}
    assert result.tie == Tie(candidates=frozenset({"a", "b"}), seats=1)
    assert not result.is_decided
    assert result.total == 2


@pytest.mark.parametrize("method", METHODS)
def test_all_equal_ties_everyone(method):
    result = method.apportion({"a": 1, "b": 1, "c": 1}, 2)
    assert result.tie == Tie(candidates=frozenset({"a", "b", "c"}), seats=2)
    assert result.total == 0


def test_equal_claims_that_all_fit_are_no_tie():
    assert DHondt().apportion({"a": 1, "b": 1}, 2).as_dict() == {"a": 1, "b": 1}


def test_with_lot_decides_the_tie():
    decided = DHondt().apportion({"a": 3, "b": 1}, 3).with_lot(["b"])
    assert decided.as_dict() == {"a": 2, "b": 1}
    assert decided.is_decided


def test_with_lot_rejects_wrong_winners():
    tied = HareNiemeyer().apportion({"a": 1, "b": 1, "c": 1}, 2)
    with pytest.raises(ValueError, match="must name 2 winners"):
        tied.with_lot(["a"])
    with pytest.raises(ValueError, match="more than once"):
        tied.with_lot(["a", "a"])
    with pytest.raises(ValueError, match=r"\['x'\] are not candidates"):
        tied.with_lot(["a", "x"])
    with pytest.raises(ValueError, match="no tie"):
        DHondt().apportion(WEIGHTS, 8).with_lot([])


def test_tie_needs_more_candidates_than_seats():
    with pytest.raises(ValidationError, match="more candidates than seats"):
        Tie(candidates=frozenset({"a", "b"}), seats=2)
    with pytest.raises(ValidationError):
        Tie(candidates=frozenset({"a", "b"}), seats=0)


# ===========================================================
# Apportionment
# ===========================================================
def test_lookup():
    result = DHondt().apportion(WEIGHTS, 8)
    assert result["a"] == 4
    assert result.get("x") is None
    assert result.get("x", 0) == 0
    with pytest.raises(KeyError, match="'x'"):
        result["x"]


def test_apportionment_rejects_duplicate_keys_and_foreign_tie():
    with pytest.raises(ValidationError, match="more than once"):
        Apportionment(seats=(("a", 1), ("a", 2)))
    with pytest.raises(ValidationError, match="not apportioned keys"):
        Apportionment(seats=(("a", 0),), tie=Tie(candidates=frozenset({"a", "b"}), seats=1))


# ===========================================================
# Input
# ===========================================================
@pytest.mark.parametrize("weight", [1.5, True, "3", None])
def test_inexact_weight_is_a_type_error(weight):
    with pytest.raises(TypeError, match="must be an int or a Fraction"):
        DHondt().apportion({"a": weight}, 1)


def test_bad_weights_and_seats():
    with pytest.raises(ValueError, match="negative"):
        DHondt().apportion({"a": -1}, 1)
    with pytest.raises(TypeError, match="non-empty strings"):
        DHondt().apportion({"": 1}, 1)
    with pytest.raises(TypeError, match="mapping"):
        DHondt().apportion([("a", 1)], 1)
    with pytest.raises(TypeError, match="seats must be an int"):
        DHondt().apportion({"a": 1}, 1.0)
    with pytest.raises(TypeError, match="seats must be an int"):
        DHondt().apportion({"a": 1}, True)
    with pytest.raises(ValueError, match="seats is negative"):
        DHondt().apportion({"a": 1}, -1)
    with pytest.raises(ValueError, match="every weight is 0"):
        HareNiemeyer().apportion({"a": 0}, 1)


def test_linear_divisor_rejects_floats_and_non_positive():
    with pytest.raises(ValidationError, match="exact"):
        LinearDivisor(first=0.5, step=1)
    with pytest.raises(ValidationError):
        LinearDivisor(first=0, step=1)
    with pytest.raises(ValidationError):
        LinearDivisor(first=1, step=0)
    assert LinearDivisor(first="1/2", step=1).first == Fraction(1, 2)


# ===========================================================
# Properties, over seeded random inputs
# ===========================================================
def cases(count=200):
    rng = random.Random(2026)
    for _ in range(count):
        keys = [f"p{i}" for i in range(rng.randint(1, 8))]
        weights = {key: rng.randint(0, 10_000) for key in keys}
        if not any(weights.values()):
            weights[keys[0]] = 1
        yield weights, rng.randint(1, 120)


def test_named_divisor_methods_are_linear_divisors():
    for weights, seats in cases():
        assert LinearDivisor(first=1, step=1).apportion(weights, seats) == DHondt().apportion(
            weights, seats
        )
        assert LinearDivisor(first=1, step=2).apportion(
            weights, seats
        ) == SainteLague().apportion(weights, seats)
        # Standard rounding: divisors 0.5, 1.5, 2.5, ... give the same seats.
        assert LinearDivisor(first=Fraction(1, 2), step=1).apportion(
            weights, seats
        ) == SainteLague().apportion(weights, seats)


@pytest.mark.parametrize("method", METHODS)
def test_every_seat_is_given_or_tied(method):
    for weights, seats in cases():
        result = method.apportion(weights, seats)
        assert result.total + (result.tie.seats if result.tie else 0) == seats


@pytest.mark.parametrize("method", [DHondt(), SainteLague()])
def test_divisor_methods_never_take_a_seat_away_when_the_house_grows(method):
    """Divisor methods are house monotone: no Alabama paradox."""
    for weights, seats in cases(60):
        smaller, larger = method.apportion(weights, seats), method.apportion(weights, seats + 1)
        if smaller.is_decided and larger.is_decided:
            assert all(larger[key] >= smaller[key] for key in weights)


def test_hare_niemeyer_stays_within_quota():
    """Each key gets the whole part of its exact share, or one more."""
    for weights, seats in cases():
        result = HareNiemeyer().apportion(weights, seats)
        total = sum(weights.values())
        for key, weight in weights.items():
            share = Fraction(weight * seats, total)
            floor = share.numerator // share.denominator
            won = result[key] + (1 if result.tie and key in result.tie.candidates else 0)
            assert floor <= result[key] <= won <= floor + 1


# ===========================================================
# Reference results
# ===========================================================
# From the test suite of votelib (github.com/simberaj/votelib, MIT), after Pukelsheim's
# biproportional examples.
@pytest.mark.parametrize(
    ("votes", "expected"),
    [
        ({"I": 1347, "II": 1014, "III": 1444}, {"I": 7, "II": 5, "III": 8}),
        ({"A": 983, "B": 2040, "C": 782}, {"A": 5, "B": 11, "C": 4}),
    ],
)
def test_sainte_lague_reference(votes, expected):
    result = SainteLague().apportion(votes, 20)
    assert result.is_decided
    assert result.as_dict() == expected
