# wahlwerk-calc

The formulas of electoral systems, each written once: seat formulas (divisor, largest
remainder, plurality), quotas, thresholds, majorities, Überhang and Ausgleich,
disproportionality, fragmentation, coalitions and power indices.

Plain numbers or numpy arrays in, plain numbers or arrays out:

```python
import wahlwerk_calc as wc

wc.divisor.sainte_lague({"a": 4160, "b": 3380, "c": 2200}, 10).seats   # {'a': 4, 'b': 4, 'c': 2}
wc.divisor.d_hondt([[47, 16, 15, 6], [10, 10, 10, 10]], [10, 4]).seats  # two scenarios at once
wc.fragmentation.effective_number([0.40, 0.35, 0.15, 0.10])             # 3.17...
wc.power.banzhaf({"a": 50, "b": 49, "c": 1})                            # exact fractions
```

- **Exact in, exact out.** `int`, `Fraction`, decimal strings (`"32.5"`) and integer
  arrays are computed exactly; floats in floating point.
- **Ties are results.** A seat formula returns a `SeatResult` naming the tied keys and the
  seats left to the lot; it never lets order decide.
- **One notation.** Every formula uses the symbols of `wahlwerk_calc.notation`.

It depends on numpy alone and on nothing of wahlwerk. The
[wahlwerk](https://github.com/wahlwerk/wahlwerk) engine computes with it, and its API
reference and website render the formulas from the docstrings here.
