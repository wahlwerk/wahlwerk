# wahlwerk

`wahlwerk` models electoral and parliamentary systems as rules-as-code: a deterministic
engine parameterised by an electoral law, so small changes to the law can be replayed
against real historical votes.

The project is built **step by step**. Do only the step asked for; do not add modules,
fields or features ahead of it to make something look complete. The planned order is
"Build order" in the README.

## Project state

The package imports cleanly (`uv run python -c "import wahlwerk"`). What exists:

| Module | Contents |
|---|---|
| `model.py` | `Model` base (with a type-checking-only blank `__init__`, see below); aliases `Count`, `Seats`, `Share` |
| `ids.py` | `Slug`, `DottedKey`; ids `BodyId`, `CandidateId`, `PartyId`, `CaucusId`, `MandateId`, `UnitId`, `LevelName`, `LawId` |
| `log.py` | `setup_logger(file_path=None, *, level, console)` (file only when given), `disable_logging`, `LOGGER_NAME`; the root adds a `NullHandler` |
| `party/` | `Party` (`id`, `name`, `short_name`), `PartyRegistry` (`[id]`, `.get()`, `.from_json()`) |
| `io/` | `read_parties`: reads a party registry file from wahlwerk-data; `read_bundle(dir_path, election_file_name, tally_file_name)`: reads a bundle directory into a `PopularVote` (file names optional, default `election.toml` with `schema` (1 or 2; `SCHEMA = 2` is written; checked here, not stored on the model), `[source]`, and in schema 2 a required `[levels]` table (main hierarchy) and optional `[hierarchies.<name>]` tables, each read from `<name>.csv` (`HIERARCHY_COLUMNS`: `unit,level,parent`), `tally.csv` with the `TallyRow` columns; blank cells are `None`; duplicate rows rejected); `resolve_election_dir(data_dir, key)`: a bundle key to its directory in wahlwerk-data (`de.landtag.st.2026` is `elections/de/landtag/st/2026/`) |
| `state/` | `Mandate` (`id`, `party`, `origin`, `is_vacant`; derived `has_party`; `from_party(party, id)`), `MandateOrigin` (`source`), `MandateSource` enum; `Term` (with `_check_order`; derived `is_ended`, `is_ended_early`), `Caucus` (`id`, `mandates`: mandate ids; `size`; no names) with `NON_ATTACHED`, `Chamber` (`term`, `mandates`, `caucuses`, `minimum_mandates`, `are_caucuses_recorded`; validates mandate ids unique and caucuses against mandates; derived `body`, `size`, `is_empty`, `has_caucuses`, `seats_without_caucus`, `non_attached_seats`, `seats_by_caucus`, `get_caucuses(include_non_attached=False)`, `vacant_seats`, `filled_seats`, `is_below_minimum`/`is_at_minimum`/`is_above_minimum`, `seats_by_party`; `from_seats(seats, *, term, minimum_mandates, caucus_protocol)`, `with_caucuses`; processes `clear_caucuses`, `form_caucuses`; display `__repr__`, `_repr_html_`, `fancy_html`) |
| `vote/` | `popular/`: `TallyRow` (`unit`, `level`, `kind`, `section`, `channel`, `party`, `candidate`, `option`, `count`; `_check_kind`), `TallyKind` enum (`VOTES`, `INVALID`, `ELIGIBLE`, `VOTERS`); `Level` (`name`, `depth`: dotted segments of its unit ids; the main hierarchy); `Hierarchy` (`name`, `levels`, `units`: `HierarchyUnit` `unit`/`level`/`parent`; `_check_tree`; `units_at(level)`), an alternative hierarchy such as the administrative one; `Tally` (`rows`, `levels`; `_check_unique`, `_check_levels`; `filter(**criteria)`, `sum_to(level, depth=None, *, hierarchy=None)` by unit-id prefix with depth from `levels`, or along a `Hierarchy`, `sum_by(*fields)`, `total()`); `PopularVote` (`source`, `tally`, `hierarchies`, each covering every counted unit; `hierarchy(name)`; `from_dir` via `read_bundle`, `from_key(key, data_dir)` via `resolve_election_dir` and `from_dir`) and `Source` (`publisher`, `title`, `url`, `licence`, `attribution`, `retrieved`, `sha256`); `chamber/`: empty |
| `measure/` | `proportionality`: `loosemore_hanby`, `rose`, `gallagher_squared`, `rae`, `lijphart`, `sainte_lague`, `d_hondt`, `regression`, each `(votes, seats) -> Fraction` over plain mappings (after votelib's `crit.proportionality`) |
| `apportionment/` | law-free; exposes its modules, not their names (`ww.apportionment.divisor.SainteLague`): `method`: `ApportionmentMethod.apportion(weights, seats) -> Apportionment` over opaque str keys and int/`Fraction` weights (floats a `TypeError`); `divisor`: `DivisorMethod` (`divisor(index)`; `DHondt`, `SainteLague`, `LinearDivisor(first, step)`); `remainder`: `LargestRemainder` (`quota(total, seats)`; `HareNiemeyer`); `majority`: `MajorityFirst(method)` (Sec. 35 (6) LWG LSA); `result`: `Apportionment` (`seats` as (key, seats) pairs in input order, `tie`; `[key]`, `.get()`, `as_dict()`, `total`, `is_decided`, `with_lot(winners)`); `tie`: `Tie` (`candidates`, `seats`); `threshold`: `Threshold.select(weights, won=None) -> frozenset` and `uses_won` (`RelativeThreshold(share, accept_equal)`, `AbsoluteThreshold`, `SeatThreshold(seats)`, `Exempt(keys)`, `AlternativeThresholds(thresholds)`, an "or"); `ausgleich`: `overhang(apportionment, minimum)`, `Ausgleich(method, limit).apportion(weights, seats, minimum)` (grow the house until every minimum is covered) |
| `law/` | modules only: `base`: `Law` (`id`, `title`, `citation`, `body`, `source`, `in_force_from`/`until`, `protocol`; checked on creation, must form a chamber; `is_in_force(on)`), `LawRegistry` (`[id]`, `.get()`, `in_force(body, on)`); `registry`: `LAWS`; `de/st/lwg.py`: `LWG_2021`; `de/bund/gobt.py`: `CAUCUS_PROTOCOL` (Sec. 10 (1) GO-BT: CDU and CSU form the caucus `union`, every other party its own; a `CaucusProtocol`, not a `Law`) |
| `process/` | `allocation/` (modules only; design and plan in its `README.md`): `base`: `Allocation` (`tally`, `totals` per level, and the optional facts `districts`, `eligible`, `house`, `seat_total`, `entitlement`, `list_seats`, `overhang`; `facts`, `total(level)`, `votes_by_party(level, section)`, `district_wins()`, `with_values`), `DistrictResult` (`unit`, `nominee`, `party`, `candidate`, `votes`, `tie`), `AllocationStep` (abstract `reads`/`writes`/`_apply`; `apply` checks both), `AllocationProtocol`, `check_protocol(protocol)`; `count`: `SumVotes(level)`; `district`: `ElectDistricts(section, level)` (plurality, `Tie` on equal votes); `eligibility`: `ApplyThreshold(threshold, section, level)` (reads `districts` if `threshold.uses_won`), `SetHouse(seats)` (the `house` fact, the legal minimum), `SetSeatTotal()` (the house less Wahlkreise won by Einzelbewerber and ineligible parties); `mehrsitze`: `RepeatForMehrsitze(protocol, factor, full_rounds, fraktion)` (raise the house and allocate again), `FraktionSize(share, section, level)` (Sec. 35 (8a), its reading documented); `seats`: `ApportionSeats(method, section, level)`, `DeductDistrictSeats()` (list seats and overhang); `chamber`: `FormChamber(minimum_mandates)` (mandates `wk.001`, `list.afd.001`, origin `ELECTION`, no caucuses); `allocate`: `allocate(vote, protocol, *, term=None) -> Chamber`, `derive(vote, protocol) -> Allocation`; `caucus`: `CaucusStep` (abstract, callable), `CaucusProtocol` (tuple of steps), `CaucusPerParty`, `CaucusOfParties` (`parties`, `id`; warns on missing parties), `ProtocolWarning` |

**One electoral law is implemented:** `law/de/st/lwg.py` (`LWG_2021`, the Wahlgesetz of Sachsen-Anhalt as it governed the Landtag elections of 2021 and 2026), and one caucus protocol, `law/de/bund/gobt.py` (Sec. 10 (1) GO-BT). Golden tests (`tests/golden/test_de_landtag_st.py`, fixtures beside it) reproduce both official results exactly, 97 and 83 seats. There is no lot inside an allocation (a tie stops the next step), no Sec. 32 S. 2, and there are no events, ballots, chamber votes, or archive discovery (`find_archive`) yet. The README describes
the target system; where it names something (`LawId`, `find_archive`), check this
table before assuming it exists.

Tests live in `tests/`, mirroring `src/wahlwerk/`. Tests that read files write their own
small fixture to `tmp_path`; they never read wahlwerk-data. Golden tests are the exception to
`tmp_path`: their fixtures are committed under `tests/golden/<bundle key>/`, small (reduced to what the
allocation reads), with every source, licence and SHA-256 in a README beside them; they never skip
or xfail.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) (`uv.lock` is committed, Python 3.10).

