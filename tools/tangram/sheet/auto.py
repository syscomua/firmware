"""Автоматически: фото ячейки -> силуэт на решётке -> раскладка 7 деталей."""
import itertools
import json
import math
import os
import sys
import time

import cv2
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from trace import (load, cell_image, contours, simplify, snap_polygon,  # noqa
                   to_points, area, H)
import tg45  # noqa

PHOTO = sys.argv[1]
OUT = sys.argv[2]
CELLS = [tuple(map(int, a.split(","))) for a in sys.argv[3:]] or \
    [(r, c) for r in range(8) for c in range(6)]


def nearest_lattice(v):
    best = None
    for b in range(-16, 17):
        a = round(v - b * H)
        d = abs(a + b * H - v)
        if best is None or d < best[0]:
            best = (d, a + b * H)
    return best[1]


def parts_of(im, r, c, half=66):
    g = cell_image(im, r, c, half)
    keep, cs, hier = contours(g)
    h, w = keep.shape
    comps = []
    for i, cnt in enumerate(cs):
        if hier[0][i][3] != -1:
            continue  # дырки пока пропускаем
        a = cv2.contourArea(cnt)
        if a < 200:
            continue
        m = cv2.moments(cnt)
        cx, cy = m["m10"] / m["m00"], m["m01"] / m["m00"]
        if abs(cx - w / 2) > 0.36 * w or abs(cy - h / 2) > 0.36 * h:
            continue
        comps.append((a, cnt))
    return comps


def solve_cell(im, r, c, log, eps_list=(0.012, 0.008, 0.016, 0.021),
               halves=(66, 72)):
    tried = 0
    for half in halves:
        comps = parts_of(im, r, c, half)
        if not comps:
            continue
        A = sum(a for a, _ in comps)
        u = math.sqrt(A / 8)
        for eps in eps_list:
            parts = []
            for a, cnt in comps:
                pts = simplify(cnt, eps)
                if len(pts) > 26:
                    parts = None
                    break
                opts = snap_polygon(pts, u, beam=2500, keep=25, ncand=5)
                opts = [(s, cost, area(to_points(s))) for s, cost in opts]
                opts = [o for o in opts if o[2] > 0.2]
                if not opts:
                    parts = None
                    break
                opts.sort(key=lambda o: o[1])
                parts.append((pts, opts[:20]))
            if not parts:
                continue
            combos = []
            for choice in itertools.product(*[p[1] for p in parts]):
                if abs(sum(o[2] for o in choice) - 8) < 1e-6:
                    combos.append((sum(o[1] for o in choice), choice))
            combos.sort(key=lambda t: t[0])
            for cost, choice in combos[:12]:
                polys = []
                x0, y0 = parts[0][0][0]
                for (pts, _), (sn, _, _) in zip(parts, choice):
                    ox = nearest_lattice((pts[0][0] - x0) / u)
                    oy = nearest_lattice((pts[0][1] - y0) / u)
                    polys.append(Polygon(to_points(sn, (ox, oy))))
                if any(not p.is_valid for p in polys):
                    continue
                if any(p.intersection(q).area > 1e-6
                       for p, q in itertools.combinations(polys, 2)):
                    continue
                tried += 1
                try:
                    sols = tg45.solve45_geom(unary_union(polys), max_nodes=5000)
                except ValueError:
                    continue
                if sols:
                    log("  решено: half=%d eps=%.3f стоимость %.2f" % (half, eps, cost))
                    return {"silhouette": [list(p.exterior.coords) for p in polys],
                            "solution": sols[0], "cost": cost, "u": u}
    log("  попыток решателя: %d" % tried)
    return None


def main():
    im = load(PHOTO)
    res = {}
    if os.path.exists(OUT):
        res = json.load(open(OUT))
    for r, c in CELLS:
        key = "%d,%d" % (r, c)
        t = time.time()
        print(key, flush=True)
        out = solve_cell(im, r, c, lambda s: print(s, flush=True))
        print("  %s за %.1fs" % ("OK" if out else "нет", time.time() - t), flush=True)
        if out and (key not in res or res[key].get("manual") is None):
            res[key] = out
            json.dump(res, open(OUT, "w"))


main()
