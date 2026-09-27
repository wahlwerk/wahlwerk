import pytest
from pydantic import ValidationError

from wahlwerk.vote.popular import Hierarchy, HierarchyUnit, Tally, TallyRow

# Halle spans two Wahlkreise here, as it spans four in reality.
HALLE_1 = "de.st.wk.035.gem.15002000.wbz.000001"
HALLE_2 = "de.st.wk.036.gem.15002000.wbz.000002"
LEUNA = "de.st.wk.033.gem.15088205.wbz.000001"

UNITS = (
    HierarchyUnit(unit="de.st", level="land"),
    HierarchyUnit(unit="de.st.krs.15002", level="kreis", parent="de.st"),
    HierarchyUnit(unit="de.st.krs.15088", level="kreis", parent="de.st"),
    HierarchyUnit(unit="de.st.gem.15002000", level="gemeinde", parent="de.st.krs.15002"),
    HierarchyUnit(unit="de.st.gem.15088205", level="gemeinde", parent="de.st.krs.15088"),
    HierarchyUnit(unit=HALLE_1, level="wahlbezirk", parent="de.st.gem.15002000"),
    HierarchyUnit(unit=HALLE_2, level="wahlbezirk", parent="de.st.gem.15002000"),
    HierarchyUnit(unit=LEUNA, level="briefwahlbezirk", parent="de.st.gem.15088205"),
)
ADMIN = Hierarchy(name="administrative", levels=("land", "kreis", "gemeinde"), units=UNITS)


def hierarchy(*units):
    return Hierarchy(name="administrative", levels=("land", "kreis", "gemeinde"), units=units)


def test_units_at_gemeinde_joins_a_split_gemeinde():
    at = ADMIN.units_at("gemeinde")
    assert at[HALLE_1] == at[HALLE_2] == "de.st.gem.15002000"
    assert at[LEUNA] == "de.st.gem.15088205"
    assert at["de.st.gem.15002000"] == "de.st.gem.15002000"
    assert "de.st.krs.15002" not in at


def test_units_at_kreis_and_land():
    assert ADMIN.units_at("kreis")[HALLE_1] == "de.st.krs.15002"
    assert set(ADMIN.units_at("land").values()) == {"de.st"}
    assert len(ADMIN.units_at("land")) == len(UNITS)


def test_units_at_unknown_level():
    with pytest.raises(ValueError, match="no level 'wahlkreis'"):
        ADMIN.units_at("wahlkreis")


def test_unit_listed_twice():
    with pytest.raises(ValidationError, match="more than once"):
        hierarchy(*UNITS, UNITS[-1])


def test_level_listed_twice():
    with pytest.raises(ValidationError, match="lists a level more than once"):
        Hierarchy(name="administrative", levels=("land", "land"))


def test_broadest_unit_has_no_parent():
    with pytest.raises(ValidationError, match="broadest level"):
        hierarchy(HierarchyUnit(unit="de.st", level="land", parent="de"))


def test_missing_parent():
    with pytest.raises(ValidationError, match="has no parent, expected one at 'land'"):
        hierarchy(UNITS[0], HierarchyUnit(unit="de.st.krs.15002", level="kreis"))


def test_parent_not_in_hierarchy():
    with pytest.raises(ValidationError, match="not a unit of the hierarchy"):
        hierarchy(UNITS[0], HierarchyUnit(unit="de.st.krs.15002", level="kreis", parent="de.x"))


def test_parent_at_wrong_level():
    # A Wahlbezirk must lie in a Gemeinde, not directly in a Kreis.
    wrong = HierarchyUnit(unit=HALLE_1, level="wahlbezirk", parent="de.st.krs.15002")
    with pytest.raises(ValidationError, match="expected a unit at 'gemeinde'"):
        hierarchy(*UNITS[:3], wrong)


# ===========================================================
# Tally.sum_to along a hierarchy
# ===========================================================
def row(unit, count, level="wahlbezirk", party="afd"):
    return TallyRow(unit=unit, level=level, section="zweitstimme", party=party, count=count)


TALLY = Tally(
    rows=(row(HALLE_1, 10), row(HALLE_2, 20), row(LEUNA, 5, level="briefwahlbezirk"))
)


def test_sum_to_gemeinde_along_hierarchy():
    gem = TALLY.sum_to("gemeinde", hierarchy=ADMIN)
    assert gem.sum_by("unit") == {"de.st.gem.15002000": 30, "de.st.gem.15088205": 5}
    assert {r.level for r in gem.rows} == {"gemeinde"}
    assert gem.levels == ()


def test_sum_to_along_hierarchy_can_go_on():
    kreis = TALLY.sum_to("gemeinde", hierarchy=ADMIN).sum_to("kreis", hierarchy=ADMIN)
    assert kreis.sum_by("unit") == {"de.st.krs.15002": 30, "de.st.krs.15088": 5}


def test_sum_to_rejects_depth_with_hierarchy():
    with pytest.raises(ValueError, match="not both"):
        TALLY.sum_to("gemeinde", 6, hierarchy=ADMIN)


def test_sum_to_rejects_unit_outside_hierarchy():
    tally = Tally(rows=(row("de.st.wk.001.gem.15081026.wbz.000001", 1),))
    with pytest.raises(ValueError, match="places unit .* in no 'gemeinde'"):
        tally.sum_to("gemeinde", hierarchy=ADMIN)
