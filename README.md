# wahlwerk

Electoral and parliamentary systems as **rules-as-code**: a deterministic engine
parameterised by an electoral law, so that small changes to the law can be evaluated
against real historical votes.

Scope covers all legislative levels, plus the derived bodies.

## Repositories

Three, split along the lines that actually differ — licence, size and change cadence:

| Repo | Holds | Why separate |
|---|---|---|
| [**wahlwerk**](https://github.com/wahlwerk/wahlwerk) | the engine | Apache-2.0, small, `pip install`-able |
| [**wahlwerk-data**](https://github.com/wahlwerk/wahlwerk-data) | normalised election bundles | dl-de/by-2-0, grows per election, must never bloat the engine's clone |
| [**wahlwerk-execute**](https://github.com/wahlwerk/wahlwerk-execute) | notebooks and analyses | depends on both; its output is figures, not a library |

The engine does **not** depend on the data repo, and its test suite passes with the
archive absent — anything that reads a bundle builds a synthetic one in a `tmp_path`, and
the real archive is exercised on the other side, in wahlwerk-data's own tests. When golden
tests arrive at M1 their fixtures will be committed here under `tests/golden/`, small and
gzipped, so **CI runs offline and a golden test never fails for network reasons**.

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
| `LawId` | dotted, `+slot` for variants | `de.bund.bwahlg.2023`, `de.bund.bwahlg.2023+apportionment` |
| `UnitId` | dotted | `de.bund.land.01`, `de.bund.wk.001` |
| `PartyId` | dotted | `cdu`, `gruene`, `team-todenhoefer` |
| `LevelName` | single segment | `wahlkreis`, `land`, `bund` |

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
  [Model fields](#model-fields).
  See [`model.py`](src/wahlwerk/model.py) and [`tests/test_validation.py`](tests/test_validation.py).
- **Exact arithmetic.** Divisor comparisons use `fractions.Fraction` or scaled integers,
  never floats. Float rounding both hides real ties and manufactures fake ones.
- **Ties are a result, not an error.** Where the law prescribes lots (Losentscheid), the
  engine returns an explicit [`Tie`](src/wahlwerk/ties.py) rather than letting sort order
  decide. `RecordedLot` replays a draw that actually happened.
- **One long table for all vote data.** A tally is a flat sequence of rows —
  `unit, section, party, candidate, count`. Cumulation is a bigger count; panachage is
  more rows; a new Land quirk is new rows, never new columns. That table is also
  literally one CSV file, which is what makes the archive format and the in-memory
  format the same thing.
- **Golden tests are the product.** Every historical election under every implemented law
  becomes a test asserting the official seat distribution exactly — party by party, Land
  list by Land list.
- **No bulk data in the repository.** Vote data lives in `wahlwerk-data`, which records
  each source's URL, retrieval date and SHA-256 so a bundle is reproducible without
  committing the multi-megabyte original. Fixtures committed here stay small and clearly
  sourced. What *is* shipped is reference data — the party registry, ~40 rows.


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
   `DottedKey`, `LawId`. The alias carries the constraint; `Field` only adds the default
   and description. If the same constraint appears three times, it wants an alias, not
   three `Field(ge=0, ...)`.
3. **Put a local constraint in the same `Field`** only when the type cannot carry it:
   `ge`, `gt`, `min_length`, `pattern`, `discriminator`.
   `votes_per_voter: int = Field(default=1, ge=1, description=...)` is right; the
   constraint is local and does not recur.
4. **Defaults are immutable**: `default=()`, `default=frozenset()`, never a `list` or
   `dict`. Pydantic copies defaults anyway, so `default_factory` is noise.
5. **Never `Field(alias=...)` on a domain model.** Source column names (`Gruppe`,
   `Anzahl`, `Stimmart`) are mapped in the reader in `io/`, not smuggled into the model.
   Otherwise the domain vocabulary silently becomes whichever Landeswahlleiter was
   parsed first.
6. **Cross-field rules go in `@model_validator(mode="after")`**, returning `self`, with
   a message that names the offending values: `f"cap {self.cap} is below minimum
   {self.minimum}"`. Not `f"invalid SeatTargets"`.
7. **Prefer a validator over a comment.** If a description says "must be", make it must
   be.


  ## Build order

  empty

  ## Development

```bash
uv sync
uv run pytest        # tests
uv run mypy          # strict, src and tests
uv run ruff check .  # lint
uv run ruff format . # format
```

## Non-goals
- **Forecasting.** Predicting vote shares is a separate and much weaker discipline; the
  counterfactual engine needs none of it to be useful.
- **Simulating the Bundesverfassungsgericht.** Judicial review is modelled as a
  *constraint checker* over law configurations, never as an agent.
- **Voter behaviour models.** Votes are inputs, historical or sampled.


## Data and attribution

No election data is committed here.

Results are generally published under Datenlizenz Deutschland (dl-de/by-2-0), which
requires attribution. Every bundle in `wahlwerk-data` carries its publisher, title, URL,
licence and attribution in `election.toml`, and `Bundle.source` keeps them — so the
attribution travels with anything republished from it rather than being left behind at the
read. Planned sources: `bundeswahlleiterin.de`, the sixteen Landeswahlleiter,
`dip.bundestag.de`, and `wahlrecht.de` as an independent check on the allocation
algorithms.

## Licence