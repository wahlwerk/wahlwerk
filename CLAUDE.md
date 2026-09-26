# wahlwerk

`wahlwerk` models electoral and parliamentary systems as rules-as-code: a deterministic
engine parameterised by an electoral law, so small changes to the law can be replayed
against real historical votes.

**Status:**
...

**There is no law implementation.** Nothing is *derived*: `Chamber.from_archive(...)`
reads a published result, it does not compute one. Event `apply` methods raise
`NotImplementedError` naming the milestone they land in; that is deliberate, not an
oversight. Do not implement one slot ahead of its milestone to make a demo work.

## Commands

```bash
uv sync
uv run pytest -q                   # tests
uv run mypy                        # strict; src and tests
uv run ruff check . && uv run ruff format .
uv run python -m wahlwerk.examples.bundestag_2025
```

All four must pass before anything is called done. mypy has no `python_version` pin —
the CI matrix runs it on 3.11, 3.12 and 3.13, which checks compatibility for real.

The engine has **no** jupyter or matplotlib dependency and must not grow one; notebooks
live in wahlwerk-execute.

## Language policy

English is the language of code; German electoral law is the subject matter.

## Project state

The project is a skeleton and **does not currently import**. Before relying on any
module, expect to fix wiring. Known breaks as of this writing:

- `wahlwerk/__init__.py` imports `Share` and `SlotModel` from `wahlwerk.model`; neither
  is defined there. This one error blocks every import of the package.
- `wahlwerk/ids.py` defines only `Slug`, `DottedKey`, `BodyId`. The mandate modules
  import `CandidateId`, `LevelName`, `PartyId`, `UnitId` from it.
- `state/caucus.py` imports from `wahlwerk.models` (no such module) and its validator
  reads `self.members`, which is commented out of the model.
- `state/chamber.py` annotates `mandates` with `Mandate` without importing it.
- `mandate/mandate.py` declares class `Mandate` with a docstring and no fields, and
  exports `MandateSource`, which actually lives in `mandate/mandate_origin.py`.
  `mandate/__init__.py` is empty, so nothing under `wahlwerk.mandate` is re-exported.
- `state/term.py` imports `Model` from the package root rather than `wahlwerk.model`,
  which re-enters `__init__.py` during package initialisation.
- `pyproject.toml` has no `[build-system]`, so uv treats this as a virtual project and
  `src/wahlwerk` is **not** installed into `.venv`. `uv run python -c "import wahlwerk"`
  fails with `ModuleNotFoundError` for that reason alone.
- `tests/` is empty and pytest is not a dependency.
- `main.py` is the `uv init` placeholder and has nothing to do with `src/wahlwerk`.

Module docstrings reference `wahlwerk.events.base.BodyState`, `wahlwerk.ballots.TallyKey`
and `wahlwerk.apportionment.base`. None of those exist yet; they describe the intended
shape of the system, not current code.

## Commands

