"""
Автоматическое снятие силуэтов с фото листка.

1. Ячейка -> порог (Оцу) -> компоненты, не касающиеся рамки -> контуры.
2. Упрощение контура (approxPolyDP), направления сторон -> ближайшие 45°.
3. Масштаб: площадь силуэта = 8 (катет маленького треугольника = 1).
4. Длины сторон -> вида m + n*sqrt(2); перебор (beam search) так, чтобы контур
   точно замкнулся и площадь была ровно 8.
Числа храним точно: p + q*h, где h = sqrt(2)/2.
"""
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crop_cells import LX, RX, LY, RY  # noqa: E402

H = math.sqrt(2) / 2
DIRV = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
# длины вида m + n*sqrt(2) = (m, 2n) в базисе (1, h)
LENGTHS = sorted({(m, 2 * n) for m in range(0, 8) for n in range(0, 6)
                  if 0 < m + n * math.sqrt(2) <= 7.5}, key=lambda t: t[0] + t[1] * H)


def val(t):
    return t[0] + t[1] * H


def mul_h(t):
    # (p + q h) * h = p h + q/2  -> только если q чётно
    p, q = t
    assert q % 2 == 0
    return (q // 2, p)


def load(path):
    return ImageOps.exif_transpose(Image.open(path)).convert("L")


def cell_image(im, r, c, half=60):
    k = im.size[0] / 1500
    vx = LX[r][c] if c < 3 else RX[c - 3]
    vy = LY[r] if c < 3 else RY[r]
    X, Y = 100 + vx * 1.278, 380 + vy * 1.277
    h = half * 1.278
    box = tuple(int(v * k) for v in (X - h, Y - h, X + h, Y + h))
    return np.array(im.crop(box))


def flatten(g):
    """Выровнять освещение (тени, блики): делим на оценку фона."""
    g = g.astype(np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (161, 161))
    bg = cv2.GaussianBlur(cv2.morphologyEx(g, cv2.MORPH_CLOSE, k), (0, 0), 20)
    return np.clip(g / np.maximum(bg, 1) * 220, 0, 255).astype(np.uint8)


def contours(g):
    g = cv2.GaussianBlur(flatten(g), (5, 5), 0)
    _, th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(th)
    Hh, Ww = th.shape
    keep = np.zeros_like(th)
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a < 150:
            continue
        fill = a / float(w * h)
        if (w > 0.6 * Ww or h > 0.6 * Hh) and fill < 0.25:
            continue  # линии рамки
        if min(w, h) < 12:
            continue  # тонкие линии
        if x <= 1 or y <= 1 or x + w >= Ww - 1 or y + h >= Hh - 1:
            if fill < 0.35:
                continue
        keep[lab == i] = 255
    cs, hier = cv2.findContours(keep, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    return keep, cs, hier


def simplify(cnt, eps_frac=0.012):
    peri = cv2.arcLength(cnt, True)
    ap = cv2.approxPolyDP(cnt, eps_frac * peri, True)
    return [(float(p[0][0]), -float(p[0][1])) for p in ap]  # y вверх


def snap_polygon(pts, u, beam=4000, keep=40, ncand=4):
    """pts в пикселях (y вверх) -> [(dir_idx, length_tuple)], стоимость, площадь."""
    n = len(pts)
    edges = []
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        dx, dy = (x1 - x0) / u, (y1 - y0) / u
        L = math.hypot(dx, dy)
        if L < 0.15:
            continue
        a = math.degrees(math.atan2(dy, dx)) % 360
        d = int(round(a / 45)) % 8
        edges.append((d, L))
    # слить соседние стороны одного направления
    merged = []
    for d, L in edges:
        if merged and merged[-1][0] == d:
            merged[-1] = (d, merged[-1][1] + L)
        else:
            merged.append((d, L))
    if len(merged) > 1 and merged[0][0] == merged[-1][0]:
        d, L = merged.pop()
        merged[0] = (d, merged[0][1] + L)
    edges = merged
    # кандидаты длин
    cands = []
    for d, L in edges:
        cs = sorted(LENGTHS, key=lambda t: abs(val(t) - L))[:ncand]
        cands.append([(t, abs(val(t) - L) / max(L, 0.5)) for t in cs])
    # beam search по частичным суммам (x = (p,q), y = (p,q))
    states = {(0, 0, 0, 0): [(0.0, [])]}
    for (d, L), cl in zip(edges, cands):
        nxt = {}
        for st, lst in states.items():
            for cost, choice in lst:
                for t, c in cl:
                    vx, vy = DIRV[d]
                    comp = mul_h(t) if (vx and vy) else t
                    s = (st[0] + vx * comp[0], st[1] + vx * comp[1],
                         st[2] + vy * comp[0], st[3] + vy * comp[1])
                    nxt.setdefault(s, []).append((cost + c, choice + [t]))
        for s in nxt:
            nxt[s] = sorted(nxt[s], key=lambda e: e[0])[:keep]
        if len(nxt) > beam:
            nxt = dict(sorted(nxt.items(), key=lambda kv: kv[1][0][0])[:beam])
        states = nxt
    if (0, 0, 0, 0) not in states:
        return []
    return [([(d, t) for (d, _), t in zip(edges, choice)], cost)
            for cost, choice in states[(0, 0, 0, 0)]]


def to_points(snapped, start=(0.0, 0.0)):
    x, y = start
    pts = []
    for d, t in snapped:
        pts.append((x, y))
        vx, vy = DIRV[d]
        L = val(t)
        if vx and vy:
            x, y = x + vx * L * H, y + vy * L * H
        else:
            x, y = x + vx * L, y + vy * L
    return pts


def area(pts):
    return abs(sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1]
                   for i in range(len(pts)))) / 2
