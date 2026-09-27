import math
from fractions import Fraction

import pytest

from wahlwerk.apportionment.divisor import SainteLague
from wahlwerk.measure import proportionality as p

# Reference values from the test suite of votelib (github.com/simberaj/votelib, MIT).
PERFECT = {
    p.loosemore_hanby: 0,
    p.rose: 1,
    p.gallagher_squared: 0,
    p.rae: 0,
    p.lijphart: 0,
    p.sainte_lague: 0,
    p.d_hondt: 1,
    p.regression: 1,
}

CANADA_2015_VOTES = {
    "liberal": 6943276,
    "conservative": 5613614,
    "ndp": 3470350,
    "bloc": 821144,
    "green": 602944,
    "other": 91837,
}
CANADA_2015_SEATS = {"liberal": 184, "conservative": 99, "ndp": 44, "bloc": 10, "green": 1}


@pytest.mark.parametrize(("index", "value"), PERFECT.items(), ids=lambda x: getattr(x, "__name__", x))
def test_perfect_proportion(index, value):
    equal = {"a": 7, "b": 5, "c": 3}
    result = index(equal, equal)
    assert result == value
    assert isinstance(result, Fraction)


def test_loosemore_hanby_kalogirou():
    assert p.loosemore_hanby({"a": 68, "b": 22}, {"a": 2}) == Fraction(11, 45)  # 0.24
    assert p.loosemore_hanby({"a": 68, "b": 22, "c": 10}, {"a": 1, "b": 1}) == Fraction(7, 25)


def test_rose_is_one_minus_loosemore_hanby():
    assert p.rose({"a": 68, "b": 22}, {"a": 2}) == Fraction(34, 45)


def test_d_hondt_kalogirou_italy_1983():
    index = p.d_hondt({"other": 99924, "aosta": 76}, {"other": 99841, "aosta": 159})
    assert index == Fraction(159, 76)
    assert round(float(index), 3) == 2.092


def test_gallagher_canada_2015():
    """About 0.12, per iscanadafair.ca; the root is taken only to compare."""
    squared = p.gallagher_squared(CANADA_2015_VOTES, CANADA_2015_SEATS)
    assert isinstance(squared, Fraction)
    assert abs(math.sqrt(squared) - 0.12) < 0.001


def test_regression_bias():
    votes = {"a": 7, "b": 5, "c": 3}
    assert p.regression(votes, {"a": 7, "b": 5, "c": 2}) > 1
    assert p.regression(votes, {"a": 7, "b": 5, "c": 4}) < 1


def test_lijphart_and_rae():
    votes, seats = {"a": 68, "b": 22, "c": 10}, {"a": 1, "b": 1}
    assert p.lijphart(votes, seats) == Fraction(28, 100)
    assert p.rae(votes, seats) == Fraction(56, 300)


def test_sainte_lague_method_minimises_its_index():
    votes = {"a": 575971, "b": 226605, "c": 122296, "d": 117494}
    best = SainteLague().apportion(votes, 20).as_dict()
    index = p.sainte_lague(votes, best)
    for gainer in votes:
        for loser in votes:
            if gainer != loser and best[loser]:
                moved = {**best, gainer: best[gainer] + 1, loser: best[loser] - 1}
                assert p.sainte_lague(votes, moved) >= index


def test_keys_on_one_side_count_as_zero():
    assert p.lijphart({"a": 1}, {"a": 1, "b": 1}) == Fraction(1, 2)


def test_seats_without_votes_are_infinite():
    with pytest.raises(ValueError, match="infinite"):
        p.sainte_lague({"a": 1}, {"a": 1, "b": 1})
    with pytest.raises(ValueError, match="infinite"):
        p.d_hondt({"a": 1}, {"a": 1, "b": 1})


def test_bad_input():
    with pytest.raises(TypeError, match="exact"):
        p.loosemore_hanby({"a": 0.5}, {"a": 1})
    with pytest.raises(TypeError, match="exact"):
        p.loosemore_hanby({"a": 1}, {"a": Fraction(1, 2)})
    with pytest.raises(ValueError, match="negative"):
        p.loosemore_hanby({"a": -1}, {"a": 1})
    with pytest.raises(ValueError, match="some votes and some seats"):
        p.loosemore_hanby({"a": 0}, {"a": 1})
