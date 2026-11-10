"""
Нечёткая раскладка: детали кладутся в силуэт, снятый с фото (без точной
подгонки длин), а затем каждая деталь «примагничивается» вершиной к вершине
уже лежащей детали. Итог — точная раскладка без наложений.
"""
import math
import os
import sys

import cv2
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import tg45  # noqa
from trace import load, cell_image, contours  # noqa

COUNTS = {"L": 2, "M": 1, "Q": 1, "P": 1, "S": 2}
AREA = {"L": 2, "M": 1, "Q": 1, "P": 1, "S": 0.5}


def target_from_cell(im, r, c, half=66, rot=None):
    g = cell_image(im, r, c, half)
    keep, cs, hier = contours(g)
    h, w = keep.shape
    polys = []
    for i, cnt in enumerate(cs):
        if hier[0][i][3] != -1 or cv2.contourArea(cnt) < 120:
            continue
        m = cv2.moments(cnt)
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        if abs(cx - w / 2) > 0.38 * w or abs(cy - h / 2) > 0.38 * h:
            continue
        peri = cv2.arcLength(cnt, True)
        ap = cv2.approxPolyDP(cnt, 0.004 * peri, True)
        if len(ap) < 3:
            continue
        p = Polygon([(float(q[0][0]), -float(q[0][1])) for q in ap]).buffer(0)
        polys.append(p)
    if not polys:
        return None
    main = max(polys, key=lambda p: p.area)
    u0 = math.sqrt(sum(p.area for p in polys) / 8)
    polys = [p for p in polys if p is main or p.distance(main) < 0.8 * u0]
    T = unary_union(polys)
    u = math.sqrt(T.area / 8)
    # выравнивание поворота: стороны должны идти под углами, кратными 45°
    if rot is None:
        num = den = 0.0
        for p in (T.geoms if T.geom_type == "MultiPolygon" else [T]):
            co = list(p.exterior.coords)
            for a, b in zip(co, co[1:]):
                L = math.dist(a, b)
                ang = math.atan2(b[1] - a[1], b[0] - a[0]) * 8  # период 45°
                num += L * math.sin(ang)
                den += L * math.cos(ang)
        rot = -math.atan2(num, den) / 8
    from shapely import affinity
    T = affinity.rotate(T, rot, origin=(0, 0), use_radians=True)
    T = affinity.scale(T, 1 / u, 1 / u, origin=(0, 0))
    x0, y0, _, _ = T.bounds
    T = affinity.translate(T, -x0, -y0)
    return T


def opening(g, d=0.07):
    return g.buffer(-d, join_style=2).buffer(d, join_style=2)


def corner(region):
    best = None
    geoms = region.geoms if region.geom_type == "MultiPolygon" else [region]
    for p in geoms:
        if p.area < 0.08:
            continue
        co = list(p.exterior.coords)[:-1]
        n = len(co)
        for i, (x, y) in enumerate(co):
            key = (round(y, 2), x)
            if best is None or key < best[0]:
                best = (key, (x, y), co[i - 1], co[(i + 1) % n])
    if best is None:
        return None
    _, c, a, b = best
    angs = []
    for q in (a, b):
        ang = math.degrees(math.atan2(q[1] - c[1], q[0] - c[0])) % 360
        angs.append(ang)
    alpha = min(angs)
    return c, (round(alpha / 45) * 45) % 360


def snap(pts, placed_pts):
    """Сдвиг, совмещающий ближайшую пару вершин (деталь <-> уже лежащие)."""
    best = None
    for p in pts:
        for q in placed_pts:
            d = math.dist(p, q)
            if best is None or d < best[0]:
                best = (d, (q[0] - p[0], q[1] - p[1]))
    return best


