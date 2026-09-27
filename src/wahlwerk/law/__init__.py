"""Laws: electoral laws in force per date, each version a protocol.

Sorted by jurisdiction, jurisdiction first as in body ids: ``law/de/st/lwg.py`` holds
the versions of the Wahlgesetz of Sachsen-Anhalt. A law is rules, not recorded data, so
it lives in the engine, is type-checked with it, and is what golden tests replay.

Modules, exposed but never flattened: ``base`` (:class:`~wahlwerk.law.base.Law`,
:class:`~wahlwerk.law.base.LawRegistry`), ``registry`` (``LAWS``, every known version)
and ``de`` (the laws themselves). This package uses ``process`` and ``apportionment``;
nothing in the engine imports it.
"""

from __future__ import annotations

from wahlwerk.law import base, de, registry

__all__ = ["base", "de", "registry"]
