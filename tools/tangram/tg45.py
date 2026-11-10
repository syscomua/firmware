"""
Движок для фигур танграма с поворотами на 45°.

Единица длины = катет маленького треугольника. Тогда:
  большой треугольник  — катеты 2,  площадь 2
  средний треугольник  — катеты √2, площадь 1
  маленький треугольник — катеты 1, площадь 0.5
  квадрат              — сторона 1, площадь 1
  параллелограмм       — стороны 1 и √2, площадь 1
Всего площадь 8.

Фигура описывается цепочкой: каждая деталь ставится поворотом (кратно 45°,
против часовой), при необходимости переворачивается, и одна её вершина
совмещается с заданной точкой (обычно — с вершиной уже положенной детали).
"""

import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

R = math.sqrt(2)
H = R / 2

BASE = {
    "L": [(0, 0), (2, 0), (0, 2)],
    "M": [(0, 0), (R, 0), (0, R)],
    "S": [(0, 0), (1, 0), (0, 1)],
    "Q": [(0, 0), (1, 0), (1, 1), (0, 1)],
    "P": [(0, 0), (1, 0), (2, 1), (1, 1)],
}

# имя -> (тип, цвет, название для инструкции, род: m/f)
PIECES = {
    "L1": ("L", "#1f5a2c", "большой тёмно-зелёный треугольник"),
    "L2": ("L", "#e8a530", "большой оранжевый треугольник"),
    "M":  ("M", "#e0457b", "средний розовый треугольник"),
    "Q":  ("Q", "#2f62d9", "синий квадрат"),
    "S1": ("S", "#6cc08b", "маленький салатовый треугольник"),
    "S2": ("S", "#b8222b", "маленький красный треугольник"),
    "P":  ("P", "#d93a3a", "красный параллелограмм"),
}
ORDER = ["L1", "L2", "M", "Q", "P", "S1", "S2"]


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def add(a, d):
    return (a[0] + d[0], a[1] + d[1])


class Fig:
    def __init__(self, key, name):
        self.key = key
        self.name = name
        self.pieces = {}   # имя -> список вершин
        self.order = []

    def put(self, name, rot=0, flip=False, v=0, at=(0, 0)):
        kind = PIECES[name][0]
        pts = list(BASE[kind])
        if flip:
            pts = [(-x, y) for x, y in pts]
        a = math.radians(rot)
        c, s = math.cos(a), math.sin(a)
        pts = [(x * c - y * s, x * s + y * c) for x, y in pts]
        dx, dy = at[0] - pts[v][0], at[1] - pts[v][1]
        pts = [(round(x + dx, 9), round(y + dy, 9)) for x, y in pts]
        self.pieces[name] = pts
        self.order.append(name)
        return self

    def __getitem__(self, name):
        return self.pieces[name]

    def check(self):
        errs = []
        missing = set(PIECES) - set(self.pieces)
        if missing:
            errs.append("нет деталей: %s" % ", ".join(sorted(missing)))
        polys = {n: Polygon(p) for n, p in self.pieces.items()}
        names = list(polys)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a = polys[names[i]].intersection(polys[names[j]]).area
                if a > 1e-6:
                    errs.append("перекрытие %s/%s: %.3f" % (names[i], names[j], a))
        u = unary_union(list(polys.values()))
        parts = 1 if u.geom_type == "Polygon" else len(u.geoms)
        return errs, parts

    def bounds(self):
        xs = [x for p in self.pieces.values() for x, _ in p]
        ys = [y for p in self.pieces.values() for _, y in p]
        return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------
# Решатель: силуэт (многоугольник) -> раскладка 7 деталей
# --------------------------------------------------------------------------

import shapely
from shapely.geometry import MultiPolygon

EPS = 1e-6
TYPE_NAMES = {"L": ["L1", "L2"], "M": ["M"], "Q": ["Q"], "P": ["P"], "S": ["S1", "S2"]}


def _ccw(pts):
    a = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
    return pts if a > 0 else pts[::-1]


def _orient_variants(kind):
    out, seen = [], set()
    for flip in (False, True):
        for k in range(8):
            pts = list(BASE[kind])
            if flip:
                pts = [(-x, y) for x, y in pts]
            a = math.radians(45 * k)
            c, s = math.cos(a), math.sin(a)
            pts = [(x * c - y * s, x * s + y * c) for x, y in pts]
            pts = _ccw(pts)
            key = frozenset((round(x - pts[0][0], 5), round(y - pts[0][1], 5)) for x, y in pts)
            norm = min(key)
            key = frozenset((round(x - norm[0], 5), round(y - norm[1], 5)) for x, y in key)
            if key in seen:
                continue
            seen.add(key)
            out.append((45 * k, flip, pts))
    return out


