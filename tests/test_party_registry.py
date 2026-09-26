import pytest
from pydantic import ValidationError

from wahlwerk.party import Party, PartyRegistry

CDU = Party(id="cdu", name="Christlich Demokratische Union Deutschlands", short_name="CDU")
SPD = Party(id="spd", name="Sozialdemokratische Partei Deutschlands", short_name="SPD")


@pytest.fixture
def registry():
    return PartyRegistry(parties=(CDU, SPD))


def test_lookup_by_id(registry):
    assert registry["cdu"] is CDU
    assert registry["spd"] is SPD


def test_unknown_id_raises_with_name(registry):
    with pytest.raises(KeyError, match="bsw"):
        registry["bsw"]


def test_get_returns_party_or_default(registry):
    assert registry.get("cdu") is CDU
    assert registry.get("bsw") is None
    assert registry.get("bsw", SPD) is SPD


def test_from_json(tmp_path):
    path = tmp_path / "parties.json"
    path.write_text(
        '{"schema": 1, "name": "de.test", "parties": {"cdu": {"name": "CDU"}}}',
        encoding="utf-8",
    )
    registry = PartyRegistry.from_json(path)
    assert registry["cdu"].name == "CDU"
    assert PartyRegistry.from_json(str(path)) == registry


def test_contains(registry):
    assert "cdu" in registry
    assert "bsw" not in registry


def test_len_and_iteration_keep_order(registry):
    assert len(registry) == 2
    assert list(registry) == [CDU, SPD]


def test_empty_registry():
    registry = PartyRegistry()
    assert len(registry) == 0
    assert "cdu" not in registry


def test_duplicate_id_is_rejected():
    other_cdu = Party(id="cdu", name="Something else")
    with pytest.raises(ValidationError, match="'cdu' is registered twice"):
        PartyRegistry(parties=(CDU, other_cdu))


def test_lookup_cache_does_not_leak_into_identity(registry):
    """Looking up caches the index; that must not change equality, hash or dump."""
    fresh = PartyRegistry(parties=(CDU, SPD))
    registry["cdu"]
    assert registry == fresh
    assert hash(registry) == hash(fresh)
    assert "_by_id" not in registry.model_dump()
