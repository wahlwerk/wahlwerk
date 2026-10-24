# References

Three kinds of source, each from its own home; wahlwerk-site reads the same three, so the
reference and the site cite the same records.

## Literature

Books, papers, judgments, from `docs/references.bib`: exported from Zotero (Better
BibLaTeX, keys `{first author}.{ThreeWordTitle}.{year}`); edit the entry in Zotero, never
the file. A docstring cites an entry with ``:cite:`key` ``.

```{bibliography}
:all:
```

## Statutes

One row per version. A statute the engine implements is its `Law` object
(`wahlwerk.law`); one it only cites is in `docs/statutes.toml`. Cited inline in the
form of its own system, with the provision: `Art. 63 (2) GG`, `Sec. 35 (8) LWG LSA`.

```{include} _statutes.md
```

## Data

Every election bundle records its own source (publisher, title, URL, licence,
attribution, retrieval date, SHA-256) in its `election.toml`; `PopularVote.source`
keeps it. The golden test fixtures name theirs in `tests/golden/<bundle key>/README.md`.
