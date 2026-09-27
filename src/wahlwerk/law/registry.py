"""Every law the engine knows, in one registry."""

from __future__ import annotations

from wahlwerk.law.base import LawRegistry
from wahlwerk.law.de.mv.lkwg import LKWG_2011
from wahlwerk.law.de.st.lwg import LWG_2021

__all__ = ["LAWS"]

LAWS = LawRegistry(laws=(LKWG_2011, LWG_2021))
"""Every registered law version: ``LAWS["de.st.lwg.2021"]``,
``LAWS.in_force("de.st.landtag", date(2021, 6, 6))``."""
