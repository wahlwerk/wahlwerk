import pytest
from pydantic import TypeAdapter, ValidationError

from wahlwerk.ids import BodyId, PartyId

party_id = TypeAdapter(PartyId)
body_id = TypeAdapter(BodyId)


@pytest.mark.parametrize("good", ["cdu", "gruene", "team-todenhoefer", "b90_gruene"])
def test_party_id_accepts_slugs(good):
    assert party_id.validate_python(good) == good


@pytest.mark.parametrize("bad", ["CDU", "de.bund.cdu", "not a slug!", "-cdu", ""])
def test_party_id_rejects_non_slugs(bad):
    with pytest.raises(ValidationError):
        party_id.validate_python(bad)


@pytest.mark.parametrize("bad", ["de.bund.Bundestag", "de..bund", ".de", ""])
def test_body_id_rejects_malformed_keys(bad):
    with pytest.raises(ValidationError):
        body_id.validate_python(bad)
