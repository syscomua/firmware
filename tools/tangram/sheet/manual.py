"""Фигуры, разложенные вручную (там, где автоматика с фото не справилась)."""
import math

R = math.sqrt(2)
h = R / 2


def house():
    return {
        # стены: прямоугольник 2√2 × √2
        "L1": [(0, R), (2 * R, R), (R, 0)],
        "M": [(0, 0), (R, 0), (0, R)],
        "S1": [(R, 0), (2 * R, 0), (3 * h, h)],
        "S2": [(2 * R, 0), (2 * R, R), (3 * h, h)],
        # крыша: левый скат — большой треугольник, правый — параллелограмм
        "L2": [(-h, R), (3 * h, R), (h, 2 * R)],
        "P": [(R, 3 * h), (3 * h, R), (5 * h, R), (2 * R, 3 * h)],
        # труба
        "Q": [(R, 3 * h), (R + 1, 3 * h), (R + 1, 3 * h + 1), (R, 3 * h + 1)],
    }


MANUAL = {
    "0,3": house,
}


import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from tg45 import Fig  # noqa: E402


def _f(build):
    f = Fig("m", "m")
    build(f)
    return dict(f.pieces)


def rocket():
    def b(f):
        f.put("L1", 0, at=(0, 0))
        f.put("L2", 180, at=(2, 2))
        f.put("M", 135, at=(3, 1))
        f.pieces["P"] = [(0, 1), (0, 2), (-1, 3), (-1, 2)]
        f.pieces["S1"] = [(0, 1), (0, 0), (-1, 0)]
        f.pieces["S2"] = [(0, 0), (-1, 0), (-1, -1)]
        f.pieces["Q"] = [(0, 1), (-h, 1 + h), (-R, 1), (-h, 1 - h)]
    return _f(b)


def fox():
    def b(f):
        # голова: розовый треугольник уголком вниз, уши — маленькие треугольники
        f.pieces["M"] = [(0, 1), (2, 1), (1, 0)]
        f.pieces["S1"] = [(0, 1), (1, 1), (0, 2)]
        f.pieces["S2"] = [(2, 1), (1, 1), (2, 2)]
        # шея — квадрат ромбиком под правой щекой
        x0 = 1 + R
        f.pieces["Q"] = [(1, 0), (1 + h, h), (x0, 0), (1 + h, -h)]
        # туловище и лапы — два больших треугольника уголком вниз
        f.pieces["L1"] = [(x0, 0), (x0 + 2 * R, 0), (x0 + R, -R)]
        f.pieces["L2"] = [(x0 + 2 * R, 0), (x0 + 4 * R, 0), (x0 + 3 * R, -R)]
        # хвост
        e = x0 + 4 * R
        f.pieces["P"] = [(e, 0), (e - h, -h), (e + h, -h), (e + R, 0)]
    return _f(b)


MANUAL.update({"4,0": rocket, "1,4": fox})


from shapely.geometry import Polygon as _Poly  # noqa: E402
import tg45 as _tg  # noqa: E402

_KIND = {"L1": "L", "L2": "L", "M": "M", "Q": "Q", "P": "P", "S1": "S", "S2": "S"}


def attach(pieces, name, a, b, prefer=(0, 0), at=None):
    """Положить деталь name так, чтобы её сторона лежала на отрезке a-b
    (вершина детали в точке a, если at не задан), без наложений.
    Из вариантов берётся тот, чей центр дальше всего в направлении prefer."""
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    best = None
    for _, _, pts in _tg.VARIANTS[_KIND[name]]:
        n = len(pts)
        for i in range(n):
            for j in ((i + 1) % n, (i - 1) % n):
                e = math.atan2(pts[j][1] - pts[i][1], pts[j][0] - pts[i][0])
                if abs((e - ang + math.pi) % (2 * math.pi) - math.pi) > 1e-6:
                    continue
                anchor = at if at is not None else a
                dx, dy = anchor[0] - pts[i][0], anchor[1] - pts[i][1]
                q = [(x + dx, y + dy) for x, y in pts]
                P = _Poly(q)
                if any(P.intersection(_Poly(o)).area > 1e-7 for o in pieces.values()):
                    continue
                c = P.centroid
                score = c.x * prefer[0] + c.y * prefer[1]
                if best is None or score > best[0]:
                    best = (score, q)
    if best is None:
        raise ValueError("не удалось положить %s" % name)
    pieces[name] = best[1]
    return best[1]


