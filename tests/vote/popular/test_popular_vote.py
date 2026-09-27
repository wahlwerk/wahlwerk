import inspect
from datetime import date

import pytest
from pydantic import ValidationError

from wahlwerk.io import bundle as io_bundle
from wahlwerk.io import read_bundle
from wahlwerk.vote.popular import (
    Hierarchy,
    HierarchyUnit,
    PopularVote,
    Source,
    Tally,
    TallyRow,
)

ELECTION = """\
schema = 1

[source]
publisher = "Statistisches Landesamt Sachsen-Anhalt"
title = "Landtagswahl 2026"
url = "https://example.org/ergebnisse.xlsx"
licence = "dl-de/by-2-0"
attribution = "Statistisches Landesamt Sachsen-Anhalt, Halle (Saale), 2026"
retrieved = 2026-09-26
sha256 = "{sha}"
""".format(sha="a" * 64)

TALLY = (
    "unit,level,kind,section,channel,party,candidate,option,count\n"
    "de.st.wk.001,wahlkreis,eligible,,,,,,590\n"
    "de.st.wk.001,wahlkreis,votes,zweitstimme,,cdu,,,61\n"
)


def test_from_dir_with_default_file_names(tmp_path):
    (tmp_path / "election.toml").write_text(ELECTION, encoding="utf-8")
    (tmp_path / "tally.csv").write_text(TALLY, encoding="utf-8")
    vote = PopularVote.from_dir(tmp_path)
    assert vote == read_bundle(tmp_path)
    assert len(vote.tally) == 2


def test_from_dir_with_custom_file_names(tmp_path):
    (tmp_path / "lt2026.toml").write_text(ELECTION, encoding="utf-8")
    (tmp_path / "lt2026.csv").write_text(TALLY, encoding="utf-8")
    vote = PopularVote.from_dir(str(tmp_path), "lt2026.toml", "lt2026.csv")
    assert vote.source.licence == "dl-de/by-2-0"
    assert len(vote.tally) == 2


def test_from_dir_defaults_match_the_reader():
    """from_dir repeats the reader's default names; they must not drift apart."""
    params = inspect.signature(PopularVote.from_dir).parameters
    assert params["election_file_name"].default == io_bundle.ELECTION_FILE
    assert params["tally_file_name"].default == io_bundle.TALLY_FILE


def test_from_key(tmp_path):
    bundle_dir = tmp_path / "elections" / "de" / "landtag" / "st" / "2026"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "election.toml").write_text(ELECTION, encoding="utf-8")
    (bundle_dir / "tally.csv").write_text(TALLY, encoding="utf-8")
    vote = PopularVote.from_key("de.landtag.st.2026", tmp_path)
    assert vote == PopularVote.from_dir(bundle_dir)


def test_from_key_with_custom_file_names(tmp_path):
    bundle_dir = tmp_path / "elections" / "de" / "landtag" / "st" / "2026"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "lt2026.toml").write_text(ELECTION, encoding="utf-8")
    (bundle_dir / "lt2026.csv").write_text(TALLY, encoding="utf-8")
    vote = PopularVote.from_key("de.landtag.st.2026", str(tmp_path), "lt2026.toml", "lt2026.csv")
    assert len(vote.tally) == 2


def test_from_key_defaults_match_the_reader():
    params = inspect.signature(PopularVote.from_key).parameters
    assert params["election_file_name"].default == io_bundle.ELECTION_FILE
    assert params["tally_file_name"].default == io_bundle.TALLY_FILE


# ===========================================================
# Hierarchies
# ===========================================================
def _vote(*hierarchies):
    source = Source(
        publisher="p",
        title="t",
        url="https://example.org/x",
        licence="l",
        attribution="a",
        retrieved=date(2026, 9, 26),
        sha256="a" * 64,
    )
    row = TallyRow(unit="de.st.wk.001", level="wahlkreis", kind="eligible", count=1)
    tally = Tally(rows=(row,))
    return PopularVote(source=source, tally=tally, hierarchies=hierarchies)


def _admin(name="administrative", covers=True):
    units = [HierarchyUnit(unit="de.st", level="land")]
    if covers:
        units.append(HierarchyUnit(unit="de.st.wk.001", level="wahlkreis", parent="de.st"))
    return Hierarchy(name=name, levels=("land",), units=tuple(units))


def test_hierarchy_by_name():
    admin = _admin()
    assert _vote(admin).hierarchy("administrative") is admin


def test_unknown_hierarchy_raises_key_error():
    with pytest.raises(KeyError, match="no hierarchy 'church'"):
        _vote(_admin()).hierarchy("church")


def test_hierarchy_must_cover_every_counted_unit():
    with pytest.raises(ValidationError, match="does not cover 1 counted units"):
        _vote(_admin(covers=False))


def test_hierarchy_names_are_unique():
    with pytest.raises(ValidationError, match="more than once"):
        _vote(_admin(), _admin())