The project uses [uv](https://docs.astral.sh/uv/) (`uv.lock` is committed, Python 3.10).

```bash
uv sync                                    # create/refresh .venv from the lockfile
uv add <pkg>                               # add a runtime dependency
uv add --dev <pkg>                         # add a dev dependency (e.g. pytest)

# src/ is not on sys.path until a [build-system] is added to pyproject.toml.
# Until then, reach the package explicitly:
PYTHONPATH=src uv run python -c "import wahlwerk"
```

There is no configured test runner, linter, or formatter yet. Adding
`[build-system]` (hatchling with `packages = ["src/wahlwerk"]`) plus a `pytest` dev
dependency is the natural first step, after which `uv run pytest` and
`uv run pytest tests/test_x.py::test_name` work normally.

## Sibling repositories

Three repos, cloned side by side:

```
CODE/wahlwerk_/
  wahlwerk/          the engine       Apache-2.0     ← you are here
  wahlwerk-data/     the archive      dl-de/by-2-0
  wahlwerk-execute/  notebooks        depends on both
```


## Architecture

### Everything inherits from `Model`

`src/wahlwerk/model.py` defines the single pydantic base class. Its configuration is
load-bearing and its docstring is the authoritative explanation; the short version:

- `frozen=True` -- state is inert. Only events produce new state, and frozen models are
  hashable, which is what lets them be used as dictionary keys in tallies.
- `extra="forbid"` -- a misspelled column in a source file from one of sixteen
  Landeswahlleiter is a hard error, not a silently dropped field.
- `validate_default=True` -- defaults cannot dodge invariants.
- `use_attribute_docstrings=True` -- is set, but fields are **not** documented with
  attribute docstrings. Every field uses `Field(default=..., description=...)` (see
  "Declaring fields" below); an explicit `description` takes precedence over a docstring.
  Existing code that uses attribute docstrings should be migrated.

pydantic does not deep-freeze containers. Use `tuple` and `frozenset` for any field that
is part of a model's identity, never `list` or `dict`.

### Exact arithmetic only

Vote counts and seat counts are `Count`/`Seats` (`int`, `ge=0`). Shares are exact
`fractions.Fraction` bounded to `[0, 1]`. **Never `float`.** Apportionment methods
(Sainte-Laguë, d'Hondt, and the tie and rounding rules around them) are only reproducible
against official results under exact rational arithmetic.

### Identifiers are strings, not objects

`src/wahlwerk/ids.py` builds every identifier from one regex: a `Slug` is lowercase ASCII
with inner hyphens or underscores (`zweitstimme`, `cdu-csu`). A `DottedKey` joins slugs
with dots, **narrowest scope last**: `de.bund.wk.001`, `de.bund.bundestag`, `de.by.landtag`.
New id types are `NewType`s over `DottedKey`, following `BodyId`.

### State vs. events

`src/wahlwerk/state/` holds standing, inert data that only events may replace: `Term`
(a Wahlperiode of a body), `Chamber` (the set of mandates constituting a body at a point
in time), `Caucus` (a Fraktion: a grouping over mandates with its own membership rules,
deliberately distinct from a party, hence `parties` is a set). `Mandate` lives at the top
level under `src/wahlwerk/mandate/` rather than in `state/`, because a seat and its origin
are referenced from outside standing state.

Models are built to tolerate partial history. A chamber reconstructed from a published
seat distribution knows the party and nothing else; a seat between a Vacancy and the
Nachrücken that fills it has no holder. That is why `Mandate`'s person/unit/level are
optional, why `Caucus` carries a `declared_size` for aggregate-only records (validated
against `members` when both are present), and why `MandateSource` has an `UNRECORDED`
member. Missing facts are modelled as absent, not faked.

### Invariants go in `@model_validator(mode="after")`

Cross-field rules are enforced on the model, not by callers. `Term._check_order`
(start not before the election, ends not before start) and `Caucus._check_size` are the
pattern: raise `ValueError` with a message naming the entity and both conflicting values.

### Declaring fields

The README section "Model fields" is the source of truth; in order of preference:

1. **Always `Field(default=..., description=...)`.** No bare `= 0`, no attribute
   docstrings, no undocumented field. A required field omits `default` but still has a
   `description`: `party: PartyId = Field(description="...")`.
2. **Use a shared alias for the type** (`Count`, `Seats`, `Share` from `model.py`;
   `Slug`, `DottedKey`, `LawId` from `ids.py`). The alias carries the constraint,
   `Field` adds only default and description. A constraint repeated three times wants
   an alias. (`Share` and `LawId` are referenced but not yet defined.)
3. **Local constraints go in the same `Field`** only when the type cannot carry them:
   `ge`, `gt`, `min_length`, `pattern`, `discriminator`.
   `votes_per_voter: int = Field(default=1, ge=1, description=...)`.
4. **Immutable defaults**: `default=()`, `default=frozenset()`; no `default_factory`.
5. **Never `Field(alias=...)` on a domain model.** Source column names (`Gruppe`,
   `Anzahl`, `Stimmart`) are mapped by the reader in `io/`, never in the model.
6. **Cross-field rules in `@model_validator(mode="after")`**, returning `self`, with a
   message naming the offending values: `f"cap {self.cap} is below minimum
   {self.minimum}"`, not `"invalid SeatTargets"`.
7. **Prefer a validator over a comment.** If a description says "must be", enforce it.
