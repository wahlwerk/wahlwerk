import math
from fractions import Fraction

import numpy as np
import pytest

from wahlwerk.calc import divisor
from wahlwerk.calc import fragmentation as f
from wahlwerk.calc import proportionality as p

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

CANADA_2015_VOTES = {"liberal": 6943276, "conservative": 5613614, "ndp": 3470350, "bloc": 821144, "green": 602944, "other": 91837}
CANADA_2015_SEATS = {"liberal": 184, "conservative": 99, "ndp": 44, "bloc": 10, "green": 1}


@pytest.mark.parametrize(("index", "value"), PERFECT.items(), ids=lambda x: getattr(x, "__name__", x))
def test_perfect_proportion(index, value):
    equal = {"a": 7, "b": 5, "c": 3}
    assert index(equal, equal) == value
    assert index([0.7, 0.5, 0.3], [7.0, 5.0, 3.0]) == pytest.approx(value)


def test_kalogirou_examples():
    assert p.loosemore_hanby({"a": 68, "b": 22}, {"a": 2}) == Fraction(11, 45)
    assert p.loosemore_hanby({"a": 68, "b": 22, "c": 10}, {"a": 1, "b": 1}) == Fraction(7, 25)
    assert p.rose({"a": 68, "b": 22}, {"a": 2}) == Fraction(34, 45)
    assert p.d_hondt({"other": 99924, "aosta": 76}, {"other": 99841, "aosta": 159}) == Fraction(159, 76)
    assert p.lijphart({"a": 68, "b": 22, "c": 10}, {"a": 1, "b": 1}) == Fraction(28, 100)
    assert p.rae({"a": 68, "b": 22, "c": 10}, {"a": 1, "b": 1}) == Fraction(56, 300)


def test_gallagher_canada_2015():
    squared = p.gallagher_squared(CANADA_2015_VOTES, CANADA_2015_SEATS)
    assert isinstance(squared, Fraction)
    assert abs(p.gallagher(CANADA_2015_VOTES, CANADA_2015_SEATS) - 0.12) < 0.001
    assert math.isclose(p.gallagher(CANADA_2015_VOTES, CANADA_2015_SEATS), math.sqrt(squared))


def test_sainte_lague_method_minimises_its_index():
    votes = {"a": 575971, "b": 226605, "c": 122296, "d": 117494}
    best = divisor.sainte_lague(votes, 20).seats
    index = p.sainte_lague(votes, best)
    for gainer in votes:
        for loser in votes:
            if gainer != loser and best[loser]:
                moved = {**best, gainer: best[gainer] + 1, loser: best[loser] - 1}
                assert p.sainte_lague(votes, moved) >= index


def test_infinite_and_missing_keys():
    assert p.lijphart({"a": 1}, {"a": 1, "b": 1}) == Fraction(1, 2)
    with pytest.raises(ValueError, match="infinite"):
        p.sainte_lague({"a": 1}, {"a": 1, "b": 1})
    assert p.advantage_ratio({"a": 3, "b": 1}, {"a": 1, "b": 1}) == {"a": Fraction(2, 3), "b": 2}


def test_batches():
    votes = np.array([[7, 5, 3], [10, 0, 0]])
    seats = np.array([[7, 5, 3], [1, 1, 1]])
    assert p.loosemore_hanby(votes, seats).tolist() == [0, Fraction(2, 3)]


def test_fragmentation():
    assert f.herfindahl({"a": 1}) == 1
    assert f.effective_number([1, 1, 1, 1]) == 4
    assert f.effective_number({"a": 50, "b": 30, "c": 20}) == Fraction(50, 19)
    assert f.fractionalization([1, 1]) == Fraction(1, 2)
    assert f.golosov([1, 1, 1]) == 3
    assert f.largest_share([3, 1]) == Fraction(3, 4)
    assert f.effective_number(np.array([[1, 1], [1, 0]])).tolist() == [2, 1]
    assert f.effective_number([0.5, 0.5]) == 2.0


def test_shares_and_counts_both_ways():
    from wahlwerk.calc import share

    assert share.shares({"a": 3, "b": 1}, per=100) == {"a": 75, "b": 25}
    assert share.shares([0.3, 0.1]).tolist() == pytest.approx([0.75, 0.25])  # floats stay floats
    # exact from floats: as decimals, never binary noise
    assert share.counts({"a": 32.5, "b": 67.5}, 1000, per=100) == {"a": 325, "b": 675}
    assert share.counts([0.1, 0.7], 10).tolist() == [1, 7]
    assert share.counts(np.array([0.1, 0.2]), 3).tolist() == [Fraction(3, 10), Fraction(3, 5)]
    assert share.counts(["32.5", "67.5"], "1000", per="100").tolist() == [325, 675]
    # several scenarios, one total each
    assert share.counts([[0.5, 0.5], [0.25, 0.75]], [10, 8]).tolist() == [[5, 5], [2, 6]]
    # and back again
    votes = {"a": 1234, "b": 4321, "c": 999}
    assert share.counts(share.shares(votes), sum(votes.values())) == votes
    with pytest.raises(ValueError, match="share above"):
        share.counts([1.5], 10)
    with pytest.raises(ValueError, match="negative"):
        share.counts([0.5], -1)
