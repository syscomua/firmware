"""Печать контура силуэта с фото: направления (с шагом 45°) и длины в единицах."""
import math, sys
import cv2
from shapely.geometry import Polygon
from fuzzy import target_from_cell
from trace import load
PHOTO = '/root/.claude/uploads/746e9745-5d65-5192-98ab-5449622e39de/eaddfa52-image.jpg'
NAMES = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
im = load(PHOTO)
for a in sys.argv[1:]:
    r, c = map(int, a.split(","))
    T = target_from_cell(im, r, c, 66)
    geoms = T.geoms if T.geom_type == "MultiPolygon" else [T]
    print("==", a, "area %.2f" % T.area)
    for g in geoms:
        g = g.simplify(0.12)
        co = list(g.exterior.coords)
        if not Polygon(co).exterior.is_ccw:
            co = co[::-1]
        # старт — самая левая нижняя точка
        co = co[:-1]
        k = min(range(len(co)), key=lambda i: (round(co[i][1], 1), co[i][0]))
        co = co[k:] + co[:k] + [co[k]]
        out = []
        for p, q in zip(co, co[1:]):
            dx, dy = q[0] - p[0], q[1] - p[1]
            L = math.hypot(dx, dy)
            if L < 0.15:
                continue
            d = int(round(math.degrees(math.atan2(dy, dx)) / 45)) % 8
            out.append("%s %.2f" % (NAMES[d], L))
        print("  start (%.2f, %.2f):" % co[0], ", ".join(out))
