"""Tiny dependency-free linear algebra: least squares by normal equations + Gauss-Jordan (no numpy on the Pi Zero)."""
from __future__ import annotations


def solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a x = b (square) by Gauss-Jordan with partial pivoting. Raises ValueError if singular."""
    n = len(b)
    m = [list(map(float, a[i])) + [float(b[i])] for i in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-300:
            raise ValueError('singular matrix')
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c] != 0.0:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c])]
    return [m[i][n] for i in range(n)]


def lstsq(rows: list[list[float]], y: list[float], w: list[float] | None = None, ridge: float = 1e-12) -> list[float]:
    """Weighted linear least squares min sum w (rows.x - y)^2 via normal equations (small ridge keeps weak terms finite)."""
    k = len(rows[0])
    ata = [[0.0] * k for _ in range(k)]
    aty = [0.0] * k
    for i, r in enumerate(rows):
        wi = 1.0 if w is None else w[i]
        for p in range(k):
            aty[p] += wi * r[p] * y[i]
            for q in range(k):
                ata[p][q] += wi * r[p] * r[q]
    scale = max(ata[i][i] for i in range(k)) or 1.0
    for i in range(k):
        ata[i][i] += ridge * scale
    return solve(ata, aty)
