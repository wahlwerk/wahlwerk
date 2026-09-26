import pytest
from pydantic import ValidationError

from wahlwerk.state import Caucus


def test_minimal_caucus():
    caucus = Caucus(id="cdu-csu")
    assert caucus.id == "cdu-csu"
    assert caucus.mandates == frozenset()
    assert caucus.size == 0


def test_mandates_become_frozenset():
    caucus = Caucus(id="spd", mandates=["spd.001", "spd.002", "spd.002"])
    assert caucus.mandates == frozenset({"spd.001", "spd.002"})
    assert caucus.size == 2


@pytest.mark.parametrize("bad", ["SPD.001", "spd 1", "", 0])
def test_mandates_must_be_mandate_ids(bad):
    with pytest.raises(ValidationError):
        Caucus(id="spd", mandates={bad})


def test_id_is_required():
    with pytest.raises(ValidationError):
        Caucus(mandates={"spd.001"})


@pytest.mark.parametrize("bad", ["CDU", "cdu.csu", "cdu/csu", "-cdu", ""])
def test_id_must_be_slug(bad):
    with pytest.raises(ValidationError):
        Caucus(id=bad)


@pytest.mark.parametrize("field", ["name", "short_name"])
def test_caucus_has_no_names(field):
    """Names belong to parties, which stay separate."""
    with pytest.raises(ValidationError):
        Caucus(id="spd", **{field: "SPD"})


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        Caucus(id="spd", parties=("spd",))