VARIANTS = {k: _orient_variants(k) for k in BASE}


def _angle(dx, dy):
    return math.degrees(math.atan2(dy, dx)) % 360


def _clean(g):
    g = shapely.set_precision(g, EPS)
    g = g.buffer(-5e-6, join_style=2, mitre_limit=10).buffer(5e-6, join_style=2, mitre_limit=10)
    g = shapely.set_precision(g, EPS)
    if g.is_empty:
        return g
    polys = [p for p in (g.geoms if hasattr(g, "geoms") else [g])
             if p.geom_type == "Polygon" and p.area > 1e-5]
    return MultiPolygon(polys) if len(polys) != 1 else polys[0]


def _corner(region):
    best = None
    polys = region.geoms if region.geom_type == "MultiPolygon" else [region]
    for p in polys:
        for ring in [p.exterior] + list(p.interiors):
            pts = list(ring.coords)[:-1]
            n = len(pts)
            for i, (x, y) in enumerate(pts):
                key = (round(y, 4), round(x, 4))
                if best is None or key < best[0]:
                    best = (key, (x, y), pts[i - 1], pts[(i + 1) % n])
    _, c, a, b = best
    da = _angle(a[0] - c[0], a[1] - c[1])
    db = _angle(b[0] - c[0], b[1] - c[1])
    return c, min(da, db)


class Budget(Exception):
    pass


def solve45(silhouette, max_solutions=1, max_nodes=40000):
    return solve45_geom(Polygon(silhouette), max_solutions, max_nodes)


def solve45_geom(geom, max_solutions=1, max_nodes=40000):
    region = _clean(geom)
    nodes = [0]
    if abs(region.area - 8) > 1e-3:
        raise ValueError("площадь силуэта %.4f, а должна быть 8" % region.area)
    counts = {"L": 2, "M": 1, "Q": 1, "P": 1, "S": 2}
    sols = []

    def rec(region, placed):
        nodes[0] += 1
        if nodes[0] > max_nodes:
            raise Budget()
        if region.is_empty or region.area < 1e-5:
            if any(counts.values()):
                return False
            sols.append(list(placed))
            return len(sols) >= max_solutions
        c, alpha = _corner(region)
        for kind in ("L", "M", "Q", "P", "S"):
            if not counts[kind]:
                continue
            for rot, flip, pts in VARIANTS[kind]:
                n = len(pts)
                for i in range(n):
                    nx, ny = pts[(i + 1) % n]
                    if abs((_angle(nx - pts[i][0], ny - pts[i][1]) - alpha + 180) % 360 - 180) > 0.01:
                        continue
                    dx, dy = c[0] - pts[i][0], c[1] - pts[i][1]
                    cand = Polygon([(x + dx, y + dy) for x, y in pts])
                    if cand.difference(region).area > 1e-5:
                        continue
                    counts[kind] -= 1
                    placed.append((kind, [(x + dx, y + dy) for x, y in pts]))
                    if rec(_clean(region.difference(cand)), placed):
                        return True
                    placed.pop()
                    counts[kind] += 1
        return False

    try:
        rec(region, [])
    except Budget:
        pass
    out = []
    for sol in sols:
        used = {k: list(v) for k, v in TYPE_NAMES.items()}
        out.append({used[k].pop(0): pts for k, pts in sol})
    return out


def fig_from_solution(key, name, sol):
    f = Fig(key, name)
    for n in ORDER:
        f.pieces[n] = [(round(x, 9), round(y, 9)) for x, y in sol[n]]
        f.order.append(n)
    return f


# --------------------------------------------------------------------------
# Черепаха для описания контуров: направления E, NE, N, NW, W, SW, S, SE
# --------------------------------------------------------------------------

DIR = {"E": 0, "NE": 45, "N": 90, "NW": 135, "W": 180, "SW": 225, "S": 270, "SE": 315}


def path(*moves, start=(0, 0)):
    """path("E", 2, "N", R, ...) -> список вершин. Длина — евклидова."""
    pts = [start]
    x, y = start
    it = iter(moves)
    for d in it:
        L = next(it)
        a = math.radians(DIR[d])
        x, y = x + L * math.cos(a), y + L * math.sin(a)
        pts.append((round(x, 9), round(y, 9)))
    if math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) > 1e-6:
        raise ValueError("контур не замкнут: %r" % (pts[-1],))
    return pts[:-1]
