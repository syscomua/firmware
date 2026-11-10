"""Порядок шагов и текст инструкции для каждой фигуры."""
import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

NAMES = {
    "L1": ("большой тёмно-зелёный треугольник", "к большому тёмно-зелёному треугольнику"),
    "L2": ("большой оранжевый треугольник", "к большому оранжевому треугольнику"),
    "M":  ("средний розовый треугольник", "к среднему розовому треугольнику"),
    "Q":  ("синий квадрат", "к синему квадрату"),
    "P":  ("красный параллелограмм", "к красному параллелограмму"),
    "S1": ("маленький салатовый треугольник", "к маленькому салатовому треугольнику"),
    "S2": ("маленький красный треугольник", "к маленькому красному треугольнику"),
}
AREA = {"L1": 2, "L2": 2, "M": 1, "Q": 1, "P": 1, "S1": .5, "S2": .5}

DIR8 = ["справа", "сверху справа", "сверху", "сверху слева",
        "слева", "снизу слева", "снизу", "снизу справа"]
POINT8 = ["вправо", "вправо-вверх", "вверх", "влево-вверх",
          "влево", "влево-вниз", "вниз", "вправо-вниз"]


def dir8(dx, dy):
    return int(round(math.degrees(math.atan2(dy, dx)) / 45)) % 8


def centroid(pts):
    p = Polygon(pts).centroid
    return p.x, p.y


def orientation(name, pts):
    if name in ("L1", "L2", "M", "S1", "S2"):
        # прямой угол — вершина, противоположная самой длинной стороне
        best = None
        for i in range(3):
            a, b = pts[(i + 1) % 3], pts[(i + 2) % 3]
            L = math.dist(a, b)
            if best is None or L > best[0]:
                best = (L, i, a, b)
        _, i, a, b = best
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = dir8(pts[i][0] - m[0], pts[i][1] - m[1])
        if d % 2 == 0:
            opp = {0: "слева", 2: "внизу", 4: "справа", 6: "вверху"}[d]
            return "прямым углом %s (длинная сторона %s)" % (POINT8[d], opp)
        return "прямым углом %s" % POINT8[d]
    if name == "Q":
        e = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        if abs(e[0]) < 1e-6 or abs(e[1]) < 1e-6:
            return "ровно, стороной вниз"
        return "ромбиком, уголком вниз"
    # параллелограмм: направление длинной стороны и «наклон»
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if math.dist(a, b) > 1.2:
            d = dir8(b[0] - a[0], b[1] - a[1]) % 4
            break
    long_dir = ["длинной стороной горизонтально",
                "длинной стороной наискосок, вправо-вверх",
                "длинной стороной вертикально",
                "длинной стороной наискосок, влево-вверх"][d]
    return long_dir


def chirality(pts):
    """+1 / -1 — какой стороной лежит параллелограмм."""
    poly = Polygon(pts)
    if not poly.exterior.is_ccw:
        pts = pts[::-1]
    n = len(pts)
    for i in range(n):
        a, b, c = pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        if abs(math.dist(a, b) - 1) < 1e-3:
            v1 = (b[0] - a[0], b[1] - a[1])
            v2 = (c[0] - b[0], c[1] - b[1])
            cross = v1[0] * v2[1] - v1[1] * v2[0]
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            ang = math.degrees(math.atan2(cross, dot))
            return 1 if ang < 90 else -1
    return 1


# В коробке (исходный квадрат) параллелограмм лежит так:
BOX_P = [(0, 0), (1, 1), (1, 3), (0, 2)]
BOX_P = [(x * math.sqrt(2) / 2, y * math.sqrt(2) / 2) for x, y in BOX_P]


def shared(a, b):
    return Polygon(a).buffer(1e-4).intersection(Polygon(b).buffer(1e-4)).length / 2


def plan(sol):
    """Порядок шагов: сначала крупные детали, каждая следующая касается уже лежащих."""
    left = dict(sol)
    order = []
    first = max(left, key=lambda n: (AREA[n], -centroid(left[n])[1], -centroid(left[n])[0]))
    order.append(first)
    del left[first]
    while left:
        def score(n):
            touch = max(shared(left[n], sol[m]) for m in order)
            return (touch > 1e-3, AREA[n], -centroid(left[n])[1])
        n = max(left, key=score)
        order.append(n)
        del left[n]
    steps = []
    union_c = unary_union([Polygon(p) for p in sol.values()]).centroid
    for k, n in enumerate(order):
        pts = sol[n]
        name, dat = NAMES[n]
        text = "Возьмите %s. Положите его %s" % (name, orientation(n, pts))
        if k == 0:
            text += ". Это основа фигуры."
        else:
            touch = [(shared(pts, sol[m]), m) for m in order[:k]]
            L, m = max(touch)
            if L > 1e-3:
                cx, cy = centroid(pts)
                mx, my = centroid(sol[m])
                text += " и приложите %s %s." % (DIR8[dir8(cx - mx, cy - my)], NAMES[m][1])
            else:
                near = [(Polygon(pts).distance(Polygon(sol[m])), m) for m in order[:k]]
                dmin, m = min(near)
                cx, cy = centroid(pts)
                if dmin < 1e-6:
                    mx, my = centroid(sol[m])
                    text += " и поставьте %s, уголком %s." % (
                        DIR8[dir8(cx - mx, cy - my)], NAMES[m][1])
                else:
                    text += ", отдельно от остальных: %s от фигуры." % (
                        DIR8[dir8(cx - union_c.x, cy - union_c.y)])
        if n == "P" and chirality(pts) != chirality(BOX_P):
            text += " Если не подходит — переверните параллелограмм другой стороной."
        steps.append({"piece": n, "text": text})
    return steps


def difficulty(sol):
    u = unary_union([Polygon(p).buffer(1e-5, join_style=2) for p in sol.values()])
    geoms = list(u.geoms) if u.geom_type == "MultiPolygon" else [u]
    verts = sum(len(g.simplify(1e-3).exterior.coords) - 1 for g in geoms)
    if verts <= 6 and len(geoms) == 1:
        return 1
    if verts <= 11:
        return 2
    return 3
