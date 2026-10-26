import pytest
from pydantic import ValidationError

from wahlwerk.vote.popular import Lot

WK = {"section": "erststimme", "unit": "de.st.wk.017"}


def test_a_lot_records_its_draw():
    lot = Lot(**WK, candidates={"a", "b"}, winners={"b"}, source="Niederschrift")
    assert lot.seats == 1
    assert lot.decides("erststimme", "de.st.wk.017", frozenset({"a", "b"}), 1)


@pytest.mark.parametrize(
    ("section", "unit", "candidates", "seats"),
    [
        ("zweitstimme", "de.st.wk.017", {"a", "b"}, 1),
        ("erststimme", "de.st.wk.018", {"a", "b"}, 1),
        ("erststimme", None, {"a", "b"}, 1),
        ("erststimme", "de.st.wk.017", {"a", "b", "c"}, 1),
        ("erststimme", "de.st.wk.017", {"a", "b"}, 2),
    ],
)
def test_a_lot_decides_only_the_tie_it_was_drawn_for(section, unit, candidates, seats):
    lot = Lot(**WK, candidates={"a", "b"}, winners={"b"})
    assert not lot.decides(section, unit, frozenset(candidates), seats)


def test_a_lot_without_unit_spans_none():
    lot = Lot(section="zweitstimme", candidates={"a", "b", "c"}, winners={"a", "c"})
    assert lot.unit is None and lot.seats == 2


@pytest.mark.parametrize(
    ("winners", "match"),
    [(set(), "names no winner"), ({"c"}, "not among the candidates"), ({"a", "b"}, "is no draw")],
)
def test_a_lot_must_be_a_draw(winners, match):
    with pytest.raises(ValidationError, match=match):
        Lot(**WK, candidates={"a", "b"}, winners=winners)
