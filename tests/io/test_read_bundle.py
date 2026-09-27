import logging
from datetime import date

import pytest

from wahlwerk.io import read_bundle, resolve_election_dir
from wahlwerk.vote.popular import TallyKind

SHA = "a" * 64

ELECTION = f"""\
schema = 1

[source]
publisher = "Statistisches Landesamt Sachsen-Anhalt"
title = "Landtagswahl 2026"
url = "https://example.org/ergebnisse.xlsx"
licence = "dl-de/by-2-0"
attribution = "Statistisches Landesamt Sachsen-Anhalt, Halle (Saale), 2026"
retrieved = 2026-09-26
sha256 = "{SHA}"
"""

HEADER = "unit,level,kind,section,channel,party,candidate,option,count\n"

TALLY = (
    HEADER
    + "de.st.wk.001,wahlkreis,eligible,,,,,,590\n"
    + "de.st.wk.001,wahlkreis,voters,,urne,,,,433\n"
    + "de.st.wk.001,wahlkreis,invalid,zweitstimme,urne,,,,4\n"
    + "de.st.wk.001,wahlkreis,votes,zweitstimme,urne,cdu,,,61\n"
    + "de.st.wk.001,wahlkreis,votes,erststimme,brief,,de.st.wk.001.mueller,,7\n"
)


def write(tmp_path, election=ELECTION, tally=TALLY):
    (tmp_path / "election.toml").write_text(election, encoding="utf-8")
    (tmp_path / "tally.csv").write_text(tally, encoding="utf-8")
    return tmp_path


def test_reads_source(tmp_path):
    vote = read_bundle(write(tmp_path))
    assert vote.source.publisher == "Statistisches Landesamt Sachsen-Anhalt"
    assert vote.source.licence == "dl-de/by-2-0"
    assert vote.source.retrieved == date(2026, 9, 26)
    assert vote.source.sha256 == SHA


def test_reads_rows_in_file_order(tmp_path):
    eligible, voters, invalid, party, candidate = read_bundle(write(tmp_path)).tally.rows
    assert eligible.kind is TallyKind.ELIGIBLE
    assert eligible.channel is None
    assert voters.channel == "urne"
    assert invalid.kind is TallyKind.INVALID
    assert invalid.section == "zweitstimme"
    assert party.party == "cdu"
    assert party.count == 61
    assert candidate.party is None
    assert candidate.candidate == "de.st.wk.001.mueller"


def test_blank_cells_are_none_not_empty_strings(tmp_path):
    eligible = read_bundle(write(tmp_path)).tally.rows[0]
    assert eligible.section is None
    assert eligible.party is None
    assert eligible.candidate is None
    assert eligible.option is None


def test_accepts_str_path(tmp_path):
    assert len(read_bundle(str(write(tmp_path))).tally) == 5


def test_header_only_gives_an_empty_tally(tmp_path):
    assert read_bundle(write(tmp_path, tally=HEADER)).tally.rows == ()


@pytest.mark.parametrize(
    ("old", "new"), [("schema = 1\n", ""), ("schema = 1", "schema = 3")]
)
def test_unsupported_schema_is_rejected(tmp_path, old, new):
    with pytest.raises(ValueError, match=r"election\.toml: schema .* is not supported"):
        read_bundle(write(tmp_path, election=ELECTION.replace(old, new)))


def test_unknown_top_level_key_is_rejected(tmp_path):
    election = ELECTION.replace("schema = 1\n", 'schema = 1\nyear = 2026\n')
    with pytest.raises(ValueError, match=r"election\.toml: unknown keys \['year'\]"):
        read_bundle(write(tmp_path, election=election))


def test_missing_source_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"expected a \[source\] table"):
        read_bundle(write(tmp_path, election="schema = 1\n"))


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('licence = "dl-de/by-2-0"\n', ""),
        ('licence = "dl-de/by-2-0"', 'license = "dl-de/by-2-0"'),
        (SHA, "not-a-hash"),
        ("https://example.org/ergebnisse.xlsx", "example.org"),
        ("retrieved = 2026-09-26", 'retrieved = "yesterday"'),
    ],
)
def test_invalid_source_is_rejected(tmp_path, old, new):
    with pytest.raises(ValueError, match=r"election\.toml: source"):
        read_bundle(write(tmp_path, election=ELECTION.replace(old, new)))


def test_malformed_toml_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"election\.toml"):
        read_bundle(write(tmp_path, election="schema = \n"))


@pytest.mark.parametrize(
    "header",
    [
        "unit,level,section,party,candidate,count\n",
        "unit,level,kind,section,channel,party,candidate,option,count,note\n",
        "Gebiet,level,kind,section,channel,party,candidate,option,count\n",
        "",
    ],
)
def test_wrong_header_is_rejected(tmp_path, header):
    with pytest.raises(ValueError, match=r"tally\.csv: header"):
        read_bundle(write(tmp_path, tally=header))


def test_short_row_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"tally\.csv: line 2: 8 cells, expected 9"):
        read_bundle(write(tmp_path, tally=HEADER + "de.st.wk.001,wahlkreis,votes,,,,,1\n"))