```bash
uv sync                                  # create/refresh .venv from the lockfile
uv add <pkg>                             # runtime dependency
uv add --dev <pkg>                       # dev dependency
uv run python -c "import wahlwerk"       # smoke test
```

All must pass before anything is called done:

```bash
uv run pytest -q
uv run mypy --strict src
uv run ruff check src tests
```

mypy runs with pydantic's plugin (`[tool.mypy]` in `pyproject.toml`), so model
constructors take field input as pydantic does: `SumVotes(level="land")` type-checks, and
pydantic validates the id at runtime.

pytest, mypy and ruff are currently listed under runtime `dependencies` in
`pyproject.toml`; they belong in the dev group (`uv add --dev`).

The engine has **no** jupyter or matplotlib dependency and must not grow one; notebooks
live in wahlwerk-execute.

Display follows one pattern: `__repr__` is a plain-text table, `_repr_html_` a plain HTML
table (both built here, no dependencies), and `fancy_html()` a chart, called explicitly.
Charts come from wahlwerk-ui, an **optional** extra (`wahlwerk[ui]`, also in the dev
group); `fancy_html` imports it inside the method and raises `ImportError` naming the
extra when it is missing. Never import `wahlwerk_ui` at module level.

## Sibling repositories

Five repos, cloned side by side:

