# Golden fixture: Landtag Mecklenburg-Vorpommern, 4 September 2011

The input and the official result for the golden test
[`tests/golden/test_de_landtag_mv.py`](../test_de_landtag_mv.py), committed so the test
runs offline and never reads wahlwerk-data. There is no Überhang: the SPD won 24 Wahlkreise and the CDU 12, both within their entitlement.

| File | What | Source |
|---|---|---|
| `election.toml`, `tally.csv` | a bundle (schema 2): the valid Erst- and Zweitstimmen per Wahlkreis and party, Urne and Brief summed; 817 rows | the Wahlbezirk file, via wahlwerk-data `elections/de/landtag/mv/2011` |
| `mandate.csv` | the official Mandate der Parteien, per Wahlkreis and for the Land, byte for byte (ISO-8859-1, `;`) | the Landeswahlleitung's `L_Mandate.csv` |

## Sources

- **Votes:** Landesamt für innere Verwaltung Mecklenburg-Vorpommern, *Wahl zum Landtag von Mecklenburg-Vorpommern am 4. September 2011: endgültiges Ergebnis der Wahlbezirke (20.09.2011, 10:28 Uhr)*,
  <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2011/Ergebnisse/L_Wahlbezirke.csv>, retrieved 2026-09-27, SHA-256 `964f6036a0bbf9e0cf4461e97595fca76932f604896bcb3d8b24c6a4ad6029ad`.
  The full attribution is in `election.toml`.
- **Seats:** Landesamt für innere Verwaltung Mecklenburg-Vorpommern, *Mandate der Parteien*, endgültiges Ergebnis
  computed on 20 September 2011, <https://www.laiv-mv.de/static/LAIV/Wahlen/2-Landtagswahlen/2011/Ergebnisse/L_Mandate.csv>, retrieved 2026-09-27, SHA-256
  `6e848181093c48d63ae3305874bbf65721a2d500543db6e018b067308ac5d4e7`. The result: SPD 27, CDU 18, DIE LINKE 14, GRÜNE 7, NPD 5; 71 seats, 36 of them from Wahlkreise; no Überhang.

No licence is stated for either file, only the publisher's name. The votes were changed:
reshaped into a long table and summed per Wahlkreis over Urnen- and Briefwahl. The seat
file is unchanged.

## The law

The election was held under the LKWG M-V (`wahlwerk.law.de.mv.lkwg.LKWG_2011`), whose
Sec. 54 (2), 57 and 58 are unchanged since 1 January 2011: at least 71 seats, 36
Wahlkreise, Hare/Niemeyer with a majority clause, and the Ausgleich of Sec. 58 (6).

## How `tally.csv` was made

As for Sachsen-Anhalt (see `../de.landtag.st.2026/README.md`), from the wahlwerk-data bundle:

```python
vote = PopularVote.from_key("de.landtag.mv.2011", "../wahlwerk-data")
votes = vote.tally.filter(kind="votes").sum_to("wahlkreis")
votes.sum_by("unit", "section", "party", "candidate")  # one row each, channel left blank
```

Invalid votes, Wahlberechtigte and Wähler are left out: the seat allocation does not use
them.
