"""Readers: the only place that knows source file formats."""

from __future__ import annotations

from wahlwerk.io.bundle import read_bundle, resolve_election_dir
from wahlwerk.io.parties import read_parties

__all__ = ["read_bundle", "read_parties", "resolve_election_dir"]
