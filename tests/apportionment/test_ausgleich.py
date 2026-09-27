import pytest
from pydantic import ValidationError

from wahlwerk.apportionment.ausgleich import Ausgleich, overhang
from wahlwerk.apportionment.divisor import DHondt, SainteLague
from wahlwerk.apportionment.remainder import HareNiemeyer

WEIGHTS = {"a": 60, "b": 40}


def test_overhang():
    result = SainteLague().apportion(WEIGHTS, 10)  # 6, 4
    assert overhang(result, {"a": 8, "b": 1}) == {"a": 2}
    assert overhang(result, {"a": 6}) == {}
    assert overhang(result, {"x": 1}) == {"x": 1}


def test_no_overhang_keeps_the_house():
    assert Ausgleich(method=SainteLague()).apportion(WEIGHTS, 10, {"a": 6}) == SainteLague().apportion(
        WEIGHTS, 10
    )


@pytest.mark.parametrize("method", [SainteLague(), DHondt(), HareNiemeyer()])
def test_ausgleich_finds_the_smallest_house_that_covers(method):
    result = Ausgleich(method=method).apportion(WEIGHTS, 10, {"a": 8})
    house = result.total
    assert house > 10
    assert result["a"] >= 8
    assert method.apportion(WEIGHTS, house - 1)["a"] < 8


def test_ausgleich_keeps_proportion_in_the_larger_house():
    # a needs 9 seats at 60 %: the house grows to 15, b gets its 6 Ausgleich seats.
    result = Ausgleich(method=SainteLague()).apportion(WEIGHTS, 10, {"a": 9})
    assert result.as_dict() == {"a": 9, "b": 6}


def test_ausgleich_returns_a_tie_the_lot_can_settle():
    result = Ausgleich(method=SainteLague()).apportion({"a": 1, "b": 1}, 1, {"a": 1})
    assert result.tie is not None
    assert result.with_lot(["a"])["a"] == 1


def test_minimum_on_key_without_weight():
    with pytest.raises(ValueError, match="no weight"):
        Ausgleich(method=SainteLague()).apportion(WEIGHTS, 10, {"x": 1})
    assert Ausgleich(method=SainteLague()).apportion(WEIGHTS, 10, {"x": 0}).total == 10


def test_limit():
    with pytest.raises(ValueError, match="limit of 12"):
        Ausgleich(method=SainteLague(), limit=12).apportion(WEIGHTS, 10, {"a": 9})
    with pytest.raises(ValidationError):
        Ausgleich(method=SainteLague(), limit=-1)


def test_bad_minimum():
    with pytest.raises(TypeError, match="non-negative int"):
        Ausgleich(method=SainteLague()).apportion(WEIGHTS, 10, {"a": 1.5})
