"""Measures: numbers computed from results for analysis, never input to a law.

Each kind of measure is its own module, reached through this package but never
flattened into it: ``wahlwerk.measure.proportionality.loosemore_hanby``. Measures depend
only on the foundation and take plain mappings of key to number, so they apply to any
result: ``Apportionment.as_dict()``, ``Chamber.seats_by_party`` or a published table.
"""

from __future__ import annotations

from wahlwerk.measure import proportionality

__all__ = ["proportionality"]
