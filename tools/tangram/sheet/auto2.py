"""Как auto.py, но контур сначала выравнивается по углу (кратно 45°) и масштабируется."""
import itertools, json, math, os, sys, time
from shapely.geometry import Polygon
from shapely.ops import unary_union
from fuzzy import target_from_cell
from trace import load, snap_polygon, to_points, area
import tg45

PHOTO, OUT = sys.argv[1], sys.argv[2]
cells = [tuple(map(int, a.split(","))) for a in sys.argv[3:]]
im = load(PHOTO)
res = json.load(open(OUT)) if os.path.exists(OUT) else {}


def nearest_lattice(v):
    best = None
    for b in range(-16, 17):
        a = round(v - b * tg45.H)
        d = abs(a + b * tg45.H - v)
        if best is None or d < best[0]:
            best = (d, a + b * tg45.H)
    return best[1]


for r, c in cells:
    t = time.time()
    done = False
    for half in (66, 72):
        T = target_from_cell(im, r, c, half)
        if T is None:
            continue
        geoms = [g for g in (T.geoms if T.geom_type == "MultiPolygon" else [T]) if g.area > 0.1]
        for tol in (0.08, 0.12, 0.16, 0.05, 0.2):
            parts = []
            for g in geoms:
                co = list(g.simplify(tol).exterior.coords)[:-1]
                opts = snap_polygon(co, 1.0, beam=3000, keep=25, ncand=4)
                opts = [(s, cost, area(to_points(s))) for s, cost in opts]
                opts = sorted([o for o in opts if o[2] > 0.2], key=lambda o: o[1])[:20]
                if not opts:
                    parts = None
                    break
                parts.append((co, opts))
            if not parts:
                continue
            combos = sorted(((sum(o[1] for o in ch), ch) for ch in itertools.product(*[p[1] for p in parts])
                             if abs(sum(o[2] for o in ch) - 8) < 1e-6), key=lambda t: t[0])
            for cost, ch in combos[:15]:
                x0, y0 = parts[0][0][0]
                polys = [Polygon(to_points(sn, (nearest_lattice(co[0][0] - x0), nearest_lattice(co[0][1] - y0))))
                         for (co, _), (sn, _, _) in zip(parts, ch)]
                if any(not p.is_valid for p in polys) or any(
                        p.intersection(q).area > 1e-6 for p, q in itertools.combinations(polys, 2)):
                    continue
                try:
                    sols = tg45.solve45_geom(unary_union(polys), max_nodes=6000)
                except Exception:
                    continue
                if sols:
                    res["%d,%d" % (r, c)] = {"solution": sols[0], "cost": cost}
                    json.dump(res, open(OUT, "w"))
                    print("%d,%d OK tol=%.2f cost=%.2f %.0fs" % (r, c, tol, cost, time.time() - t), flush=True)
                    done = True
                    break
            if done:
                break
        if done:
            break
    if not done:
        print("%d,%d нет %.0fs" % (r, c, time.time() - t), flush=True)
