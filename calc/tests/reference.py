"""Slow, obvious implementations to check the fast ones against."""

from __future__ import annotations

import itertools
import math
from fractions import Fraction


def divisor_seats(votes, seats, post):
    """Rank every claim v / post(k) exactly; return (seats, tied set, open)."""
    claims = []
    for key, v in votes.items():
        for k in range(seats):
            p = post(k)
            claims.append((math.inf if (p == 0 and v) else (Fraction(v) / p if p else 0), key))
    return _largest(claims, seats, list(votes))


def largest_remainder_seats(votes, seats, quota):
    total = sum(votes.values())
    q = quota(Fraction(total), seats)
    parts = {k: Fraction(v) / q for k, v in votes.items()}
    whole = {k: math.floor(p) for k, p in parts.items()}
    if not 0 <= seats - sum(whole.values()) <= len(votes):
        return None
    won, tied, left = _largest([(parts[k] - whole[k], k) for k in votes], seats - sum(whole.values()), list(votes))
    return {k: whole[k] + won[k] for k in votes}, tied, left


def _largest(claims, count, keys):
    won = dict.fromkeys(keys, 0)
    if count == 0:
        return won, set(), 0
    edge = sorted((c for c, _ in claims), reverse=True)[count - 1]
    above = [k for c, k in claims if c > edge]
    at = [k for c, k in claims if c == edge]
    for k in above:
        won[k] += 1
    if len(above) + len(at) == count:
        for k in at:
            won[k] += 1
        return won, set(), 0
    return won, set(at), count - len(above)


def swings(weights, quota):
    n = len(weights)
    eta = [0] * n
    for i in range(n):
        others = [j for j in range(n) if j != i]
        for r in range(n):
            for c in itertools.combinations(others, r):
                w = sum(weights[j] for j in c)
                if w < quota <= w + weights[i]:
                    eta[i] += 1
    return eta


def shapley_shubik(weights, quota):
    n = len(weights)
    pivots = [0] * n
    for order in itertools.permutations(range(n)):
        w = 0
        for i in order:
            w += weights[i]
            if w >= quota:
                pivots[i] += 1
                break
    return [Fraction(p, math.factorial(n)) for p in pivots]