def bird():
    p = {}
    p["L1"] = [(0, 0), (2 * R, 0), (R, -R)]                      # туловище
    p["L2"] = [(2 * R, 0), (2 * R - 2, 0), (2 * R, 2)]           # правое крыло
    x = 2 * R - 2 - R
    p["M"] = [(x, 0), (x + R, 0), (x, R)]                         # левое крыло
    p["S1"] = [(x, 0), (x, 1), (x - 1, 0)]                        # голова
    p["P"] = [(2 * R + 2 * h, 0), (2 * R + h, -h), (2 * R - h, -h), (2 * R, 0)]  # хвост
    p["S2"] = [(2 * R - h, -h), (R, -R), (2 * R, -R)]
    p["Q"] = [(0, 0), (h, -h), (0, -R), (-h, -h)]
    return p


def rooster():
    p = {}
    p["S1"] = [(0, 0), (R, 0), (h, -h)]                           # лапы
    p["S2"] = [(R, 0), (2 * R, 0), (3 * h, -h)]
    p["L1"] = [(0, 0), (2 * R, 0), (R, R)]                        # туловище
    p["M"] = [(0, 0), (1, 1), (0, 2)]                             # шея
    p["Q"] = [(0, 2), (h, 2 - h), (R, 2), (h, 2 + h)]             # голова
    p["L2"] = [(2 * R, 0), (R, R), (3 * R, R)]                    # хвост
    p["P"] = [(2 * R, 0), (2 * R + 1, 0), (2 * R + 2, 1), (2 * R + 1, 1)]
    return p


def person():
    p = {}
    p["L1"] = [(0, 0), (2, 0), (0, 2)]                            # платье
    p["L2"] = [(2, 0), (2, 2), (0, 2)]
    p["M"] = [(0, 2), (2, 2), (1, 3)]                             # плечи
    p["Q"] = [(1, 3), (1 + h, 3 + h), (1, 3 + R), (1 - h, 3 + h)]  # голова
    p["P"] = [(2, 1), (2, 2), (3, 3), (3, 2)]                     # рука
    p["S1"] = [(3, 2), (4, 2), (3, 3)]                            # флажок
    p["S2"] = [(4, 2), (4, 3), (3, 3)]
    return p


def horse():
    p = {}
    p["L1"] = [(0, 0), (2 * R, 0), (R, -R)]                       # туловище
    p["L2"] = [(R, -R), (3 * R, -R), (2 * R, 0)]
    p["S1"] = [(R, -R), (2 * R, -R), (1.5 * R, -R - h)]           # ноги
    p["S2"] = [(2 * R, -R), (3 * R, -R), (2.5 * R, -R - h)]
    p["M"] = [(2 * R, 0), (2 * R + 1, -1), (2 * R + 1, 1)]        # хвост
    p["P"] = [(1, 0), (0, 0), (-1, 1), (0, 1)]                    # шея
    p["Q"] = [(-1, 1), (0, 1), (0, 2), (-1, 2)]                   # голова
    return p


def donkey():
    p = {}
    p["L1"] = [(0, 0), (2 * R, 0), (R, -R)]
    p["L2"] = [(R, -R), (3 * R, -R), (2 * R, 0)]
    p["S1"] = [(R, -R), (2 * R, -R), (1.5 * R, -R - h)]
    p["S2"] = [(2 * R, -R), (3 * R, -R), (2.5 * R, -R - h)]
    p["Q"] = [(0, 0), (1, 0), (1, 1), (0, 1)]                     # шея
    p["M"] = [(1, 1), (1 - R, 1), (1, 1 + R)]                     # голова
    attach(p, "P", (2 * R, 0), (3 * R, -R), prefer=(1, 1))        # хвост
    return p


def cat():
    p = {}
    x0 = 1 + R
    p["M"] = [(0, 1), (2, 1), (1, 0)]                             # мордочка
    p["S1"] = [(0, 1), (1, 1), (0, 2)]                            # уши
    p["S2"] = [(2, 1), (1, 1), (2, 2)]
    p["Q"] = [(1, 0), (1 + h, h), (x0, 0), (1 + h, -h)]           # шея
    p["L1"] = [(x0, 0), (x0 + 2 * R, 0), (x0 + R, -R)]            # туловище
    p["L2"] = [(x0 + R, -R), (x0 + 3 * R, -R), (x0 + 2 * R, 0)]
    attach(p, "P", (x0 + 2 * R, 0), (x0 + 3 * R, -R), prefer=(1, 2))  # хвост
    return p


