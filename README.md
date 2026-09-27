# wahlwerk

Electoral and parliamentary systems as **rules-as-code**: a deterministic engine
parameterised by an electoral law, so that small changes to the law can be evaluated
against real historical votes.

Scope covers all legislative levels, plus the derived bodies.

## Approach

The long-term aim is to represent most systems of government: parliamentary,
presidential, semi-presidential, directorial, and the mixtures in between. The engine
gets there by composition, not by classification.

- **Small, general building blocks.** Each block models one kind of standing thing and
  nothing else, knows nothing about the system it sits in, and is reused unchanged in
  every system that has it. A system is a composition of blocks, never a subclass.
- **State, protocols, events and processes, kept apart.**
  - *State* is inert: what exists at a point in time. It is never edited, only
    replaced.
  - A *protocol* is data: an ordered tuple of *steps*, each a small frozen model that
    says one thing (how something is filled, who can end it, which parties form one
    caucus). The constitution and electoral law in force are protocols, referenced by
    the date they apply to, so an election is evaluated under the law of its day.
  - An *event* is a dated fact from history: an election with its votes, a member
    leaving a caucus. Events are inputs, never logic.
  - A *process* is the only way state changes: it applies a protocol, step by step in
    order, and returns new state. An *internal* process changes one unit
    (`chamber.form_caucuses(protocol)`); an *external* process spans several units or
    forms a new one (forming a chamber after an election).
  - A counterfactual is the same event under a different protocol.
- **Steps are objects, not functions.** A step can be printed, compared, hashed and
  validated when it is written, and a protocol can be stored as part of a law. Two
  protocols that differ in one step show exactly that difference.
- **Folders by role, dependencies one way.** Foundation (`model`, `ids`, `log`) <-
  entities (`party`) <- state (`state`: term, chamber, caucus, mandate) <- processes
  (`process`) <- laws (`law`); readers (`io`) feed entities and state. What a vote
  recorded (`vote`) is input, not state: it depends only on the foundation and processes
  read it. The arithmetic of dividing seats (`apportionment`) and the measures of a
  result (`measure`) depend only on the foundation and know no law.
- **Relations, not labels.** What separates one system of government from another is
  a handful of relations: who selects whom, who can remove whom, who can end whose
  term. The engine models these relations directly. A system type is *derived* from
  them, never declared, because real constitutions mix them and a counterfactual
  changes one relation at a time.
- **One rule at a time.** Because rules are small and separate, replacing one rule and
  replaying history is the basic operation. That is the whole point of rules-as-code.
- **Partial history is normal.** Every block tolerates missing facts, modelled as
  absent, so a record known only as a seat table and one known seat by seat use the
  same types.

## Repositories

Five, split along the lines that actually differ: licence, size and change cadence.

