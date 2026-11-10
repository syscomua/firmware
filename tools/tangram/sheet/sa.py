"""
Подгонка 7 деталей под силуэт с фото методом имитации отжига.

Положение деталей непрерывное (сдвиги допускаются), повороты — кратно 45°,
параллелограмм можно перевернуть. Энергия: несовпадение с маской + штраф за
наложения (на растре). После отжига соседние стороны «примагничиваются»,
и раскладка проверяется точно (без наложений).
"""
import json
import math
import os
import random
import sys
import time

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import tg45  # noqa
from fuzzy import target_from_cell  # noqa
from trace import load  # noqa

NAMES = ["L1", "L2", "M", "Q", "P", "S1", "S2"]
KIND = {"L1": "L", "L2": "L", "M": "M", "Q": "Q", "P": "P", "S1": "S", "S2": "S"}
VARS = {k: [np.array(v[2]) - np.mean(v[2], axis=0) for v in tg45.VARIANTS[k]] for k in tg45.VARIANTS}
STEP = 0.05


class Grid:
    def __init__(self, T):
        x0, y0, x1, y1 = T.bounds
        pad = 1.0
        xs = np.arange(x0 - pad, x1 + pad, STEP)
        ys = np.arange(y0 - pad, y1 + pad, STEP)
        self.X, self.Y = np.meshgrid(xs, ys)
        from shapely import contains_xy
        self.mask = contains_xy(T, self.X, self.Y)
        self.bounds = (x0, y0, x1, y1)
        self.inside = np.argwhere(self.mask)

    def raster(self, pts):
        m = np.ones(self.X.shape, bool)
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            m &= (x2 - x1) * (self.Y - y1) - (y2 - y1) * (self.X - x1) >= 0
        return m


def poly(name, var, pos):
    return VARS[KIND[name]][var] + np.array(pos)


def energy(cnt, mask):
    cov = cnt > 0
    return np.count_nonzero(cov ^ mask) + 3 * np.count_nonzero(cnt > 1)


def anneal(G, iters=25000, seed=0):
    rng = random.Random(seed)
    x0, y0, x1, y1 = G.bounds
    state = {}
    rasters = {}
    cnt = np.zeros(G.X.shape, np.int16)
    for n in NAMES:
        iy, ix = G.inside[rng.randrange(len(G.inside))]
        state[n] = [rng.randrange(len(VARS[KIND[n]])), (G.X[iy, ix], G.Y[iy, ix])]
        rasters[n] = G.raster(poly(n, *state[n]))
        cnt += rasters[n]
    E = energy(cnt, G.mask)
    best = (E, {k: [v[0], tuple(v[1])] for k, v in state.items()})
    T0, T1 = 60.0, 0.5
    for it in range(iters):
        T = T0 * (T1 / T0) ** (it / iters)
        mv = rng.random()
        changed = []
        if mv < 0.08:  # поменять местами две детали
            a, b = rng.sample(NAMES, 2)
            na, nb = list(state[a]), list(state[b])
            state[a] = [na[0], nb[1]]
            state[b] = [nb[0], na[1]]
            changed = [(a, na), (b, nb)]
        else:
            n = rng.choice(NAMES)
            old = list(state[n])
            v, (x, y) = old
            if mv < 0.18:
                v = rng.randrange(len(VARS[KIND[n]]))
            elif mv < 0.24:
                iy, ix = G.inside[rng.randrange(len(G.inside))]
                x, y = G.X[iy, ix], G.Y[iy, ix]
            else:
                s = 0.6 * (T / T0) + 0.03
                x += rng.gauss(0, s)
                y += rng.gauss(0, s)
            state[n] = [v, (x, y)]
            changed = [(n, old)]
        newr = {}
        for n, _ in changed:
            cnt -= rasters[n]
            newr[n] = G.raster(poly(n, *state[n]))
            cnt += newr[n]
        E2 = energy(cnt, G.mask)
        if E2 <= E or rng.random() < math.exp((E - E2) / T):
            E = E2
            rasters.update(newr)
            if E < best[0]:
                best = (E, {k: [v[0], tuple(v[1])] for k, v in state.items()})
        else:
            for n, old in changed:
                cnt -= newr[n]
                cnt += rasters[n]
                state[n] = old
    return best


# ---------------------------------------------------------------- примагничивание

def edges(p):
    return [(p[i], p[(i + 1) % len(p)]) for i in range(len(p))]


def contact_shift(a, b, maxd):
    """Сдвиг детали a, чтобы её сторона легла на сторону b (ближайшая пара)."""
    best = None
    for a1, a2 in edges(a):
        ux, uy = a2[0] - a1[0], a2[1] - a1[1]
        La = math.hypot(ux, uy)
        ux, uy = ux / La, uy / La
        for b1, b2 in edges(b):
            vx, vy = b2[0] - b1[0], b2[1] - b1[1]
            Lb = math.hypot(vx, vy)
            if ux * vx / Lb + uy * vy / Lb > -0.999:  # стороны должны смотреть навстречу
                continue
            nx, ny = -uy, ux
            d = (b1[0] - a1[0]) * nx + (b1[1] - a1[1]) * ny
            if abs(d) > maxd:
                continue
            t1 = (b1[0] - a1[0]) * ux + (b1[1] - a1[1]) * uy
            t2 = (b2[0] - a1[0]) * ux + (b2[1] - a1[1]) * uy
            lo, hi = max(0, min(t1, t2)), min(La, max(t1, t2))
            if hi - lo < 0.2:
                continue
            if best is None or abs(d) < abs(best[0]):
                best = (d, (nx, ny), (ux, uy))
    return best


