import random
from fractions import Fraction

import pytest

from wahlwerk.calc import compensation, majority, quota, remainder, threshold

from reference import largest_remainder_seats


@pytest.mark.parametrize("rule", [quota.hare, quota.hagenbach_bischoff, quota.droop], ids=lambda f: f.__name__)
def test_largest_remainder_matches_reference(rule):
    rng = random.Random(rule.__name__)
    for _ in range(300):
        votes = {f"k{i}": rng.randint(0, rng.choice([6, 10**5])) for i in range(rng.randint(1, 6))}
        if not any(votes.values()):
            continue
        seats = rng.randint(1, 20)
        expected = largest_remainder_seats(votes, seats, rule)
        if expected is None:  # the quota gives too many whole seats, or too few
            with pytest.raises(ValueError, match="more than"):
                remainder.largest_remainder(votes, seats, rule)
            continue
        result = remainder.largest_remainder(votes, seats, rule)
        assert (result.seats, set(result.tied), result.open) == expected


def test_quota_property_of_hare_niemeyer():
    rng = random.Random(1)
    for _ in range(200):
        votes = [rng.randint(1, 1000) for _ in range(5)]
        seats = rng.randint(1, 40)
        result = remainder.hare_niemeyer(votes, seats)
        for v, s in zip(votes, result.decided.tolist()):
            exact = Fraction(v * seats, sum(votes))
            assert s >= int(exact) and s <= int(exact) + 1


def test_quotas():
    assert quota.hare(100, 8) == Fraction(25, 2)
    assert quota.hagenbach_bischoff(100, 9) == 10
    assert quota.droop(100, 9) == 11
    assert quota.imperiali(100, 8) == 10
    assert quota.hare(100.0, 8) == 12.5


def test_majorities():
    assert majority.majority_of(598) == 300
    assert majority.majority_of(599) == 300
    assert majority.qualified_majority(630, "2/3") == 420
    assert majority.qualified_majority(631, "2/3") == 421
    assert majority.majority_of([69, 71]).tolist() == [35, 36]
    assert majority.is_majority(300, 598) and not majority.is_majority(299, 598)
    assert majority.is_majority([1, 2], [3, 3]).tolist() == [False, True]


def test_majority_first():
    assert majority.majority_first({"a": 501, "b": 499}, 2).seats == {"a": 2, "b": 0}
    assert majority.majority_first({"a": 40, "b": 35, "c": 25}, 3).seats == {"a": 1, "b": 1, "c": 1}


def test_thresholds():
    votes = {"a": 60, "b": 35, "c": 5}
    assert threshold.share_threshold(votes, "5/100") == {"a": True, "b": True, "c": True}
    assert threshold.share_threshold(votes, "5/100", accept_equal=False)["c"] is False
    assert threshold.share_threshold([0.6, 0.35, 0.05], 0.06).tolist() == [True, True, False]
    assert threshold.count_threshold(votes, 35) == {"a": True, "b": True, "c": False}
    assert threshold.seat_threshold({"a": 3, "b": 2}, 3) == {"a": True, "b": False}
    assert threshold.effective_threshold(9) == Fraction(3, 40)


def test_compensation():
    assert compensation.overhang({"a": 5, "b": 3}, {"a": 7}) == {"a": 2, "b": 0}
    assert compensation.smallest_size({"a": 60, "b": 40}, 10, {"a": 7}).seats == {"a": 7, "b": 4}
    with pytest.raises(ValueError, match="limit"):
        compensation.smallest_size({"a": 60, "b": 40}, 10, {"a": 9}, limit=12)


def test_plurality_and_whole_seats():
    from wahlwerk.calc import plurality

    assert plurality.plurality({"a": 3, "b": 5}).seats == {"a": 0, "b": 1}
    tied = plurality.plurality({"a": 5, "b": 5, "c": 1})
    assert tied.tied == ["a", "b"] and tied.open == 1
    assert plurality.plurality([5, 4, 3], 2).seats.tolist() == [1, 1, 0]
    with pytest.raises(ValueError, match="keys with votes"):
        plurality.plurality({"a": 1, "b": 0}, 2)
    assert quota.whole_seats(100, Fraction(250, 8)) == 3
    assert compensation.remaining({"a": 5, "b": 3}, {"a": 7, "b": 1, "c": 1}) == {"a": 0, "b": 2, "c": 0}
