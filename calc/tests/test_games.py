import random
from fractions import Fraction

import pytest

from wahlwerk_calc import coalition, power

from reference import shapley_shubik, swings


def test_power_against_enumeration():
    rng = random.Random(5)
    for _ in range(100):
        weights = [rng.randint(0, 12) for _ in range(rng.randint(1, 6))]
        if not sum(weights):
            continue
        quota = rng.randint(1, sum(weights))
        assert power.swings(weights, quota).tolist() == swings(weights, quota)
        assert power.shapley_shubik(weights, quota).tolist() == shapley_shubik(weights, quota)
        eta = swings(weights, quota)
        if sum(eta):
            assert power.banzhaf(weights, quota).tolist() == [Fraction(e, sum(eta)) for e in eta]


def test_un_security_council():
    """Five permanent members with a veto, ten others; nine votes needed."""
    weights = [7] * 5 + [1] * 10
    phi = power.shapley_shubik(weights, quota=39)
    assert phi[0] == Fraction(421, 2145)  # 0.1963, the textbook value
    assert sum(phi) == 1


def test_keyed_and_default_quota():
    seats = {"a": 50, "b": 49, "c": 1}
    assert power.banzhaf(seats) == {"a": Fraction(3, 5), "b": Fraction(1, 5), "c": Fraction(1, 5)}
    assert power.penrose(seats)["a"] == Fraction(3, 4)
    with pytest.raises(TypeError, match="whole"):
        power.banzhaf([1.5, 2])


def test_coalitions():
    seats = {"a": 40, "b": 35, "c": 15, "d": 10}
    assert coalition.is_winning(seats, ["a", "c"])
    assert not coalition.is_winning(seats, ["a", "d"])
    assert coalition.surplus(seats, ["a", "b"]) == 24
    assert coalition.minimal_winning(seats) == [frozenset("ab"), frozenset("bcd"), frozenset("ac")]
    assert coalition.minimum_winning(seats) == [frozenset("ac")]
    assert len(coalition.winning(seats)) == 7  # a+d and b+c have 50 of 100
    assert coalition.minimal_winning([2, 1, 1], quota=3) == [frozenset({0, 1}), frozenset({0, 2})]
