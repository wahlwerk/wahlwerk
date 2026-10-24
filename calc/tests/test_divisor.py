import math
import random
from fractions import Fraction

import numpy as np
import pytest

from wahlwerk_calc import divisor as d
from wahlwerk_calc.result import SeatResult

from reference import divisor_seats

POSTS = {
    d.d_hondt: lambda k: k + 1,
    d.sainte_lague: lambda k: k + Fraction(1, 2),
    d.adams: lambda k: k,
    d.danish: lambda k: k + Fraction(1, 3),
    d.imperiali: lambda k: k + 2,
    d.modified_sainte_lague: lambda k: Fraction(7, 10) if k == 0 else k + Fraction(1, 2),
    d.dean: lambda k: Fraction(k * (k + 1)) / (k + Fraction(1, 2)),
}


def _check(result: SeatResult, expected):
    seats, tied, left = expected
    assert result.seats == seats
    assert set(result.tied) == tied
    assert result.open == left


@pytest.mark.parametrize("method", POSTS, ids=lambda f: f.__name__)
def test_matches_exact_ranking_on_random_votes(method):
    rng = random.Random(method.__name__)
    for _ in range(300):
        n = rng.randint(1, 6)
        # Small numbers make ties common; large ones exercise the float ranking.
        top = rng.choice([4, 12, 10**6])
        votes = {f"k{i}": rng.randint(0, top) for i in range(n)}
        if not any(votes.values()):
            continue
        seats = rng.randint(0, 25)
        _check(method(votes, seats), divisor_seats(votes, seats, POSTS[method]))


def test_huntington_hill_against_squared_ranking():
    rng = random.Random(7)
    for _ in range(200):
        votes = {f"k{i}": rng.randint(0, 30) for i in range(rng.randint(1, 5))}
        if not any(votes.values()):
            continue
        seats = rng.randint(0, 15)
        claims = sorted(
            ((math.inf if k == 0 else v / math.sqrt(k * (k + 1)), key) for key, v in votes.items() if v for k in range(seats)),
            reverse=True,
        )
        result = d.huntington_hill(votes, seats)
        assert result.total + result.open == seats
        if result.is_decided and seats:
            assert claims[seats - 1][0] > (claims[seats][0] if len(claims) > seats else -1) or claims[seats - 1][0] == math.inf


def test_close_claims_beyond_float_precision_are_ranked_exactly():
    # 10**17 + 1 and 10**17 are equal as floats; their claims are not.
    result = d.d_hondt({"a": 10**17 + 1, "b": 10**17}, 1)
    assert result.seats == {"a": 1, "b": 0}
    assert result.is_decided


def test_tie_is_a_result():
    result = d.d_hondt({"a": 2, "b": 2, "c": 1}, 1)
    assert result.tied == ["a", "b"] and result.open == 1
    assert result.with_lot(["b"]).seats == {"a": 0, "b": 1, "c": 0}
    with pytest.raises(ValueError, match="not all tied"):
        result.with_lot(["c"])


def test_arrays_floats_and_batches():
    assert d.sainte_lague([47, 16, 15, 6], 10).seats.tolist() == [5, 2, 2, 1]
    assert d.sainte_lague(np.array([0.47, 0.16, 0.15, 0.06]), 10).seats.tolist() == [5, 2, 2, 1]
    assert d.sainte_lague({"a": "47", "b": "16.0", "c": "15", "d": 6}, 10).seats == {"a": 5, "b": 2, "c": 2, "d": 1}
    batch = d.d_hondt(np.array([[47, 16, 15, 6], [10, 10, 10, 10]]), [10, 4])
    assert batch.seats.tolist() == [[6, 2, 2, 0], [1, 1, 1, 1]]
    keyed = d.d_hondt({"a": [47, 10], "b": [16, 10]}, 3)
    assert keyed.seats["a"].tolist() == [2, 1] and keyed.seats["b"].tolist() == [1, 1]
    assert keyed.tied == [[], ["a", "b"]] and keyed.open.tolist() == [0, 1]
    assert np.asarray(d.d_hondt([3, 1], 4)).tolist() == [3, 1]


def test_bad_input():
    with pytest.raises(TypeError, match="bool"):
        d.d_hondt({"a": True}, 1)
    with pytest.raises(ValueError, match="negative"):
        d.d_hondt({"a": -1, "b": 2}, 1)
    with pytest.raises(ValueError, match="every weight is 0"):
        d.d_hondt({"a": 0}, 1)
    with pytest.raises(ValueError, match="finite"):
        d.d_hondt([math.nan, 1.0], 1)
    assert d.d_hondt({"a": 0}, 0).seats == {"a": 0}


def test_divisor_range_and_seats_at_agree():
    votes = {"a": 47, "b": 16, "c": 15, "d": 6}
    for sp in (d.D_HONDT, d.SAINTE_LAGUE, d.DANISH):
        low, high = d.divisor_range(votes, 10, sp)
        middle = (Fraction(low) + Fraction(high)) / 2
        assert d.seats_at(votes, middle, sp) == d.highest_averages(votes, 10, sp)
        on_edge = d.seats_at(votes, high, sp)
        assert not on_edge.is_decided


def test_from_divisors_matches_named_methods():
    votes = {"a": 47, "b": 16, "c": 15, "d": 6}
    assert d.highest_averages(votes, 10, d.Signposts.from_divisors(1, 2)) == d.sainte_lague(votes, 10)
    assert d.highest_averages(votes, 10, d.Signposts.from_divisors(2, 1)) == d.imperiali(votes, 10)


def test_house_monotonicity():
    rng = random.Random(3)
    for _ in range(100):
        votes = [rng.randint(1, 1000) for _ in range(5)]
        previous = np.asarray(d.sainte_lague(votes, 1))
        for seats in range(2, 30):
            current = d.sainte_lague(votes, seats)
            if current.is_decided:
                assert np.all(np.asarray(current) >= previous)
                previous = np.asarray(current)