def test_blank_kind_is_rejected(tmp_path):
    row = "de.st.wk.001,wahlkreis,,zweitstimme,,cdu,,,1\n"
    with pytest.raises(ValueError, match=r"tally\.csv: line 2: kind is blank"):
        read_bundle(write(tmp_path, tally=HEADER + row))


@pytest.mark.parametrize(
    "row",
    [
        "de.st.wk.001,wahlkreis,votes,zweitstimme,,,,,1\n",  # no recipient
        "de.st.wk.001,wahlkreis,votes,zweitstimme,,cdu,,,-1\n",  # negative
        "de.st.wk.001,wahlkreis,votes,zweitstimme,,cdu,,,1.5\n",  # not an integer
        "de.st.wk.001,wahlkreis,votes,zweitstimme,,CDU,,,1\n",  # not a slug
        "de.st.wk.001,wahlkreis,ballots,zweitstimme,,cdu,,,1\n",  # unknown kind
        "de.st.wk.001,wahlkreis,votes,zweitstimme,,cdu,,,\n",  # blank count
        "de.st.wk.001,wahlkreis,eligible,zweitstimme,,,,,1\n",  # people with a section
    ],
)
def test_invalid_row_names_file_and_line(tmp_path, row):
    with pytest.raises(ValueError, match=r"tally\.csv: line 3"):
        read_bundle(write(tmp_path, tally=HEADER + TALLY.splitlines(keepends=True)[1] + row))


def test_duplicate_row_names_file(tmp_path):
    row = TALLY.splitlines(keepends=True)[4]
    with pytest.raises(ValueError, match=r"(?s)tally\.csv: .*more than once"):
        read_bundle(write(tmp_path, tally=TALLY + row))


def test_schema_is_not_part_of_the_model(tmp_path):
    assert "schema_version" not in type(read_bundle(write(tmp_path))).model_fields


@pytest.mark.parametrize("name", ["election.toml", "tally.csv"])
def test_missing_file_is_rejected(tmp_path, name):
    write(tmp_path)
    (tmp_path / name).unlink()
    with pytest.raises(ValueError, match=rf"{name}: missing from the bundle"):
        read_bundle(tmp_path)


def test_missing_directory_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"election\.toml: missing from the bundle"):
        read_bundle(tmp_path / "nope")


def test_logs_what_was_read(tmp_path, caplog):
    path = write(tmp_path)
    with caplog.at_level(logging.INFO, logger="wahlwerk"):
        read_bundle(path)
    assert f"{path}: read 5 tally rows" in caplog.text


def test_custom_file_names(tmp_path):
    (tmp_path / "lt2026.toml").write_text(ELECTION, encoding="utf-8")
    (tmp_path / "lt2026.csv").write_text(TALLY, encoding="utf-8")
    vote = read_bundle(tmp_path, "lt2026.toml", "lt2026.csv")
    assert len(vote.tally) == 5


def test_custom_file_name_missing_is_named(tmp_path):
    write(tmp_path)
    with pytest.raises(ValueError, match=r"other\.csv: missing from the bundle"):
        read_bundle(tmp_path, tally_file_name="other.csv")


def test_resolve_election_dir_follows_the_key(tmp_path):
    target = tmp_path / "elections" / "de" / "landtag" / "st" / "2026"
    target.mkdir(parents=True)
    assert resolve_election_dir(tmp_path, "de.landtag.st.2026") == target
    assert resolve_election_dir(str(tmp_path), "de.landtag.st.2026") == target


@pytest.mark.parametrize("key", ["de/landtag", "..", "de..st", "De.st", "", "de.st/../x"])
def test_resolve_election_dir_rejects_malformed_key(tmp_path, key):
    with pytest.raises(ValueError, match="is not a dotted key"):
        resolve_election_dir(tmp_path, key)


def test_resolve_election_dir_rejects_non_string_key(tmp_path):
    with pytest.raises(TypeError, match="key must be a str"):
        resolve_election_dir(tmp_path, 2026)


def test_resolve_election_dir_rejects_unknown_key(tmp_path):
    with pytest.raises(ValueError, match=r"no bundle for key 'de\.landtag\.st\.2031'"):
        resolve_election_dir(tmp_path, "de.landtag.st.2031")


# ===========================================================
# Schema 2: [levels]
# ===========================================================
LEVELS = "\n[levels]\nland = 2\nwahlkreis = 4\n"
ELECTION_2 = ELECTION.replace("schema = 1", "schema = 2") + LEVELS


def test_schema_2_reads_levels_in_file_order(tmp_path):
    levels = read_bundle(write(tmp_path, election=ELECTION_2)).tally.levels
    assert [(level.name, level.depth) for level in levels] == [("land", 2), ("wahlkreis", 4)]


def test_schema_2_levels_let_sum_to_take_the_level_alone(tmp_path):
    tally = read_bundle(write(tmp_path, election=ELECTION_2)).tally
    land = tally.filter(kind="votes").sum_to("land")
    assert {row.unit for row in land.rows} == {"de.st"}


