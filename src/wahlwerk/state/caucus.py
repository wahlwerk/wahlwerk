"""A Fraktion: a grouping over mandates, and non-attached seats, which are in none.

**Non-attached** means a filled seat whose holder belongs to no caucus: fraktionslos in
the Bundestag, Non-Inscrits in the European Parliament, whose English term this is. It
is a relation between a seat and a chamber's caucuses, not a property of the seat, so it
is never stored on :class:`~wahlwerk.state.mandate.Mandate`; the chamber counts it.
Not "independent", which means elected without a party.
"""

from __future__ import annotations

from pydantic import Field

from wahlwerk.ids import CaucusId, MandateId
from wahlwerk.model import Model

__all__ = ["NON_ATTACHED", "Caucus"]

NON_ATTACHED = "non-attached"
"""Key for non-attached seats: in a seat table, the count of those whose party is not
given; as a caucus id, the imaginary caucus they appear as.

Reserved in :meth:`Chamber.from_seats <wahlwerk.state.chamber.Chamber.from_seats>`, so no
party may use it as its id, and in a chamber, so no real caucus may use it either.
"""


class Caucus(Model):
    """A grouping over the mandates of a chamber, with its own membership rules.

    Deliberately distinct from a party: one caucus can span several parties. A caucus
    points at seats by their :attr:`Mandate.id <wahlwerk.state.mandate.Mandate.id>`, it
    does not own them. It carries no names: those belong to the parties, which stay
    separate. The chamber checks that it has mandates, that each is a filled seat in it,
    and that each sits in at most one caucus.
    """

    id: CaucusId = Field(
        description="The key of the caucus, unique within its chamber, e.g. ``cdu-csu``.",
    )
    mandates: frozenset[MandateId] = Field(
        default_factory=frozenset,
        description="The ids of the chamber's mandates whose seats are in the caucus.",
    )

    # ===========================================================
    # Properties
    # ===========================================================
    @property
    def size(self) -> int:
        """The number of seats in the caucus."""
        return len(self.mandates)
