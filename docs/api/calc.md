# Formulas (wahlwerk-calc)

`wahlwerk_calc` holds every formula of the engine, each written once: seat formulas,
quotas, thresholds, majorities, Überhang and Ausgleich, measures of a result, coalitions
and power. It is its own distribution, `wahlwerk-calc`, depending on numpy alone and on
nothing of wahlwerk; the engine computes with it, and `ww.calc` is the same package.

**Inputs and outputs are plain.** A mapping of key to number gives a mapping back, an
array gives an array, a 2-D array (or a mapping of key to a sequence) is several
scenarios at once:

```python
import wahlwerk_calc as wc

wc.divisor.sainte_lague({"a": 4160, "b": 3380, "c": 2200}, 10).seats   # {'a': 4, 'b': 4, 'c': 2}
wc.fragmentation.effective_number([0.40, 0.35, 0.15, 0.10])            # 3.17...
wc.power.banzhaf({"union": 208, "afd": 152, "spd": 120, "gruene": 85, "linke": 64, "ssw": 1})
chamber.apply(wc.coalition.minimal_winning)                            # on a Chamber, by caucus
```

**Exact in, exact out.** `int`, `Fraction`, decimal strings (`"32.5"`) and integer arrays
are computed exactly (a seat formula ranks in floating point and checks the last seat
exactly); floats in floating point. **Ties are results**: a seat formula returns a
{class}`~wahlwerk_calc.result.SeatResult` naming the tied keys and the open seats; the
engine's law steps stop on it until the lot is applied.

## Notation

Every formula on this page and on the website uses these symbols, from
{mod}`wahlwerk_calc.notation`.

```{include} ../_notation.md
```

## Layer 1: shares, quotas, the seat result

```{eval-rst}
.. automodule:: wahlwerk_calc.share
.. automodule:: wahlwerk_calc.quota
.. automodule:: wahlwerk_calc.result
```

## Layer 2: seat formulas

```{eval-rst}
.. automodule:: wahlwerk_calc.divisor
.. automodule:: wahlwerk_calc.remainder
.. automodule:: wahlwerk_calc.plurality
```

## Layer 3: clauses around them

```{eval-rst}
.. automodule:: wahlwerk_calc.majority
.. automodule:: wahlwerk_calc.threshold
.. automodule:: wahlwerk_calc.compensation
```

## Layer 4: measures of a result

```{eval-rst}
.. automodule:: wahlwerk_calc.proportionality
.. automodule:: wahlwerk_calc.fragmentation
```

## Layer 5: coalitions and power

```{eval-rst}
.. automodule:: wahlwerk_calc.coalition
.. automodule:: wahlwerk_calc.power
```

## Notation as data

```{eval-rst}
.. automodule:: wahlwerk_calc.notation
```
