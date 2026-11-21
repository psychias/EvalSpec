"""The statistics the experiment analyses share, in plain Python (no SciPy needed).

    eta_squared(groups)          share of the variance that lies between the groups
    oneway_anova(groups)         F, p, eta squared and degrees of freedom
    f_sf(F, d1, d2)              P(F > f) of the F distribution
    chi2_sf(x, k)                P(X > x) of the chi-square distribution
    friedman(matrix)             Friedman statistic and Kendall's W for blocked ratings

A group is a list of numbers; `groups` is a list of groups. `matrix` has one row per
block (a response, a model) and one column per treatment (a judge, a prompt format).
"""
from __future__ import annotations

import math


def eta_squared(groups, when_constant: float = float("nan")) -> float:
    """One-way eta squared, SS_between / SS_total, as a fraction.

    `when_constant` is returned when all values are equal, or when there are none.
    """
    values = [v for g in groups for v in g]
    n = len(values)
    if n == 0:
        return when_constant
    grand_mean = sum(values) / n
    ss_total = sum((v - grand_mean) ** 2 for v in values)
    if ss_total == 0:
        return when_constant
    ss_between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in groups if g)
    return ss_between / ss_total


def _betacf(a, b, x):
    """Continued fraction of the incomplete beta function (Lentz's method)."""
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    d = 1e-30 if abs(d) < 1e-30 else d
    d = 1 / d
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1e-30 if abs(d) < 1e-30 else d
        c = 1 + aa / c
        c = 1e-30 if abs(c) < 1e-30 else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1e-30 if abs(d) < 1e-30 else d
        c = 1 + aa / c
        c = 1e-30 if abs(c) < 1e-30 else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 3e-7:
            break
    return h


def _betai(a, b, x):
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0 or x >= 1:
        return 0.0 if x <= 0 else 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1 - bt * _betacf(b, a, 1 - x) / b


def f_sf(F, d1, d2) -> float:
    """P(F > f) for an F distribution with (d1, d2) degrees of freedom."""
    return _betai(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * F))


def chi2_sf(x, k) -> float:
    """P(X > x) for a chi-square distribution with k degrees of freedom."""
    if x <= 0:
        return 1.0
    a = k / 2.0
    xx = x / 2.0
    if xx < a + 1:                       # series for the lower incomplete gamma P(a, x); Q = 1 - P
        term = 1.0 / a
        s = term
        n = a
        for _ in range(500):
            n += 1
            term *= xx / n
            s += term
            if abs(term) < abs(s) * 1e-12:
                break
        return 1 - s * math.exp(-xx + a * math.log(xx) - math.lgamma(a))
    b = xx + 1 - a                       # continued fraction for the upper incomplete gamma
    c = 1e30
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-30 if abs(d) < 1e-30 else d
        c = b + an / c
        c = 1e-30 if abs(c) < 1e-30 else c
        d = 1 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return math.exp(-xx + a * math.log(xx) - math.lgamma(a)) * h


def oneway_anova(groups) -> dict | None:
    """One-way between-groups ANOVA.

    Returns F, p, eta2 (a fraction), dfb, dfw and the group sizes; None when there are
    not more values than groups. With no variance within the groups F is infinite and p 0.
    """
    values = [v for g in groups for v in g]
    k, n = len(groups), len(values)
    if n <= k:
        return None
    grand_mean = sum(values) / n
    ss_between = sum(len(g) * (sum(g) / len(g) - grand_mean) ** 2 for g in groups if g)
    ss_within = sum((v - sum(g) / len(g)) ** 2 for g in groups for v in g)
    ss_total = ss_between + ss_within
    out = {"dfb": k - 1, "dfw": n - k, "sizes": [len(g) for g in groups]}
    if ss_within == 0 or out["dfw"] == 0:
        return {**out, "F": float("inf"), "p": 0.0, "eta2": ss_between / ss_total if ss_total else 0.0}
    F = (ss_between / out["dfb"]) / (ss_within / out["dfw"])
    return {**out, "F": F, "p": f_sf(F, out["dfb"], out["dfw"]), "eta2": ss_between / ss_total}


def friedman(matrix) -> tuple[float, int, float]:
    """Friedman test over blocks: (chi-square statistic, degrees of freedom, Kendall's W).

    Ties within a block share the mean of their ranks; the statistic carries no tie correction.
    """
    n, k = len(matrix), len(matrix[0])
    rank_sums = [0.0] * k
    for row in matrix:
        order = sorted(range(k), key=lambda c: row[c])
        ranks = [0.0] * k
        i = 0
        while i < k:
            j = i
            while j + 1 < k and row[order[j + 1]] == row[order[i]]:
                j += 1
            for t in range(i, j + 1):
                ranks[order[t]] = (i + j) / 2 + 1
            i = j + 1
        for c in range(k):
            rank_sums[c] += ranks[c]
    stat = 12.0 / (n * k * (k + 1)) * sum(r * r for r in rank_sums) - 3 * n * (k + 1)
    return stat, k - 1, stat / (n * (k - 1))
