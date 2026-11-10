"""Шаблоны силуэтов с параметрами для фигур, которые не снялись с фото автоматически."""
import math
import sys

from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from fit import fit, lat, h

R = math.sqrt(2)
D = {"E": 0, "NE": 45, "N": 90, "NW": 135, "W": 180, "SW": 225, "S": 270, "SE": 315}


def walk(moves, close_dir=None):
    """moves: [(dir, len)], последний отрезок до старта должен идти в close_dir."""
    x = y = 0.0
    pts = [(0.0, 0.0)]
    for d, L in moves:
        if L <= 1e-9:
            return None
        a = math.radians(D[d])
        x, y = x + L * math.cos(a), y + L * math.sin(a)
        pts.append((x, y))
    if close_dir is None:
        if math.hypot(x, y) > 1e-7:
            return None
        pts = pts[:-1]
    else:
        a = math.radians(D[close_dir])
        # (x, y) + t*(cos a, sin a) = (0, 0), t > 0
        c, s = math.cos(a), math.sin(a)
        t = -(x * c + y * s)
        if t <= 1e-9 or abs(x + t * c) > 1e-7 or abs(y + t * s) > 1e-7:
            return None
    A = 0.5 * abs(sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts))))
    if abs(A - 8) > 1e-6:
        return None
    p = Polygon(pts)
    return p if p.is_valid else None


def diamond(cx, cy, s):
    r = s * h
    return Polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])


T = {}


def tpl(cell, **ranges):
    def deco(fn):
        T[cell] = (fn, ranges)
        return fn
    return deco


# --- Ваза: горлышко, шестиугольное тулово, ножка, подставка (размеры сняты с фото)
@tpl((4, 2))
def vase():
    return Polygon([(0, 0), (3, 0), (2, 1), (2, 2), (3, 3), (2, 4), (2, 5), (1, 5), (1, 4),
                    (0, 3), (1, 2), (1, 1)])


# --- Цветок: «галочка» сверху, два перевёрнутых треугольника, трапеция внизу
@tpl((4, 3), tt=[0, 1, 2], cw=[1, R, 2, 1 + h], th=[h, 1, R])
def flower(tt, cw, th):
    if tt == 0:
        b = 1.25 * R; trap = Polygon([(-b, 0), (b, 0), (b - h, h), (-b + h, h)]); y = h
    elif tt == 1:
        trap = Polygon([(-1.5, 0), (1.5, 0), (0.5, 1), (-0.5, 1)]); y = 1
    else:
        trap = Polygon([(-R, 0), (R, 0), (0, R)]); y = 0  # треугольник вместо трапеции
    if tt == 2:
        t2 = Polygon([(0, R), (R, 2 * R), (-R, 2 * R)]); y = R
    else:
        t2 = Polygon([(0, y), (R, y + R), (-R, y + R)])
    t1 = Polygon([(0, y + R), (R, y + 2 * R), (-R, y + 2 * R)])
    y0 = y + 2 * R
    a = 8 - trap.area - 4
    w2 = cw / 2
    H = (a + cw * cw / 2) / cw
    if H < cw:
        return None
    chev = Polygon([(0, y0), (w2, y0 + w2), (w2, y0 + H), (0, y0 + H - w2), (-w2, y0 + H), (-w2, y0 + w2)])
    if abs(trap.area + 4 + chev.area - 8) > 1e-6:
        return None
    return unary_union([trap, t1, t2, chev])


# --- Два ромба
@tpl((4, 5), s=lat(-2.5, 2.5, 3, 4), side=[0, 1])
def two_diamonds(s, side):
    a = diamond(0, 0, 2)
    if side == 0:
        dx, dy = R + s * h, R - s * h
    else:
        dx, dy = R + s * h, -R + s * h
    b = diamond(dx, dy, 2)
    if a.intersection(b).area > 1e-9:
        return None
    u = unary_union([a, b])
    return u if u.geom_type == "Polygon" else None


# --- Цифра 1
@tpl((7, 0), a=lat(0.7, 2, 3, 3), b=lat(2.5, 5.5, 6, 4), c=lat(0.8, 4, 4, 5),
     d=lat(0.5, 2, 2, 3), e=lat(0.5, 3, 3, 4))
def one(a, b, c, d, e):
    return walk([("E", a), ("N", b), ("SW", c), ("SE", d), ("NE", e)], "S")


# --- Утюг
@tpl((5, 4), a=lat(0.5, 2, 2, 3), b=lat(1.5, 5, 5, 4), c=lat(0.5, 2, 2, 3), d=lat(0.3, 2, 2, 3),
     e=lat(0.3, 1.6, 2, 3), f=lat(0.3, 1.5, 2, 3), g=lat(0.5, 4, 4, 4))
