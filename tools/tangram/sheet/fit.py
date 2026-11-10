"""
Подбор по шаблону: шаблон фигуры с параметрами (длины на решётке a + b·√2/2),
перебор параметров с площадью 8, сортировка по похожести на силуэт с фото
(IoU после совмещения центров), проверка решателем.
"""
import itertools
import math
import os
import sys

from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import tg45  # noqa
from fuzzy import target_from_cell  # noqa
from trace import load  # noqa

h = math.sqrt(2) / 2
PHOTO = '/root/.claude/uploads/746e9745-5d65-5192-98ab-5449622e39de/eaddfa52-image.jpg'
_IM = None


def lat(lo, hi, amax=6, bmax=8):
    return sorted({round(a + b * h, 9) for a in range(-amax, amax + 1)
                   for b in range(-bmax, bmax + 1) if lo <= a + b * h <= hi})


def iou(a, b):
    ca, cb = a.centroid, b.centroid
    b = affinity.translate(b, ca.x - cb.x, ca.y - cb.y)
    best = 0
    for dx in (-0.15, 0, 0.15):
        for dy in (-0.15, 0, 0.15):
            bb = affinity.translate(b, dx, dy)
            best = max(best, a.intersection(bb).area / a.union(bb).area)
    return best


def fit(cell, template, ranges, top=60, nodes=6000, verbose=True, min_iou=0.0):
    global _IM
    if _IM is None:
        _IM = load(PHOTO)
    r, c = cell
    T = target_from_cell(_IM, r, c, 66)
    cands = []
    names = list(ranges)
    for vals in itertools.product(*[ranges[n] for n in names]):
        p = dict(zip(names, vals))
        try:
            g = template(**p)
        except (ValueError, AssertionError):
            continue
        if g is None:
            continue
        if isinstance(g, list):
            g = unary_union([Polygon(x) for x in g])
        if not g.is_valid or abs(g.area - 8) > 1e-6:
            continue
        cands.append((iou(T, g), p, g))
    cands.sort(key=lambda t: -t[0])
    if verbose:
        print("кандидатов:", len(cands), "лучшее IoU:", round(cands[0][0], 3) if cands else None)
    for sc, p, g in cands[:top]:
        if sc < min_iou:
            break
        sols = tg45.solve45_geom(g, max_nodes=nodes)
        if sols:
            if verbose:
                print("решено: IoU %.3f" % sc, {k: round(v, 3) for k, v in p.items()})
            return sols[0], sc, p
    return None, None, None


def turtle(start, *moves):
    """moves: (направление_в_градусах, длина) ..."""
    x, y = start
    pts = [(x, y)]
    for d, L in moves:
        a = math.radians(d)
        x, y = x + L * math.cos(a), y + L * math.sin(a)
        pts.append((x, y))
    if math.dist(pts[0], pts[-1]) > 1e-6:
        return None
    return Polygon(pts[:-1])


def close_turtle(start, moves):
    """Последний ход не задаётся: замыкаем отрезком, если он под углом, кратным 45°."""
    x, y = start
    pts = [(x, y)]
    for d, L in moves:
        a = math.radians(d)
        x, y = x + L * math.cos(a), y + L * math.sin(a)
        pts.append((x, y))
    dx, dy = start[0] - x, start[1] - y
    if math.hypot(dx, dy) > 1e-9:
        ang = math.degrees(math.atan2(dy, dx)) % 45
        if min(ang, 45 - ang) > 1e-6:
            return None
    p = Polygon(pts)
    return p if p.is_valid else None