def snap_all(pieces, rounds=6):
    names = list(pieces)
    for _ in range(rounds):
        moved = False
        for n in names:
            # первая линия контакта
            others = [pieces[m] for m in names if m != n]
            cands = [contact_shift(pieces[n], o, 0.18) for o in others]
            cands = [c for c in cands if c and abs(c[0]) > 1e-9]
            if not cands:
                continue
            d, (nx, ny), u = min(cands, key=lambda c: abs(c[0]))
            pieces[n] = [(x + d * nx, y + d * ny) for x, y in pieces[n]]
            moved = True
            # вершина к вершине, если рядом
            bv = None
            for a in pieces[n]:
                for o in others:
                    for b in o:
                        dd = math.dist(a, b)
                        if 1e-9 < dd < 0.06 and (bv is None or dd < bv[0]):
                            bv = (dd, (b[0] - a[0], b[1] - a[1]))
            if bv:
                # сдвиг только вдоль линии контакта, чтобы не потерять её
                t = bv[1][0] * u[0] + bv[1][1] * u[1]
                pieces[n] = [(x + t * u[0], y + t * u[1]) for x, y in pieces[n]]
        if not moved:
            break
    return pieces


def separate(pieces, rounds=30):
    """Раздвинуть остаточные наложения (сдвиг по наименьшей глубине)."""
    names = list(pieces)
    for _ in range(rounds):
        worst = 0
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                A, B = Polygon(pieces[names[i]]), Polygon(pieces[names[j]])
                inter = A.intersection(B).area
                if inter < 1e-9:
                    continue
                worst = max(worst, inter)
                # оси разделения — нормали сторон
                best = None
                for p in (pieces[names[i]], pieces[names[j]]):
                    for a1, a2 in edges(p):
                        ux, uy = a2[0] - a1[0], a2[1] - a1[1]
                        L = math.hypot(ux, uy)
                        nx, ny = -uy / L, ux / L
                        pa = [x * nx + y * ny for x, y in pieces[names[i]]]
                        pb = [x * nx + y * ny for x, y in pieces[names[j]]]
                        o1 = max(pa) - min(pb)
                        o2 = max(pb) - min(pa)
                        if o1 < o2:
                            cand = (o1, (nx, ny), 1)
                        else:
                            cand = (o2, (nx, ny), -1)
                        if best is None or cand[0] < best[0]:
                            best = cand
                o, (nx, ny), sgn = best
                # двигаем j на всю глубину
                pieces[names[j]] = [(x + sgn * o * nx, y + sgn * o * ny) for x, y in pieces[names[j]]]
        if worst < 1e-9:
            break
    return pieces


def valid(pieces):
    ps = [Polygon(p) for p in pieces.values()]
    for i in range(len(ps)):
        for j in range(i + 1, len(ps)):
            if ps[i].intersection(ps[j]).area > 1e-6:
                return False
    return True


def parts(geom):
    return 1 if geom.geom_type == "Polygon" else len(geom.geoms)


def fit_cell(im, r, c, restarts=40, iters=30000, seed0=0):
    T = target_from_cell(im, r, c, 66)
    G = Grid(T)
    nparts = parts(T.buffer(0.05))
    results = []
    for k in range(restarts):
        E, st = anneal(G, iters, seed=seed0 + k)
        pieces = {n: [tuple(p) for p in poly(n, *st[n]).tolist()] for n in NAMES}
        pieces = snap_all(pieces)
        if not valid(pieces):
            before = {n: p[0] for n, p in pieces.items()}
            pieces = separate(pieces)
            if max(math.dist(before[n], pieces[n][0]) for n in pieces) > 0.3:
                continue
            pieces = snap_all(pieces)
        if not valid(pieces):
            continue
        extra = max(0, parts(unary_union([Polygon(p).buffer(1e-4) for p in pieces.values()])) - nparts)
        U = unary_union([Polygon(p) for p in pieces.values()])
        iou = U.intersection(T).area / U.union(T).area
        results.append((iou - 0.08 * extra, E, pieces))
    results.sort(key=lambda t: -t[0])
    return results[0] if results else None


if __name__ == "__main__":
    photo, out = sys.argv[1], sys.argv[2]
    im = load(photo)
    res = json.load(open(out)) if os.path.exists(out) else {}
    for a in sys.argv[3:]:
        r, c = map(int, a.split(","))
        t = time.time()
        b = fit_cell(im, r, c)
        print(a, None if not b else "IoU %.3f E %d" % (b[0], b[1]), "%.0fs" % (time.time() - t), flush=True)
        if b:
            res[a] = {"solution": b[2], "iou": b[0]}
            json.dump(res, open(out, "w"))
