"""The law file's JSON Schema: every type defined, every law valid, a broken file rejected."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.apportionment.threshold import Threshold
from wahlwerk.law.registry import LAWS
from wahlwerk.law.schema import DIALECT, law_schema, types_of
from wahlwerk.law.serialize import SCHEMA, law_to_json
from wahlwerk.process.allocation.base import AllocationStep

jsonschema = pytest.importorskip("jsonschema")

BASES = (AllocationStep, ApportionmentMethod, Threshold)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return law_schema()


def _validator(schema: dict[str, Any]) -> Any:
    return jsonschema.Draft202012Validator(schema)


def _refs(node: Any) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if "$ref" in node else []
        return found + [ref for value in node.values() for ref in _refs(value)]
    if isinstance(node, list):
        return [ref for item in node for ref in _refs(item)]
    return []


def _law_data(law_id: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(law_to_json(LAWS[law_id]))
    return data


def test_the_schema_is_a_valid_2020_12_schema(schema: dict[str, Any]) -> None:
    assert schema["$schema"] == DIALECT
    jsonschema.Draft202012Validator.check_schema(schema)


def test_every_ref_resolves(schema: dict[str, Any]) -> None:
    refs = set(_refs(schema))
    assert refs
    for ref in refs:
        assert ref.startswith("#/$defs/")
        assert ref.removeprefix("#/$defs/") in schema["$defs"]


def test_the_step_types_are_every_concrete_step() -> None:
    names = {cls.__name__ for cls in types_of(AllocationStep)}
    assert {"SumVotes", "ApportionSeats", "RaiseForAusgleich", "FormChamber"} <= names
    assert "AllocationStep" not in names
    assert "DivisorMethod" not in {cls.__name__ for cls in types_of(ApportionmentMethod)}


@pytest.mark.parametrize("base", BASES, ids=lambda base: base.__name__)
def test_a_base_is_one_of_its_concrete_types(schema: dict[str, Any], base: type) -> None:
    definition = schema["$defs"][base.__name__]
    assert [item["$ref"] for item in definition["oneOf"]] == [
        f"#/$defs/{cls.__name__}" for cls in types_of(base)
    ]


@pytest.mark.parametrize("base", BASES, ids=lambda base: base.__name__)
def test_every_type_is_tagged_as_the_serializer_writes_it(
    schema: dict[str, Any], base: type
) -> None:
    for cls in types_of(base):
        definition = schema["$defs"][cls.__name__]
        assert definition["properties"]["type"]["const"] == f"{cls.__module__}.{cls.__qualname__}"
        assert definition["required"][0] == "type"
        assert definition["additionalProperties"] is False


def test_fields_keep_their_descriptions(schema: dict[str, Any]) -> None:
    house = schema["$defs"]["SetHouse"]["properties"]["seats"]
    assert house["description"]


@pytest.mark.parametrize("law_id", sorted(law.id for law in LAWS), ids=str)
def test_every_law_in_the_registry_is_valid(schema: dict[str, Any], law_id: str) -> None:
    _validator(schema).validate(_law_data(law_id))


def _errors(schema: dict[str, Any], data: dict[str, Any]) -> list[Any]:
    return list(_validator(schema).iter_errors(data))


def test_an_unknown_step_type_is_rejected(schema: dict[str, Any]) -> None:
    data = _law_data("de.st.lwg.2021")
    data["law"]["protocol"][0]["type"] = "wahlwerk.process.allocation.count.CountVotes"
    assert _errors(schema, data)


def test_a_misspelled_field_is_rejected(schema: dict[str, Any]) -> None:
    data = _law_data("de.st.lwg.2021")
    data["law"]["protocol"][0]["levle"] = "land"
    assert _errors(schema, data)


def test_a_share_is_a_fraction_string(schema: dict[str, Any]) -> None:
    data = _law_data("de.st.lwg.2021")
    threshold = next(
        step["threshold"] for step in data["law"]["protocol"] if "threshold" in step
    )
    assert threshold["share"] == "1/20"
    threshold["share"] = 0.05
    assert _errors(schema, data)


def test_another_file_format_is_rejected(schema: dict[str, Any]) -> None:
    data = _law_data("de.st.lwg.2021")
    other = copy.deepcopy(data)
    other["schema"] = SCHEMA + 1
    assert _errors(schema, other)
