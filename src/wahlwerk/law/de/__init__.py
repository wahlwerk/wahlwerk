"""Laws of Germany, one package per jurisdiction: ``bund`` and the Länder by their
two-letter code (``st`` for Sachsen-Anhalt), as in :data:`~wahlwerk.ids.BodyId`."""

from __future__ import annotations

from wahlwerk.law.de import bund, st

__all__ = ["bund", "st"]