def test_schema_1_records_no_levels(tmp_path):
    assert read_bundle(write(tmp_path)).tally.levels == ()


def test_schema_1_with_levels_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"unknown keys \['levels'\]"):
        read_bundle(write(tmp_path, election=ELECTION + LEVELS))


def test_schema_2_without_levels_is_rejected(tmp_path):
    election = ELECTION.replace("schema = 1", "schema = 2")
    with pytest.raises(ValueError, match=r"election\.toml: expected a \[levels\] table"):
        read_bundle(write(tmp_path, election=election))


@pytest.mark.parametrize("depth", ["0", '"4"', "true", "4.0"])
def test_schema_2_bad_depth_is_rejected(tmp_path, depth):
    election = ELECTION_2.replace("wahlkreis = 4", f"wahlkreis = {depth}")
    with pytest.raises(ValueError, match=r"election\.toml: levels:"):
        read_bundle(write(tmp_path, election=election))


def test_schema_2_row_at_unlisted_level_names_file(tmp_path):
    election = ELECTION_2.replace("wahlkreis = 4", "gemeinde = 6")
    with pytest.raises(ValueError, match=r"(?s)tally\.csv: .*level 'wahlkreis', not one of"):
        read_bundle(write(tmp_path, election=election))


def test_schema_2_row_at_wrong_depth_names_file(tmp_path):
    election = ELECTION_2.replace("wahlkreis = 4", "wahlkreis = 5")
    with pytest.raises(ValueError, match=r"(?s)tally\.csv: .*has 4 segments, but level"):
        read_bundle(write(tmp_path, election=election))


# ===========================================================
# Schema 2: [hierarchies]
# ===========================================================
HIERARCHY_TOML = '\n[hierarchies.administrative]\nlevels = ["land", "kreis"]\n'
ADMINISTRATIVE = (
    "unit,level,parent\n"
    "de.st,land,\n"
    "de.st.krs.15081,kreis,de.st\n"
    "de.st.wk.001,wahlkreis,de.st.krs.15081\n"
)


def write_2(tmp_path, hierarchy=ADMINISTRATIVE, toml=HIERARCHY_TOML):
    write(tmp_path, election=ELECTION_2 + toml)
    if hierarchy is not None:
        (tmp_path / "administrative.csv").write_text(hierarchy, encoding="utf-8")
    return tmp_path


def test_reads_hierarchy(tmp_path):
    vote = read_bundle(write_2(tmp_path))
    admin = vote.hierarchy("administrative")
    assert admin.levels == ("land", "kreis")
    assert (admin.units[0].unit, admin.units[0].parent) == ("de.st", None)
    kreis = vote.tally.filter(kind="votes").sum_to("kreis", hierarchy=admin)
    assert {row.unit for row in kreis.rows} == {"de.st.krs.15081"}


def test_hierarchies_are_optional(tmp_path):
    assert read_bundle(write(tmp_path, election=ELECTION_2)).hierarchies == ()


def test_schema_1_with_hierarchies_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"unknown keys \['hierarchies'\]"):
        read_bundle(write(tmp_path, election=ELECTION + HIERARCHY_TOML))


def test_missing_hierarchy_file_is_named(tmp_path):
    with pytest.raises(ValueError, match=r"administrative\.csv: missing from the bundle"):
        read_bundle(write_2(tmp_path, hierarchy=None))


@pytest.mark.parametrize(
    ("toml", "message"),
    [
        ('\n[hierarchies.Admin]\nlevels = ["land"]\n', "is not a slug"),
        ('\n[hierarchies.administrative]\nlevels = "land"\n', "expected levels"),
        ('\n[hierarchies.administrative]\nlevels = ["land"]\nfile = "x.csv"\n', "unknown keys"),
        ("\n[hierarchies]\nadministrative = 1\n", "expected a table"),
    ],
)
def test_bad_hierarchy_table_is_rejected(tmp_path, toml, message):
    with pytest.raises(ValueError, match=rf"election\.toml: hierarchies.*{message}"):
        read_bundle(write_2(tmp_path, toml=toml))


def test_hierarchy_bad_header_is_rejected(tmp_path):
    with pytest.raises(ValueError, match=r"administrative\.csv: header"):
        read_bundle(write_2(tmp_path, hierarchy=ADMINISTRATIVE.replace("parent", "in")))


def test_hierarchy_not_a_tree_names_file(tmp_path):
    broken = ADMINISTRATIVE.replace("de.st.krs.15081,kreis,de.st", "de.st.krs.15081,kreis,")
    with pytest.raises(ValueError, match=r"(?s)administrative\.csv: .*has no parent"):
        read_bundle(write_2(tmp_path, hierarchy=broken))


def test_hierarchy_must_cover_the_tally(tmp_path):
    short = "unit,level,parent\nde.st,land,\nde.st.krs.15081,kreis,de.st\n"
    with pytest.raises(ValueError, match=r"(?s)does not cover 1 counted units"):
        read_bundle(write_2(tmp_path, hierarchy=short))