```
CODE/wahlwerk_/
  wahlwerk/                  the engine       Apache-2.0     <- you are here
  wahlwerk-data/             the archive      GPL-3.0; data: its source's licence
  wahlwerk-data-processing/  bundle makers    reads the sources, writes wahlwerk-data bundles
                                              with the engine's reader, checks published sums
  wahlwerk-execute/          notebooks        depends on the engine and the archive
  wahlwerk-ui/               charts           no dependencies; optional extra of the engine
```

## Language policy

English is the language of code; German electoral law is the subject matter. Keep the
term of art (`Zweitstimme`, `Wahlkreis`, `Nachrücken`), translate everything else.
Identifiers are ASCII-transliterated (`Aufloesung`); prose uses correct German. Full
policy in the README, "Language".

## Architecture

### Everything inherits from `Model`

`src/wahlwerk/model.py` defines the single pydantic base class. Its configuration is
load-bearing and its docstring is the authoritative explanation; the short version:

- `frozen=True`: state is inert. Only events produce new state, and frozen models are
  hashable, which is what lets them be used as dictionary keys in tallies.
- `extra="forbid"`: a misspelled column in a source file from one of sixteen
  Landeswahlleiter is a hard error, not a silently dropped field.
- `validate_default=True`: defaults cannot dodge invariants.
- Under `TYPE_CHECKING` only, `Model` declares a blank-docstring `__init__`: Pylance
  documents a constructor call with the nearest `__init__` docstring, which would be
  pydantic's generic one; it never falls back to the class docstring there, so a call
  shows the fields alone, and the class docstring shows on the class name elsewhere.

