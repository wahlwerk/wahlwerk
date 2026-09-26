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
| `model.py` | `Model` base; aliases `Count`, `Seats`, `Share` |
| `ids.py` | `Slug`, `DottedKey`; ids `BodyId`, `CandidateId`, `PartyId`, `CaucusId`, `MandateId` |
| `log.py` | `setup_logger(file_path=None, *, level, console)` (file only when given), `disable_logging`, `LOGGER_NAME`; the root adds a `NullHandler` |
| `party/` | `Party` (`id`, `name`, `short_name`), `PartyRegistry` (`[id]`, `.get()`, `.from_json()`) |
| `io/` | `read_parties`: reads a party registry file from wahlwerk-data |
| `state/` | `Mandate` (`id`, `party`, `origin`, `is_vacant`; derived `has_party`; `from_party(party, id)`), `MandateOrigin` (`source`), `MandateSource` enum; `Term` (with `_check_order`; derived `is_ended`, `is_ended_early`), `Caucus` (`id`, `mandates`: mandate ids; `size`; no names) with `NON_ATTACHED`, `Chamber` (`term`, `mandates`, `caucuses`, `minimum_mandates`, `are_caucuses_recorded`; validates mandate ids unique and caucuses against mandates; derived `body`, `size`, `is_empty`, `has_caucuses`, `seats_without_caucus`, `non_attached_seats`, `seats_by_caucus`, `get_caucuses(include_non_attached=False)`, `vacant_seats`, `filled_seats`, `is_below_minimum`/`is_at_minimum`/`is_above_minimum`, `seats_by_party`; `from_seats`, `with_caucuses`; processes `clear_caucuses`, `form_caucuses`; display `__repr__`, `_repr_html_`, `fancy_html`) |
| `process/` | `CaucusStep` (abstract, callable), `CaucusProtocol` (tuple of steps), `CaucusPerParty`, `GroupParties` (`parties`, `id`; warns on missing parties), `ProtocolWarning` |

**There is no law implementation.** There are no events, ballots, tallies, apportionment, or archive discovery (`find_archive`) yet. The README describes
the target system; where it names something (`LawId`, `Tie`, `tests/golden/`), check this
table before assuming it exists.

Tests live in `tests/`, mirroring `src/wahlwerk/`. Tests that read files write their own
small fixture to `tmp_path`; they never read wahlwerk-data.

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

Four repos, cloned side by side:

```
CODE/wahlwerk_/
  wahlwerk/          the engine       Apache-2.0     <- you are here
  wahlwerk-data/     the archive      dl-de/by-2-0
  wahlwerk-execute/  notebooks        depends on both
  wahlwerk-ui/       charts           no dependencies; optional extra of the engine
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
| `process/` | processes | steps, protocols, and the processes that apply them |
| `io/` | readers | the only place that knows source file formats |
| `event/`, `law/` | later | dated facts; protocols in force per date |

No grab-bag folders (`basics/`, `core/`, `common/`, `utils/`). Dependencies point one
way, and a module imports only from layers to its left:

```
foundation  <-  entities  <-  state  <-  process
                   ^            ^
                   io ----------+
```

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
`vacant.001`), and ids from real results will come from how the seat was won
(`wk.001`). A `Caucus` has an `id` (`CaucusId`, a slug unique within its chamber) and
**no names**: names belong to `Party`, and parties stay separate from caucuses, so a
caucus never copies or combines party names. It holds `mandates`, the ids of its seats, and
`Chamber._check_caucuses` keeps the two from disagreeing: no caucus is empty, every
mandate id exists in the chamber, is filled, and sits in at most one caucus.
`GroupParties` accepts `Party` objects or ids and names the caucus by the party ids
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
  validated and later stored as part of a law. Parameters are fields with
  descriptions like any other model. `Protocol` is not used as a class name
  (`typing.Protocol`); protocols are type aliases such as `CaucusProtocol`.
- **Process**: applying a protocol step by step. *Internal* processes change one unit
  and are methods on it (`Chamber.form_caucuses(protocol)`: clear, then apply each
  step); *external* processes span several units or form a new one.
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
the package root or a sibling package's `__init__`, inside `src/wahlwerk`. The root
`__init__` imports everything, so importing from it re-enters package initialisation.

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