def iron(a, b, c, d, e, f, g):
    return walk([("SE", a), ("E", b), ("NW", c), ("N", d), ("W", e), ("SW", f), ("W", g)], "SW")


# --- Стульчик
@tpl((7, 1), w=lat(1.5, 4.5, 4, 4), H=lat(2, 5, 5, 4), bw=lat(0.7, 1.6, 2, 3),
     s=lat(0.6, 1.6, 2, 3), n=lat(0.3, 1.6, 2, 3), k=lat(0.4, 2, 2, 3))
def chair(w, H, bw, s, n, k):
    # спинка справа, сиденье, слева «домик»
    k2x = w - bw - n - k * h  # горизонтальная проекция ската вниз-влево
    if k2x <= 0:
        return None
    k2 = k2x / h
    return walk([("E", w), ("N", H), ("W", bw), ("S", H - s), ("W", n), ("NW", k), ("SW", k2)], "S")


# --- Ракета
@tpl((4, 0), a=lat(0.3, 1.6, 2, 3), b=lat(0.5, 2.5, 3, 3), c=lat(0.7, 3.5, 4, 3),
     d=lat(0.3, 1.2, 2, 3), e=lat(0.4, 2.2, 3, 3))
def rocket(a, b, c, d, e):
    f = b + d + e / R
    return walk([("E", a), ("SE", b), ("E", c), ("SE", d), ("S", e), ("SW", d), ("W", c),
                 ("SW", b), ("W", a), ("NE", f), ("NW", f)])


# --- Ёлочка-стрелка: верхний треугольник, «крылья», ствол
@tpl((3, 0), tw=lat(0.7, 2.2, 2, 3), th=lat(0.4, 1.6, 2, 3), wl=lat(0.5, 2.5, 3, 3),
     wv=lat(0.3, 1.2, 2, 3), wo=lat(0.6, 3, 3, 3), e=lat(0.3, 1.6, 2, 3))
def tree_arrow(tw, th, wl, wv, wo, e):
    # от левого нижнего угла ствола по часовой стрелке... идём против: вправо
    apex_len = None
    # верхний треугольник: от правого края основания вверх-влево и вниз-влево
    # x-координата правого края основания:
    x = tw + wl * h - wo * h + e
    half = x - tw / 2
    if half <= 0:
        return None
    s = half * R
    return walk([("E", tw), ("N", th), ("SE", wl), ("N", wv), ("NW", wo), ("E", e),
                 ("NW", s), ("SW", s), ("E", e), ("SW", wo), ("S", wv), ("NE", wl)], "S")


# --- Свеча
@tpl((2, 2), cw=[1, R], e=lat(0.3, 1.5, 2, 3), cap=lat(0, 0.75, 1, 2), kh=lat(0.3, 1, 1, 2),
     q0=lat(-0.5, 1, 1, 2), fx=lat(-0.5, 1.2, 2, 3))
def candle(cw, e, cap, kh, q0, fx):
    base = Polygon([(-e, 0), (cw + e, 0), (cw, e), (0, e)])
    area_rest = 8 - 1 - 1 - (cw + e) * e - (cw + 2 * cap) * kh
    ch = area_rest / cw
    if ch < 1:
        return None
    col = box(0, e, cw, e + ch)
    capb = box(-cap, e + ch, cw + cap, e + ch + kh)
    y = e + ch + kh
    if q0 < -cap - 1e-9 or q0 + 1 > cw + cap + 1e-9:
        return None
    q = box(q0, y, q0 + 1, y + 1)
    if fx < q0 - 1e-9 or fx + h > q0 + 1 + 1e-9:
        return None
    fl = Polygon([(fx, y + 1), (fx + h, y + 1 + h), (fx + h, y + 1 + h + R), (fx, y + 1 + R)])
    u = unary_union([base, col, capb, q, fl])
    if abs(u.area - 8) > 1e-6:
        return None
    return u


# --- Кораблик: корпус-трапеция, большой парус (2 больших треугольника), кливер
@tpl((2, 0))
def sailboat():
    m = 4 - 2 * R
    hull = Polygon([(1, 0), (3, 0), (4, 1), (0, 1)])
    main = Polygon([(m, 1), (4, 1), (m, 1 + 2 * R)])
    jib = Polygon([(m - R, 1), (m, 1), (m, 1 + R)])
    return unary_union([hull, main, jib])


if __name__ == "__main__":
    import json
    out = sys.argv[1]
    cells = [tuple(map(int, a.split(","))) for a in sys.argv[2:]]
    try:
        res = json.load(open(out))
    except Exception:
        res = {}
    for cell in cells:
        fn, ranges = T[cell]
        print(cell, flush=True)
        sol, sc, p = fit(cell, fn, ranges, top=40, nodes=8000)
        if sol:
            res["%d,%d" % cell] = {"solution": sol, "cost": 1 - sc}
            json.dump(res, open(out, "w"))


