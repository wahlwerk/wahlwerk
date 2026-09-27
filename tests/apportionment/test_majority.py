import random

import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.divisor import DHondt
from wahlwerk.apportionment.majority import MajorityFirst
from wahlwerk.apportionment.remainder import HareNiemeyer


def cases(count=200):
    rng = random.Random(2026)
    for _ in range(count):
        keys = [f"p{i}" for i in range(rng.randint(1, 8))]
        weights = {key: rng.randint(0, 10_000) for key in keys}
        if not any(weights.values()):
            weights[keys[0]] = 1
        yield weights, rng.randint(1, 120)


# ===========================================================
# MajorityFirst: Sec. 35 (6) LWG LSA
# ===========================================================
def test_majority_first_gives_the_majority_a_remainder_seat_first():
    # Hare, 10 seats: a 5.1, b 2.5, c 2.4 -> 5, 3, 2; a has 51 % but only half the seats.
    weights = {"a": 510, "b": 250, "c": 240}
    assert HareNiemeyer().apportion(weights, 10).as_dict() == {"a": 5, "b": 3, "c": 2}
    result = MajorityFirst(method=HareNiemeyer()).apportion(weights, 10)
    assert result.as_dict() == {"a": 6, "b": 2, "c": 2}
    assert result.total == 10


def test_majority_first_takes_the_seat_before_a_tie_among_the_others():
    # b and c tie for the one remainder seat; the clause gives it to a before the lot.
    weights = {"a": 510, "b": 245, "c": 245}
    assert HareNiemeyer().apportion(weights, 10).tie is not None
    result = MajorityFirst(method=HareNiemeyer()).apportion(weights, 10)
    assert result.as_dict() == {"a": 6, "b": 2, "c": 2}
    assert result.is_decided


def test_majority_first_leaves_a_majority_alone():
    weights = {"a": 560, "b": 250, "c": 190}
    method = MajorityFirst(method=HareNiemeyer())
    assert method.apportion(weights, 10) == HareNiemeyer().apportion(weights, 10)


def test_majority_first_without_a_majority_is_the_method():
    for weights, seats in cases(50):
        total = sum(weights.values())
        if all(2 * weight <= total for weight in weights.values()):
            assert MajorityFirst(method=HareNiemeyer()).apportion(
                weights, seats
            ) == HareNiemeyer().apportion(weights, seats)


def test_majority_first_always_gives_a_majority_key_more_than_half():
    for weights, seats in cases():
        total = sum(weights.values())
        majority = [key for key, weight in weights.items() if 2 * weight > total]
        if majority:
            result = MajorityFirst(method=HareNiemeyer()).apportion(weights, seats)
            assert 2 * result[majority[0]] > seats


def test_majority_first_needs_a_largest_remainder_method():
    with pytest.raises(ValidationError):
        MajorityFirst(method=DHondt())
