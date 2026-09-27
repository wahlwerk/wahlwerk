"""A popular vote as recorded: its tally, and where the tally came from.

A :class:`PopularVote` is what the electorate recorded in one election or referendum:
the :class:`Tally`, together with the :class:`Source` it was normalised from. The source
travels with the rows, so the attribution the licence requires is kept with anything
built from them.

A popular vote is input: it holds no law and forms no chamber. Getting from its tally
to a chamber is a process in :mod:`wahlwerk.process`, which reads it. On disk, in
wahlwerk-data, a popular vote is stored as a *bundle* directory, read by
:func:`wahlwerk.io.bundle.read_bundle`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pydantic import Field, model_validator

from wahlwerk.model import Model
from wahlwerk.vote.popular.hierarchy import Hierarchy
from wahlwerk.vote.popular.tally import Tally

__all__ = ["PopularVote", "Source"]


class Source(Model):
    """The original publication a popular vote was normalised from.

    The original file is not committed; its URL, retrieval date and SHA-256 make the
    normalised tally reproducible without it.
    """

    publisher: str = Field(
        min_length=1,
        description="Who published the original, e.g. ``Statistisches Landesamt Sachsen-Anhalt``.",
    )
    title: str = Field(
        min_length=1,
        description="The title of the original publication.",
    )
    url: str = Field(
        pattern=r"^https?://\S+$",
        description="Where the original was retrieved from.",
    )
    licence: str = Field(
        min_length=1,
        description="The licence of the original, e.g. ``dl-de/by-2-0``.",
    )
    attribution: str = Field(
        min_length=1,
        description="The attribution text the licence requires, verbatim.",
    )
    retrieved: date = Field(
        description="The day the original was retrieved.",
    )
    sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the original file, lowercase hex.",
    )


class PopularVote(Model):
    """One popular vote's tally and the source it was normalised from."""

    source: Source = Field(
        description="The original publication the tally was normalised from.",
    )
    tally: Tally = Field(
        default_factory=Tally,
        description="Every counted row of the vote, in file order.",
    )
    hierarchies: tuple[Hierarchy, ...] = Field(
        default_factory=tuple,
        description=(
            "Hierarchies beside the tally's main one, for analysis, e.g. the "
            "administrative one (Land, Kreis, Gemeinde); each covers every counted unit."
        ),
    )

    @model_validator(mode="after")
    def _check_hierarchies(self) -> PopularVote:
        names = [hierarchy.name for hierarchy in self.hierarchies]
        if len(set(names)) != len(names):
            raise ValueError(f"hierarchies {names} name a hierarchy more than once")
        counted = {row.unit for row in self.tally.rows}
        for hierarchy in self.hierarchies:
            missing = counted - {entry.unit for entry in hierarchy.units}
            if missing:
                raise ValueError(
                    f"hierarchy {hierarchy.name!r} does not cover {len(missing)} counted "
                    f"units, e.g. {min(missing)!r}"
                )
        return self

    def hierarchy(self, name: str) -> Hierarchy:
        """The hierarchy called ``name``; raises ``KeyError`` naming it if there is none."""
        for hierarchy in self.hierarchies:
            if hierarchy.name == name:
                return hierarchy
        raise KeyError(f"no hierarchy {name!r}; expected one of {[h.name for h in self.hierarchies]}")

    # ===========================================================
    # Constructors
    # ===========================================================
    @classmethod
    def from_dir(
        cls,
        dir_path: str | Path,
        election_file_name: str = "election.toml",
        tally_file_name: str = "tally.csv",
    ) -> PopularVote:
        """Load the popular vote stored in a bundle directory, as kept in wahlwerk-data.

        The format is read by :func:`wahlwerk.io.bundle.read_bundle`; the file names
        default to its :data:`~wahlwerk.io.bundle.ELECTION_FILE` and
        :data:`~wahlwerk.io.bundle.TALLY_FILE`.
        """
        # wahlwerk.io.bundle imports PopularVote at load time; importing it here instead
        # avoids a circular import.
        from wahlwerk.io.bundle import read_bundle

        return read_bundle(Path(dir_path), election_file_name, tally_file_name)

    @classmethod
    def from_key(
        cls,
        key: str,
        data_dir: str | Path,
        election_file_name: str = "election.toml",
        tally_file_name: str = "tally.csv",
    ) -> PopularVote:
        """Load the popular vote ``key`` from the wahlwerk-data clone at ``data_dir``.

        ``PopularVote.from_key("de.landtag.st.2026", "../wahlwerk-data")`` reads
        ``../wahlwerk-data/elections/de/landtag/st/2026``; the key is turned into a
        directory by :func:`wahlwerk.io.bundle.resolve_election_dir`, then read by
        :meth:`from_dir`.
        """
        # See from_dir: wahlwerk.io.bundle imports PopularVote at load time.
        from wahlwerk.io.bundle import resolve_election_dir

        return cls.from_dir(
            resolve_election_dir(Path(data_dir), key), election_file_name, tally_file_name
        )
