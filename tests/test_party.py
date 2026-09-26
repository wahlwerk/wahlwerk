import pytest
from pydantic import ValidationError

from wahlwerk.party import Party


def test_party():
    party = Party(id="spd", name="Sozialdemokratische Partei Deutschlands", short_name="SPD")
    assert party.id == "spd"
    assert party.short_name == "SPD"


def test_short_name_is_optional():
    assert Party(id="ssw", name="Südschleswigscher Wählerverband").short_name is None


@pytest.mark.parametrize("missing", ["id", "name"])
def test_id_and_name_are_required(missing):
    fields = {"id": "spd", "name": "SPD"}
    del fields[missing]
    with pytest.raises(ValidationError):
        Party(**fields)


def test_id_must_be_slug():
    with pytest.raises(ValidationError):
        Party(id="SPD", name="SPD")


@pytest.mark.parametrize("field", ["name", "short_name"])
def test_names_cannot_be_empty(field):
    fields = {"id": "spd", "name": "SPD", field: ""}
    with pytest.raises(ValidationError):
        Party(**fields)