def fuzzy_solve(T, max_nodes=20000, branch=6, tol_out=0.18):
    Tbig = T.buffer(0.12, join_style=2)
    nodes = [0]
    best = [None]

    def rec(placed, counts):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            return True
        covered = unary_union([Polygon(p) for _, p in placed]) if placed else Polygon()
        if len(placed) == 7:
            miss = T.difference(covered).area
            extra = covered.difference(Tbig).area
            score = miss + extra
            if best[0] is None or score < best[0][0]:
                best[0] = (score, list(placed))
            return score < 0.25
        R = opening(T.difference(covered))
        cr = corner(R)
        if cr is None:
            return False
        c, alpha = cr
        cands = []
        placed_vs = [v for _, p in placed for v in p]
        for kind in ("L", "M", "Q", "P", "S"):
            if not counts[kind]:
                continue
            for rot, flip, pts in tg45.VARIANTS[kind]:
                n = len(pts)
                for i in range(n):
                    nx, ny = pts[(i + 1) % n]
                    a = math.degrees(math.atan2(ny - pts[i][1], nx - pts[i][0])) % 360
                    if abs((a - alpha + 180) % 360 - 180) > 1:
                        continue
                    dx, dy = c[0] - pts[i][0], c[1] - pts[i][1]
                    q = [(x + dx, y + dy) for x, y in pts]
                    if placed_vs:
                        d, (sx, sy) = snap(q, placed_vs)
                        if d < 0.3:
                            q = [(x + sx, y + sy) for x, y in q]
                    cand = Polygon(q)
                    if placed and cand.intersection(covered).area > 1e-6:
                        continue
                    out = cand.difference(Tbig).area
                    if out > tol_out * AREA[kind]:
                        continue
                    gain = cand.intersection(R).area
                    cands.append((out - 0.3 * gain, kind, q))
        cands.sort(key=lambda t: t[0])
        for _, kind, q in cands[:branch]:
            counts[kind] -= 1
            placed.append((kind, q))
            if rec(placed, counts):
                return True
            placed.pop()
            counts[kind] += 1
        return False

    rec([], dict(COUNTS))
    if best[0] is None:
        return None, None
    score, placed = best[0]
    used = {k: list(v) for k, v in tg45.TYPE_NAMES.items()}
    sol = {used[k].pop(0): [(round(x, 9), round(y, 9)) for x, y in p] for k, p in placed}
    return sol, score


def solve_cell_hard(im, r, c, nodes=25000):
    from shapely import affinity
    best = None
    for half in (66, 72):
        T0 = target_from_cell(im, r, c, half)
        if T0 is None:
            continue
        for scale in (1.0, 0.96, 1.04):
            Ts = affinity.scale(T0, scale, scale, origin=(0, 0))
            Ts = affinity.scale(Ts, math.sqrt(8 / Ts.area) * scale, math.sqrt(8 / Ts.area) * scale, origin=(0, 0)) if False else Ts
            for k in range(4):
                T = affinity.rotate(Ts, 90 * k, origin=(0, 0))
                try:
                    sol, score = fuzzy_solve(T, max_nodes=nodes, branch=5, tol_out=0.22)
                except Exception:
                    continue
                if sol is None:
                    continue
                # повернуть решение обратно
                a = math.radians(-90 * k)
                ca, sa = math.cos(a), math.sin(a)
                sol = {n: [(round(x * ca - y * sa, 9), round(x * sa + y * ca, 9)) for x, y in p]
                       for n, p in sol.items()}
                if best is None or score < best[1]:
                    best = (sol, score)
                if score < 0.3:
                    return best
    return best


def main_hard(argv):
    import json, time
    photo, out = argv[0], argv[1]
    im = load(photo)
    res = {}
    for a in argv[2:]:
        r, c = map(int, a.split(","))
        t = time.time()
        best = solve_cell_hard(im, r, c)
        print(a, None if not best else round(best[1], 3), "%.0fs" % (time.time() - t), flush=True)
        if best:
            res[a] = {"solution": best[0], "cost": best[1]}
            json.dump(res, open(out, "w"))


if __name__ == "__main__" and sys.argv[1] == "hard":
    main_hard(sys.argv[2:])
elif __name__ == "__main__":
    import json
    import time
    photo, out = sys.argv[1], sys.argv[2]
    cells = [tuple(map(int, a.split(","))) for a in sys.argv[3:]]
    im = load(photo)
    res = json.load(open(out)) if os.path.exists(out) else {}
    for r, c in cells:
        t = time.time()
        best = None
        for half in (66, 72):
            T = target_from_cell(im, r, c, half)
            if T is None:
                continue
            for tol in (0.18, 0.3):
                sol, score = fuzzy_solve(T, tol_out=tol)
                if sol and (best is None or score < best[1]):
                    best = (sol, score)
                if best and best[1] < 0.25:
                    break
            if best and best[1] < 0.25:
                break
        key = "%d,%d" % (r, c)
        print(key, "score", None if not best else round(best[1], 3), "%.1fs" % (time.time() - t), flush=True)
        if best:
            res[key] = {"solution": best[0], "cost": best[1], "fuzzy": True}
            json.dump(res, open(out, "w"))