pydantic does not deep-freeze containers. Use `tuple` and `frozenset` for any field that
is part of a model's identity, never `list` or `dict`.

### Exact arithmetic only

Vote counts and seat counts are `Count`/`Seats` (`int`, `ge=0`). Shares are `Share`, an
exact `fractions.Fraction` bounded to `[0, 1]`. **Never `float`.** Apportionment methods
(Sainte-Laguë, d'Hondt, and the tie and rounding rules around them) are only reproducible
against official results under exact rational arithmetic.

### Identifiers are strings, not objects

`src/wahlwerk/ids.py` builds every identifier from one regex: a `Slug` is lowercase ASCII
with inner hyphens or underscores (`zweitstimme`, `cdu-csu`). A `DottedKey` joins slugs
with dots, **narrowest scope last**: `de.bund.wk.001`, `de.bund.bundestag`, `de.by.landtag`.
New id types follow `BodyId`: a `NewType` over `str`, wrapped in the constraint object
itself, `Annotated[_XId, DOTTED]` or `Annotated[_XId, SINGLE]`. Two traps:

- Never `NewType("XId", DottedKey)`: `NewType` needs a real class as its base, and
  pyright rejects every annotation using it (`reportInvalidTypeForm`).
- Never `Annotated[_XId, Slug]` or `Annotated[_XId, DottedKey]`: pydantic silently
  ignores an `Annotated` alias used as metadata, so the pattern is never checked.

Add an id type when the first field needs it, not before.

### Package layout

Folders are sorted by role; each answers one question.

| Where | Role | Holds |
|---|---|---|
| `model.py`, `ids.py`, `log.py` | foundation | the base model, identifiers, logging; top-level modules, no folder |
| `party/` | entities | things with a stable identity that everything refers to by id; not state. Later siblings: a person/candidate and a body model, then possibly one `entity/` folder |
| `state/` | state | what exists at a point in time, inert, replaced only by processes: `Term`, `Chamber`, `Caucus`, `Mandate` |
| `vote/` | votes | what a vote recorded, split by who votes: `vote/popular/` (`TallyRow`, one row type for votes and the people eligible and voting) and `vote/chamber/` (empty so far); input, never replaced by a process; not state |
| `apportionment/` | methods | how seats are divided among keys, free of any law: apportionment methods, thresholds, majority clauses, Überhang and Ausgleich, `Tie`; imports only the foundation |
| `process/` | processes | steps, protocols, and the processes that apply them: caucus formation (`caucus`) and the allocation from a popular vote to a chamber (`allocation/`); they use `apportionment/` |
| `measure/` | measures | numbers computed from results for analysis, never input to a law: `proportionality` (Loosemore-Hanby, Gallagher squared, Sainte-Laguë and D'Hondt indices, ...); imports only the foundation |
| `io/` | readers | the only place that knows source file formats |
| `law/` | laws | rules as protocols, by jurisdiction: electoral laws, one version per `Law` object (`law/de/st/lwg.py`), with a registry by id and by body and date; caucus protocols from a Geschäftsordnung (`law/de/bund/gobt.py`); rules, not data, so here and not in wahlwerk-data |
| `event/` | later | dated facts |

No grab-bag folders (`basics/`, `core/`, `common/`, `utils/`). Dependencies point one
way, and a module imports only from layers to its left:

```
foundation  <-  entities  <-  state  <-  process
     ^             ^            ^          |  |
     |             io ----------+          |  |
     +---------  vote  <-------------------+  |
     +---------  apportionment  <-------------+
     +---------  measure                      |
                                     law  ----+  (uses process and apportionment)
```

`vote` imports only the foundation (ids, not `Party` objects); `process` reads it,
`state` never imports it. `apportionment` and `measure` import only the foundation; `process` uses `apportionment`, nothing uses `measure`. Votes are told apart by who votes, and each case has its own subpackage: a
**popular vote** (`vote/popular/`) is cast by the electorate and recorded as `TallyRow`
counts per unit (votes, invalid votes, Wahlberechtigte and Wähler alike, told apart by
`TallyKind`), which are aggregated into larger units; a **chamber vote**
(`vote/chamber/`) is cast by the members of a body (a chamber or a committee), secret
like the Bundeskanzlerwahl or named like a namentliche Abstimmung, and is not modelled
yet. A chamber vote is not a tally. Never call either case a "ballot" or a "roll call".

`state` never imports `process` at load time (only under `TYPE_CHECKING`, or inside a
method with a comment saying why).

### State

`src/wahlwerk/state/` holds standing, inert data that only processes may replace:
`Term` (a Wahlperiode of a body), `Chamber` (the mandates constituting a body at a point
in time, and the caucuses over them), `Caucus` (a Fraktion: a grouping over mandates,
deliberately distinct from a party) and `Mandate` (one seat, what `Chamber.mandates` is
made of).

`Chamber.mandates` is the source of truth for a chamber's seats; `size`, seats per
party and vacancies are derived from it. `Chamber.caucuses` is stored beside it,
because who sits in which caucus (CDU/CSU spanning two parties, a member who leaves)
cannot be derived from the seats. Every `Mandate` has an `id` (`MandateId`, dotted,
unique within its chamber) that names the seat, not its holder, so it survives
Nachrücken; `from_seats` numbers them per party (`spd.001`, `non-attached.001`,
`vacant.001`), while an allocation names them by how the seat was won
(`wk.001`, `list.afd.001`, as `FormChamber` does). A `Caucus` has an `id` (`CaucusId`, a slug unique within its chamber) and
**no names**: names belong to `Party`, and parties stay separate from caucuses, so a
caucus never copies or combines party names. It holds `mandates`, the ids of its seats, and
`Chamber._check_caucuses` keeps the two from disagreeing: no caucus is empty, every
mandate id exists in the chamber, is filled, and sits in at most one caucus.
`CaucusOfParties` accepts `Party` objects or ids and names the caucus by the party ids
joined with `-` (`cdu-csu`) unless `id` is given. Caucus membership is **never** a field
on `Mandate`: it belongs to the holder, not the seat. Three facts about a seat are kept
apart and never conflated: **vacant** (`Mandate.is_vacant`: the seat exists, nobody
holds it; the opposite is *filled*), **unrecorded** (`Mandate.has_party` is
false: the party is not on record), **without caucus**
(`Chamber.seats_without_caucus`: any seat in no caucus, vacant ones included) and
**non-attached** (`Chamber.non_attached_seats`: *filled* seats in no caucus, `None` when
membership is not on record, i.e. no caucuses and `are_caucuses_recorded` false; `form_caucuses`
sets it, `clear_caucuses` unsets it). Non-attached is the European Parliament's English term and
is used instead of fraktionslos because the concept is not German; never "independent",
which means elected without a party. The concept and both constants live in `state/caucus.py`,
not on `Mandate`: non-attached is a relation between a seat and the caucuses. In a seat table the reserved key `NON_ATTACHED`
(`"non-attached"`), or `None` for short, gives their count, with their party left
unrecorded. In `Chamber.seats_by_caucus` (keyed by caucus id) they appear under the
imaginary caucus `NON_ATTACHED`, which exists only in derived views and never in
`Chamber.caucuses`; `get_caucuses(include_non_attached=True)` builds it as a `Caucus`
with id `NON_ATTACHED` (`"non-attached"`), so no real caucus may use that id. `minimum_mandates` is compared with *filled* seats;
`Chamber.from_seats` forms caucuses with the protocol `(CaucusPerParty(),)` and pads a
short table with vacant seats in no caucus. The general approach (blocks, state/rules/events, relations not
labels) is "Approach" in the README. The body is stored once, on `Term`
(optional, like every other `Term` field); `Chamber.body` is a property reading
`term.body`, `None` when either is missing. A chamber whose term details are unknown
uses `Term(body=...)` with everything else left out. `Mandate.party` is the party whose
nomination **won** the seat and never changes during the term. A member who changes
party keeps the mandate (Art. 38 GG), so a person's current party is not the seat's
party; that belongs to `Caucus` later.

Models are built to tolerate partial history, so `Mandate.party` is optional and
`MandateSource` has an `UNRECORDED` member. Missing facts are modelled as absent
(`None`), never faked with placeholder values like `"unknown-party-id"` or `"???"`.

### Events, protocols, processes

Four terms, kept apart (full text in the README, "Approach"):

- **Event**: a dated fact from history (an election, a member leaving a caucus). Input,
  never logic. None exist yet.
- **Protocol**: an ordered tuple of **steps**. Each step is a frozen `Model` with
  `apply(state) -> state` and a `__call__` that forwards to it. Steps are **objects,
  never functions or lambdas**, so a protocol can be printed, compared, hashed,
  validated and stored as part of a law (`law/`). Parameters are fields with
  descriptions like any other model. `Protocol` is not used as a class name
  (`typing.Protocol`); protocols are type aliases such as `CaucusProtocol`.
- **Process**: applying a protocol step by step. *Internal* processes change one unit
  and are methods on it (`Chamber.form_caucuses(protocol)`: clear, then apply each
  step); *external* processes span several units or form a new one
  (`allocate(vote, protocol)`, forming a chamber from a popular vote).
- A counterfactual is the same event under a different protocol.

Processes depend on state, never the reverse: `wahlwerk.process` imports from
`wahlwerk.state`, and state modules import process types only under `TYPE_CHECKING`
(`Chamber.from_seats` imports `CaucusPerParty` inside the method for this reason).
Steps build their result through a validating helper (`Chamber.with_caucuses`), so
every step's output passes the model's invariants.

### Party registry: model here, data in wahlwerk-data

The engine knows what a party *is* (`Party`) and how the file *looks*
(`wahlwerk.io.parties`); which parties exist is data in
`wahlwerk-data/parties/<country>/<scope>.json`. A registry is passed explicitly, never
held in a global, because party names change over time. Load it with
`PartyRegistry.from_json(path)`. The reader rejects a missing or unknown `schema`,
duplicate JSON keys (which `json` would otherwise silently collapse) and unknown fields.

### Imports

Import from the defining module (`wahlwerk.model`, `wahlwerk.state.term`), never from
the package root or a sibling package's `__init__`, inside `src/wahlwerk`.

What each `__init__` exposes to users: **a package re-exports only its own modules, never
its subpackages' contents.** `wahlwerk.state.Chamber`, `wahlwerk.vote.popular.TallyRow`;
`process/`, `vote/` and `apportionment/` expose their modules or subpackages but not their names
(`wahlwerk.process.caucus.CaucusPerParty`), so the popular/chamber split stays visible.
The root exposes only the packages `apportionment`, `io`, `law`, `measure`, `party`, `process`, `state`, `vote` and
`setup_logger`, for `import wahlwerk as ww`: `ww.state.Chamber`, `ww.io.read_bundle`,
`ww.process.caucus.CaucusOfParties`. No model is flattened into the root;
`tests/test_root.py` pins it. Every caucus step's name starts with `Caucus`.
When a module in a lower layer needs a reader or process at call time
(`PartyRegistry.from_json`, `PopularVote.from_dir`), it imports it inside the method with a
comment saying why, so no two modules import each other at load time.

### General conventions

- **Paths are `pathlib.Path`, everywhere.** Never build or handle paths as strings. A
  function that takes a path accepts `str | Path` and converts on its first line:
  `file_path = Path(file_path)`.
- **`.get()` always returns something and never raises**: the value, or `default`
  (`None` unless given), like `dict.get`. Indexing (`registry["cdu"]`) is the lookup
  that raises, with a `KeyError` naming the missing key.
- **Alternative constructors are `from_*` classmethods, built in layers.** Each builds
  on the one below instead of repeating it: `party_id_of` (a `Party` or its id, to an
  id) feeds `Mandate.from_party(party)`, which feeds
  `Chamber.from_seats({party: seats})`. A `from_*` on a class returns **one** instance
  of that class; repeating it for a seat count is the caller's job. Deeper constructors
  (with origins, holders, units) reuse these. Wherever a party is accepted, take
  `Party | str` and normalise with `party_id_of`.
- **Booleans start with `is_` or `has_`** (strongly preferred), or `are_` / `have_`
  where the subject is plural; fields and properties alike: `Mandate.is_vacant`,
  `Chamber.is_empty`, `Chamber.has_caucuses`.
- **Aliases in function signatures document, they do not validate.** `seats: Seats` in
  a plain function is just `int` at runtime, so the function checks explicitly
  (`TypeError` for a non-`int` or a `bool`, `ValueError` for a negative), as
  `Chamber.from_seats` does. No `@validate_call`: it would silently coerce `"2"` and
  `2.0` to `2`.
- **Logging: `logger = logging.getLogger(__name__)` in each module that logs**, below
  `__all__`. The package is silent until the user calls `wahlwerk.log.setup_logger()`
  (only a `NullHandler` is attached, and no file is written unless asked for). Use lazy
  %-formatting (`logger.info("read %d parties", n)`), never f-strings. Levels: INFO for
  what a reader read and anything a constructor does implicitly (padding vacant seats);
  DEBUG for each process step; WARNING for data that is legal but suspicious. Errors
  are raised, not logged. When the *caller* can fix something that still ran (a
  protocol step naming a party without seats), use `warnings.warn` with a category
  such as `ProtocolWarning` and `stacklevel=2` instead: it shows in notebooks without
  `setup_logger`, and can be filtered or turned into an error. Logging is diagnostics only: no result may depend on it, and
  how a result was derived belongs in a trace (planned), not in the log. Tests that
  call `setup_logger` restore the package logger afterwards.
- **Reader errors are `ValueError` naming the file**: `f"{file_path}: ..."`, so a bad
  row in one of many source files can be found.

### Invariants go in `@model_validator(mode="after")`

Cross-field rules are enforced on the model, not by callers. `Term._check_order`
(start not before the election, ends not before start) is the pattern: raise
`ValueError` with a message naming the entity and both conflicting values.

### Declaring fields

The README section "Model fields" is the source of truth; in order of preference:

1. **Always `Field(default=..., description=...)`.** No bare `= 0`, no attribute
   docstrings, no undocumented field. A required field omits `default` but still has a
   `description`: `body: BodyId = Field(description="...")`.
2. **Use a shared alias for the type** (`Count`, `Seats`, `Share` from `model.py`;
   `Slug`, `DottedKey` from `ids.py`). The alias carries the constraint, `Field` adds
   only default and description. A constraint repeated three times wants an alias.
3. **Local constraints go in the same `Field`** only when the type cannot carry them:
   `ge`, `gt`, `min_length`, `pattern`, `discriminator`.
   `number: int | None = Field(default=None, ge=1, description=...)`.
4. **Empty container defaults use `default_factory`** with an immutable type:
   `default_factory=tuple`, `default_factory=frozenset`; never `list` or `dict`. Scalars
   and `None` keep `default=`.
5. **Never `Field(alias=...)` on a domain model.** Source column names (`Gruppe`,
   `Anzahl`, `Stimmart`) are mapped by the reader in `io/`, never in the model.
6. **Cross-field rules in `@model_validator(mode="after")`**, returning `self`, with a
   message naming the offending values: `f"cap {self.cap} is below minimum
   {self.minimum}"`, not `"invalid SeatTargets"`.
7. **Prefer a validator over a comment.** If a description says "must be", enforce it.