def heron():
    p = {}
    # шея — параллелограмм стоймя, голова — маленький треугольник клювом вправо
    p["L1"] = [(0, 0), (2 * R, 0), (R, -R)]                       # туловище
    p["L2"] = [(0, 0), (R, -R), (0, -2 * R)]                      # хвост/крыло
    p["Q"] = [(2 * R - 1, 0), (2 * R, 0), (2 * R, 1), (2 * R - 1, 1)]
    p["P"] = [(2 * R - 1, 1), (2 * R, 1), (2 * R + 1, 2), (2 * R, 2)]  # шея
    p["S1"] = [(2 * R, 2), (2 * R + 1, 2), (2 * R, 3)]            # голова
    p["M"] = [(R, -R), (R + 1, -R - 1), (R - 1, -R - 1)]          # нога
    p["S2"] = [(R, -R - 1), (R + h, -R - 1 - h), (R - h, -R - 1 - h)]
    return p


MANUAL.update({"0,2": bird, "2,4": rooster, "3,2": person, "5,2": horse,
               "6,0": donkey, "7,4": cat, "0,0": heron})


def donkey2():
    p = {}
    p["L1"] = [(0, 0), (2 * R, 0), (R, -R)]
    p["L2"] = [(R, -R), (3 * R, -R), (2 * R, 0)]
    p["S1"] = [(R, -R), (2 * R, -R), (1.5 * R, -R - h)]
    p["S2"] = [(2 * R, -R), (3 * R, -R), (2.5 * R, -R - h)]
    p["Q"] = [(0, 0), (1, 0), (1, 1), (0, 1)]                     # шея
    attach(p, "M", (0, 1), (1, 1), prefer=(-1, 1))                # голова
    p["P"] = [(-R + 1, 1 + R), (1, 1 + R), (1 + h, 1 + R + h), (-R + 1 + h, 1 + R + h)][:0] or None
    del p["P"]
    attach(p, "P", (2 * R, 0), (2 * R + 1, 0), prefer=(1, 1))     # хвост
    return p


MANUAL["6,0"] = donkey2


def rooster2():
    p = {}
    p["S1"] = [(0, 0), (R, 0), (h, -h)]                           # лапы
    p["S2"] = [(R, 0), (2 * R, 0), (3 * h, -h)]
    p["L1"] = [(0, 0), (2 * R, 0), (R, R)]                        # туловище
    p["M"] = [(0, 0), (1, 1), (0, 2)]                             # шея
    p["Q"] = [(1, 1), (1 + h, 1 + h), (1, 1 + R), (1 - h, 1 + h)]  # голова
    p["L2"] = [(R, R), (2 * R, 0), (2 * R, 2 * R)]                # хвост
    p["P"] = [(2 * R, 2 * R), (2 * R, 2 * R - 1), (2 * R + 1, 2 * R - 2), (2 * R + 1, 2 * R - 1)]
    return p


def cat2():
    p = {}
    p["Q"] = [(0, 0), (h, h), (0, R), (-h, h)]                    # голова
    p["S1"] = [(0, R), (-h, h), (-h, R + h)]                      # уши
    p["S2"] = [(0, R), (h, h), (h, R + h)]
    p["L1"] = [(0, 0), (2 * R, 0), (R, R)]                        # туловище
    p["L2"] = [(R, R), (3 * R, R), (2 * R, 0)]
    p["M"] = [(2 * R - 2, 0), (2 * R, 0), (2 * R - 1, -1)]        # лапы
    attach(p, "P", (2 * R, 0), (3 * R, R), prefer=(1, 1))         # хвост
    return p


def person2():
    p = {}
    p["L1"] = [(0, 0), (0, 2 * R), (R, R)]                        # туловище
    p["M"] = [(0, 0), (R, 0), (R, R)]
    p["S1"] = [(0, 2 * R), (R, 2 * R), (h, 1.5 * R)]
    p["S2"] = [(R, 2 * R), (R, R), (h, 1.5 * R)]
    p["L2"] = [(R, 2 * R), (R + 2, 2 * R), (R, 2 * R - 2)]        # флажок
    p["Q"] = [(h, 2 * R), (R, 2 * R + h), (h, 2 * R + R), (0, 2 * R + h)]  # голова
    attach(p, "P", (0, 2 * R + h), (h, 2 * R + R), prefer=(-1, 2))  # шапка
    return p


MANUAL.update({"2,4": rooster2, "7,4": cat2, "3,2": person2})


def candle():
    from shapely.geometry import Polygon as P_
    sil = P_([(0, 0), (4, 0), (3, 1), (3, 3), (2, 4), (1, 3), (1, 1)])
    return {k: list(v) for k, v in _tg.solve45_geom(sil)[0].items()}


MANUAL["2,2"] = candle