| Repo | Holds | Why separate |
|---|---|---|
| [**wahlwerk**](https://github.com/wahlwerk/wahlwerk) | the engine | Apache-2.0, small, `pip install`-able |
| [**wahlwerk-data**](https://github.com/wahlwerk/wahlwerk-data) | normalised election bundles | GPL-3.0, data under its source's licence (usually dl-de/by-2-0), grows per election, must never bloat the engine's clone |
| **wahlwerk-data-processing** | one script per source, writing the bundles | reads the original files (xlsx, csv), which never enter the archive; checks every published sum |
| [**wahlwerk-execute**](https://github.com/wahlwerk/wahlwerk-execute) | notebooks and analyses | depends on the engine and the archive; its output is figures, not a library |
| **wahlwerk-ui** | charts | no dependencies; the engine's optional extra `wahlwerk[ui]` |

The engine does **not** depend on the data repo, and its test suite passes with the
archive absent — anything that reads a bundle builds a synthetic one in a `tmp_path`, and
the real archive is checked on the other side, where each bundle is generated and compared
with every sum the source publishes. Golden tests keep their fixtures here, under
`tests/golden/`: reduced to what the allocation reads (votes per Wahlkreis), with every
source and SHA-256 beside them, so **CI runs offline and a golden test never fails for
network reasons**.

`wahlwerk-data` is the *archive*: every Bundestagswahl since 1949, sixteen Länder,
kommunal. To use it, clone it and let the engine find it:

```bash
git clone https://github.com/wahlwerk/wahlwerk-data.git   # beside this repo
```

Resolution order, first hit wins:

```
$WAHLWERK_DATA          explicit — what CI and containers set
../wahlwerk-data        a sibling clone, searched upwards from the cwd
~/.cache/wahlwerk/data  a fetched copy, once scripts/fetch_data.py exists
```

So **cloning `wahlwerk-data` beside `wahlwerk` is convenient, not required** — it is just
what makes the middle path work with no configuration. `wahlwerk.io.find_archive` reports
every path it searched if none is found.

Bundles carry `schema = N` in their `election.toml` and the engine declares which
versions it reads, so a format change is a loud, testable break rather than a silent
mis-parse. `wahlwerk-data` tags releases; an analysis pins an engine version and a data
tag together, which is what makes a reproduction reproducible.

## Language

English is the language of code; German electoral law is the subject matter. The rule
that keeps both honest:

> **Translate the concept. Keep the term of art.**

A term is *of art* if translating it would lose a distinction the law makes, or if you
would have to invent the English. Everything else is English.

| Keep German | Use English | Why |
|---|---|---|
| `Zweitstimme`, `Erststimme` | ~~second vote~~ | "second" sounds like ordering; it names a function |
| `Wahlkreis`, `Stimmkreis`, `Wahlbezirk` | ~~constituency~~ | English has one word for three legally distinct things |
| `Überhang`, `Ausgleich`, `Grundmandatsklausel` | — | no English equivalent exists |
| `Nachrücken`, `Wahlprüfung`, `Auflösung` | — | named procedures in statute |
| — | `party`, `seat`, `unit`, `count`, `share` | the same concept in every country |

The test: **does an official source use this word?** If the Bundeswahlleiterin, a
statute or the BVerfG says it, keep it. If you had to reach for a dictionary, you are
inventing vocabulary nobody else uses.


**Orthography.** Identifiers and filenames are ASCII-transliterated (`ue`, `oe`, `ae`,
`ss`) so they stay greppable and typeable on any keyboard. Prose, data and output use
correct German:

```python
# wahlwerk/events/aufloesung.py
class Aufloesung(Model):
    """Auflösung under Art. 68 GG: the term ends early."""
```

Sphinx roles name the *identifier*, so ``:class:`Aufloesung` `` stays ASCII while the
sentence around it does not. `ruff` catches the mistake that matters — an `__all__`
entry that no longer names anything is `F822`.


**Everything else is English**: docstrings, comments, test names, commit messages,
error messages, and this README. A German reader knows English; nobody outside knows
what a `Zweitstimmendeckung` is either way, so the docstring explains it.

**Legal citations** stay in the German form with an English gloss on first use, and
always with the section: `Sec. 10 (1) GO-BT`, `Art. 68 GG`, `Sec. 4 (2) BWahlG`.
Judgments carry their docket: `BVerfG, 2 BvF 1/23`.


## Identifiers

Every stable key is a lowercase ASCII dotted path, narrowest scope last. The scheme is
enforced in [`ids.py`](src/wahlwerk/ids.py) — each id is a `NewType` over a
pattern-constrained string, so `de.bund.Bundestag` fails validation where it is written,
and mypy still refuses to pass a `PartyId` where a `UnitId` belongs.


| Type | Shape | Examples |
|---|---|---|
| `BodyId` | dotted | `de.bund.bundestag`, `de.by.landtag` |
| `CandidateId` | dotted | `max-mustermann` |
| `LawId` | dotted, jurisdiction first | `de.st.lwg.2021`, later `de.bund.bwahlg.2023` |
| `UnitId` | dotted | `de.st.wk.001`, `de.st.wk.035.gem.15002000.wbz.000001` |
| `PartyId` | single segment | `cdu`, `gruene`, `team-todenhoefer` |
| `CaucusId` | single segment, unique within a chamber | `spd`, `cdu-csu` |
| `MandateId` | dotted, unique within a chamber | `wk.001`, `list.afd.001`, `spd.001` |
| `LevelName` | single segment | `wahlkreis`, `land`, `bund` |

All of these exist; a new id type is added with the first field that needs it. A
`MandateId` names the seat, not its holder, so it survives Nachrücken: an allocation
names it by how the seat was won (`wk.001` for a Wahlkreis, `list.afd.001` for a list
seat), a seat table by party (`spd.001`).

**Bodies** are named by jurisdiction then institution. `de.bund` is the federation;
the sixteen Länder use their official two-letter code:

| | Body | | Body |
|---|---|---|---|
| Bund | `de.bund.bundestag` | | `de.bund.bundesrat` |
| BW | `de.bw.landtag` | NI | `de.ni.landtag` |
| BY | `de.by.landtag` | NW | `de.nw.landtag` |
| BE | `de.be.abgeordnetenhaus` | RP | `de.rp.landtag` |
| BB | `de.bb.landtag` | SL | `de.sl.landtag` |
| HB | `de.hb.buergerschaft` | SN | `de.sn.landtag` |
| HH | `de.hh.buergerschaft` | ST | `de.st.landtag` |
| HE | `de.he.landtag` | SH | `de.sh.landtag` |
| MV | `de.mv.landtag` | TH | `de.th.landtag` |

Three Länder do not call their parliament a Landtag, which is why the institution is
named rather than assumed: Berlin has an Abgeordnetenhaus, Bremen and Hamburg have a
Bürgerschaft. Municipal bodies extend the same path —
`de.nw.koeln.rat`, `de.by.muenchen.stadtrat`.

A `BodyId` is only a key. The institution *model* — name, jurisdiction, Bundesrat vote
weight, election calendar — arrives with M6, when the Bundesrat needs the sixteen Länder
as data rather than as strings.



## Non-negotiables

- **Everything is a frozen, validated pydantic model.** Invariants live on the type, so
  a bad number fails where it enters the system — when a reader parses a row out of a
  Landeswahlleiter file — not eight stages later as a seat count that is off by one.
  Unknown columns are a hard error (`extra="forbid"`); vote counts cannot be negative;
  a ballot section cannot let a voter pile five marks when they only have three.
  Every field is declared with `Field(default=..., description=...)`; see
  [Model fields](#model-fields) and [`model.py`](src/wahlwerk/model.py).
- **Exact arithmetic.** Divisor comparisons use `fractions.Fraction` or scaled integers,
  never floats. Float rounding both hides real ties and manufactures fake ones.
- **Ties are a result, not an error.** Where the law prescribes lots (Losentscheid), the
  engine returns an explicit [`Tie`](src/wahlwerk/apportionment/tie.py) rather than
  letting sort order decide, and `Apportionment.with_lot(winners)` applies a draw that
  actually happened. Inside an allocation a tie stops the next step, until a lot can be
  applied there too.
- **One long table for all vote data.** A tally is a flat sequence of rows:
  `unit, level, kind, section, channel, party, candidate, option, count`. Cumulation is a bigger count; panachage is
  more rows; a new Land quirk is new rows, never new columns. That table is also
  literally one CSV file, which is what makes the archive format and the in-memory
  format the same thing.
- **Golden tests are the product.** Every historical election under every implemented law
  becomes a test asserting the official seat distribution exactly: party by party,
  Wahlkreis and list seats alike (`tests/golden/`).
- **No bulk data in the repository.** Vote data lives in `wahlwerk-data`, which records
  each source's URL, retrieval date and SHA-256 so a bundle is reproducible without
  committing the multi-megabyte original. Fixtures committed here stay small and clearly
  sourced. Reference data lives there too: the party registry is
  `wahlwerk-data/parties/de/de.bund.json`, loaded with `PartyRegistry.from_json(path)`.
  The engine knows what a party *is* and how the file *looks*, never which parties
  exist.


## Model fields

Every field is declared with `Field`, carrying its default and its description:

```python
class BallotSection(Model):
    party: PartyId = Field(description="The list the votes in this section count for.")
    votes_per_voter: int = Field(default=1, ge=1, description="Marks one voter may place here.")
    votes: Count = Field(default=0, description="Valid votes cast in this section.")
```

Rules, in order of preference:

1. **Always `Field(default=..., description=...)`.** The description lives on the field,
   not in an attribute docstring, so it shows in the JSON schema and next to the type.
   A required field has no sensible default: it omits `default` and still carries a
   `description`. Never a bare `= 0` or an undocumented field.
2. **Reach for a shared alias for the type.** `model.py` exports `Count` (≥ 0),
   `Seats` (≥ 0) and `Share` (exact `Fraction`, 0–1); `ids.py` exports `Slug`,
   `DottedKey` and the id types. The alias carries the constraint; `Field` only adds the default
   and description. If the same constraint appears three times, it wants an alias, not
   three `Field(ge=0, ...)`.
3. **Put a local constraint in the same `Field`** only when the type cannot carry it:
   `ge`, `gt`, `min_length`, `pattern`, `discriminator`.
   `votes_per_voter: int = Field(default=1, ge=1, description=...)` is right; the
   constraint is local and does not recur.
4. **Empty container defaults use `default_factory`** with an immutable type:
   `Field(default_factory=tuple, ...)`, `Field(default_factory=frozenset, ...)`, never a
   `list` or `dict`. Scalars and `None` keep `default=`.
5. **Never `Field(alias=...)` on a domain model.** Source column names (`Gruppe`,
   `Anzahl`, `Stimmart`) are mapped in the reader in `io/`, not smuggled into the model.
   Otherwise the domain vocabulary silently becomes whichever Landeswahlleiter was
   parsed first.
6. **Cross-field rules go in `@model_validator(mode="after")`**, returning `self`, with
   a message that names the offending values: `f"cap {self.cap} is below minimum
   {self.minimum}"`. Not `f"invalid SeatTargets"`.
7. **Prefer a validator over a comment.** If a description says "must be", make it must
   be.

## General conventions

- **Paths are `pathlib.Path`, everywhere.** A function that takes a path accepts
  `str | Path` and converts on its first line:

  ```python
  def read_parties(file_path: str | Path) -> tuple[Party, ...]:
      file_path = Path(file_path)
  ```

- **`.get()` always returns something and never raises**: the value, or `default`
  (`None` unless given), like `dict.get`. Indexing is the lookup that raises:

  ```python
  registry.get("bsw")         # None
  registry.get("bsw", other)  # other
  registry["bsw"]             # KeyError: "no party 'bsw' in registry"
  ```

- **Booleans start with `is_` or `has_`** (strongly preferred), or `are_` / `have_`
  where the subject is plural; fields and properties alike: `Mandate.is_vacant`,
  `Chamber.is_empty`, `Chamber.has_caucuses`.

- **Missing facts are absent, not faked.** An unknown value is `None`, never a
  placeholder like `"unknown-party-id"` or `"???"`, which would pass validation and be
  counted as real.


## Build order

Built one small step at a time; each step leaves the package importable.

**Done**

- `Model` base and the `Count`, `Seats`, `Share` aliases
- Identifiers: `Slug`, `DottedKey`, `BodyId`, `CandidateId`, `PartyId`, `CaucusId`,
  `MandateId`, `UnitId`, `LevelName`, `LawId`
- `Mandate` (party that won it, origin) with `MandateOrigin` and `MandateSource`, in
  `state/` since it is what a chamber is made of
- Standing state: `Term` (with its date-order invariant), `Chamber` (mandates as the
  source of truth for seats, caucuses stored beside them and validated against them;
  `size`, `is_empty`, `seats_by_party`, vacant and filled seats, `minimum_mandates`
  with `is_below_minimum` / `is_at_minimum` / `is_above_minimum`), `Caucus` (`id`
  and `mandates` as mandate ids; names stay on the parties)
- `Mandate.id`: every seat has an id unique within its chamber (`spd.001`), which
  caucuses refer to
- `Mandate.is_vacant`: a seat that exists but nobody holds, distinct from a seat whose
  party is not on record
- The first process: `Chamber.form_caucuses(protocol)` clears and re-forms caucuses
  from a protocol of `CaucusStep`s (`CaucusPerParty`, `CaucusOfParties`) in
  `wahlwerk.process`
- Non-attached seats (fraktionslos in the Bundestag): the seat-table key
  `"non-attached"` (or `None`), `Chamber.non_attached_seats`, and the imaginary caucus
  `non-attached` in `seats_by_caucus` and `get_caucuses`
- Opt-in logging: `wahlwerk.log.setup_logger()` / `disable_logging()`, one logger per
  module, silent by default
- `Party` and `PartyRegistry` (`[id]`, `.get()`, `.from_json()`), with the reader for
  wahlwerk-data's party files in `wahlwerk.io`
- Tests under `tests/`, mirroring `src/wahlwerk/`
- `TallyRow`, one long-table row for votes, invalid votes, Wahlberechtigte and Wähler
- `PopularVote` and `Source`, and `read_bundle` for the bundle directory wahlwerk-data
  stores it in (`election.toml`, `tally.csv`); "bundle" names the files, not the model
- `Tally`, the long table of rows: `filter`, `sum_to` (roll up units by id prefix),
  `sum_by`, `total`; two rows counting the same thing are rejected
- The level structure: `Level` and `Tally.levels`, from the `[levels]` table of a
  schema-2 bundle, for the main (electoral) hierarchy the unit ids follow; every row is
  checked against it, and `sum_to("wahlkreis")` takes the depth from it
- Alternative hierarchies beside it, for analysis: `Hierarchy` in
  `PopularVote.hierarchies`, from `[hierarchies.<name>]` and `<name>.csv`;
  `sum_to("gemeinde", hierarchy=...)` (the administrative one: Land, Kreis, Gemeinde)
- Apportionment methods in `wahlwerk.apportionment`, free of any law: divisor
  methods (`DHondt`, `SainteLague`, `LinearDivisor`) and largest remainder
  (`HareNiemeyer`), exact, with a `Tie` as a result where claims are equal and
  `with_lot` to apply the lot actually drawn; `MajorityFirst`, the majority clause of
  Sec. 35 (6) LWG LSA, around any largest remainder method
- Thresholds (relative, absolute, seats won, exempt keys, and "or" over them) and
  Überhang/Ausgleich, in the same package
  (`overhang`, `Ausgleich`: the smallest house covering every key's seats), after
  votelib
- The allocation, `wahlwerk.process.allocation`: a law is a protocol of steps (count,
  Wahlkreis winners, threshold, seat total, entitlement, list seats, chamber) checked
  for order before it runs; `allocate(vote, protocol)` returns the `Chamber`
- The Mehrsitze loop of Sec. 35 (8), (8a) LWG LSA (`RepeatForMehrsitze`, `FraktionSize`)
- `law/`: electoral laws as versioned protocols by jurisdiction, with a registry by body
  and date; the first is `law/de/st/lwg.py`. Beside it, the caucus protocol of the
  Bundestag's Geschäftsordnung, `law/de/bund/gobt.py` (CDU and CSU form the `union`),
  passed to `Chamber.from_seats(..., caucus_protocol=...)`
- Golden tests: the Landtag Sachsen-Anhalt 2021 (97 seats, raised from 83 for
  Mehrsitze) and 2026 (83), each derived from the votes under the law in force on
  election day, equal the official Sitzverteilung exactly, party by party, Wahlkreis and
  list seats; fixtures and sources in `tests/golden/`
- Measures of disproportionality in `wahlwerk.measure.proportionality`, exact, after
  votelib

**Next**

The path from a popular vote to a chamber, and how it was built, is in
[`src/wahlwerk/process/allocation/README.md`](src/wahlwerk/process/allocation/README.md). In order:

- A lot inside an allocation, so a tied Wahlkreis or entitlement can be decided as
  recorded instead of stopping the run
- The LWG of 2016 and earlier (87 seats, 43 Wahlkreise), and Mecklenburg-Vorpommern,
  whose bundles are being prepared in wahlwerk-data

Alongside:

- A trace of how a result was derived: one helper that applies a protocol and records
  each step (`before`, step, `after`) when a `record()` context is active, so every
  process is traced the same way; kept off the state so equality is unaffected
- Move pytest, mypy and ruff from runtime to dev dependencies
- `Caucus.parties` and `Caucus.is_gemeinschaft`, derived from the seats a caucus
  groups (CDU/CSU is formed by `CaucusOfParties`)
- `Caucus.declared_size` for aggregate-only records, validated against `mandates` when
  both are present
- `Mandate.unit`, `Mandate.level` with `UnitId` and `LevelName`
- Chamber votes in `vote/chamber/`: votes cast by the members of a body, secret
  (Bundeskanzlerwahl, as counts) or named (namentliche Abstimmung, one row per member
  `MandateId` and choice); tallies stay popular-vote only
- `find_archive()`, once there is more than one file to find in wahlwerk-data

## Development

```bash
uv sync
uv run pytest -q             # tests
uv run mypy --strict src     # types (with pydantic's mypy plugin)
uv run ruff check src tests  # lint
```

## Non-goals
- **Forecasting.** Predicting vote shares is a separate and much weaker discipline; the
  counterfactual engine needs none of it to be useful.
- **Simulating the Bundesverfassungsgericht.** Judicial review is modelled as a
  *constraint checker* over law configurations, never as an agent.
- **Voter behaviour models.** Votes are inputs, historical or sampled.


## Data and attribution

No election data is committed here, except the golden test fixtures: small, reduced to
the votes per Wahlkreis and the official seat table, each with its sources, licence and
SHA-256 in a README beside it.

Results are generally published under Datenlizenz Deutschland (dl-de/by-2-0), which
requires attribution. Every bundle in `wahlwerk-data` carries its publisher, title, URL,
licence and attribution in `election.toml`, and `PopularVote.source` keeps them — so the
attribution travels with anything republished from it rather than being left behind at the
read. Planned sources: `bundeswahlleiterin.de`, the sixteen Landeswahlleiter,
`dip.bundestag.de`, and `wahlrecht.de` as an independent check on the allocation
algorithms.

## Licence