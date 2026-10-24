r"""The symbols every formula uses, one meaning each.

The API reference and the website print this table and use only these symbols, so a
formula reads the same in a docstring, the reference and on the site. Indices: :math:`i`
and :math:`j` run over options (parties, caucuses, Länder), :math:`k` over seats of one option.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["SYMBOLS", "Symbol"]


@dataclass(frozen=True)
class Symbol:
    """One symbol: its LaTeX, what it stands for, and the group it belongs to."""

    latex: str
    meaning: str
    group: str


SYMBOLS: tuple[Symbol, ...] = (
    Symbol(r"i, j", "an option: what is voted for or apportioned to; a party, a candidate, a caucus, a Land", "options"),
    Symbol(r"n", "the number of options", "options"),
    Symbol(r"v_i", "the votes (or any weight) of option i", "votes"),
    Symbol(r"V = \sum_i v_i", "the total votes", "votes"),
    Symbol(r"p_i = v_i / V", "the vote share of option i", "votes"),
    Symbol(r"s_i", "the seats of option i", "seats"),
    Symbol(r"S = \sum_i s_i", "the seats to give: the chamber size", "seats"),
    Symbol(r"q_i = s_i / S", "the seat share of option i", "seats"),
    Symbol(r"m_i", "the minimum seats of option i, e.g. Wahlkreise won outright", "seats"),
    Symbol(r"Q", "a quota: the votes one seat is worth", "methods"),
    Symbol(r"D", "a divisor: the votes per seat that rounds to the chamber size", "methods"),
    Symbol(r"\sigma(k)", "a signpost: where a quotient rounds up from k to k + 1 seats", "methods"),
    Symbol(r"\theta", "a legal threshold, as a share of the votes", "methods"),
    Symbol(r"M", "the members a majority is reckoned on", "majorities"),
    Symbol(r"\operatorname{maj}(M) = \lfloor M/2 \rfloor + 1", "a majority of M", "majorities"),
    Symbol(r"C", "a coalition: a set of options", "majorities"),
    Symbol(r"w(C) = \sum_{i \in C} s_i", "the seats of a coalition", "majorities"),
    Symbol(r"T", "the quota of a weighted vote: the seats a coalition needs", "majorities"),
    Symbol(r"\eta_i", "the coalitions for which option i is pivotal (swings)", "power"),
    Symbol(r"\beta_i, \phi_i", "the Banzhaf and Shapley-Shubik indices of option i", "power"),
    Symbol(r"H, N", "concentration (Herfindahl) and the effective number of options", "measures"),
)
"""Every symbol, in the order the reference lists them."""
