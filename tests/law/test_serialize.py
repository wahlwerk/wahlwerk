import json

import pytest

from wahlwerk.law.de.st.lwg import LWG_2021
from wahlwerk.law.edit import replace
from wahlwerk.law.registry import LAWS
from wahlwerk.law.serialize import from_data, law_from_json, law_to_json, to_data
from wahlwerk.process.allocation.eligibility import SetChamberSize


@pytest.mark.parametrize("law", list(LAWS), ids=lambda law: law.id)
def test_every_registered_law_round_trips(law):
    assert law_from_json(law_to_json(law)) == law


def test_a_revised_law_round_trips():
    law = LWG_2021.revise(id="example.st.lwg.101", protocol=replace(LWG_2021.protocol, SetChamberSize, seats=101))
    assert law_from_json(law_to_json(law)) == law


def test_models_carry_their_type_and_exact_values():
    data = json.loads(law_to_json(LWG_2021))
    assert data["schema"] == 1
    threshold = data["law"]["protocol"][2]["steps"][1]["threshold"]  # inside QUALIFY
    assert threshold == {
        "type": "wahlwerk.apportionment.threshold.RelativeThreshold",
        "share": "1/20",
        "accept_equal": True,
    }


def test_only_wahlwerk_models_are_read():
    with pytest.raises(ValueError, match="not a wahlwerk model"):
        from_data({"type": "os.system"})
    with pytest.raises(TypeError, match="not a wahlwerk model"):
        from_data({"type": "wahlwerk.law.serialize.json"})
    with pytest.raises(ValueError, match="no model"):
        from_data({"type": "wahlwerk.law.base.Nothing"})


def test_a_file_must_hold_a_law_of_a_known_schema():
    with pytest.raises(ValueError, match="schema"):
        law_from_json(json.dumps({"schema": 99, "law": {}}))
    with pytest.raises(TypeError, match="not a Law"):
        law_from_json(json.dumps({"schema": 1, "law": to_data(LWG_2021.protocol[0])}))
