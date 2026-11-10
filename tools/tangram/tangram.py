#!/usr/bin/env python3
"""
Танграм: 7 долей, автоматический подбор и генерация фигур.

Методика
--------
1. Дискретизация. Квадрат танграма имеет сторону 4. Каждая единичная клетка
   режется обеими диагоналями на 4 элементарных треугольника (S, E, N, W).
   Все стороны всех долей идут либо по линиям сетки, либо по диагоналям
   клеток, поэтому любая доля — это ровно набор таких треугольников
   (большой треугольник = 16 шт., средний/квадрат/параллелограмм = 8,
   маленький = 4; всего 64).

   Треугольник храним как одну целочисленную точку — его центр тяжести в
   координатах x6. Повороты на 90° и зеркальные отражения — это просто
   линейные преобразования этих точек, сдвиги — на кратные 6.

2. "Собрать заданную фигуру" = задача точного покрытия (exact cover):
   столбцы — 7 долей + все треугольники силуэта, строки — все допустимые
   положения каждой доли внутри силуэта. Решаем алгоритмом X Кнута.

3. "Придумать новые фигуры" = случайный рост: доли по одной прикладываются
   к уже выложенным так, чтобы касаться по стороне и не перекрываться.
   Вариант --style compact предпочитает положения с большим числом общих
   сторон (фигуры получаются плотнее и "читаемее"). Силуэт такой фигуры —
   готовая головоломка, а решение уже известно.

4. "Найти все фигуры определённого класса" = перебор силуэтов + проверка
   решателем. Команда convex перебирает все выпуклые многоугольники
   площади 16 со сторонами по 8 направлениям и находит ровно 13 собираемых —
   это совпадает с теоремой Ванга–Сюна (1942).

Ограничение: доли поворачиваются на 90° (и могут переворачиваться). Повороты
на 45° меняют решётку (появляется sqrt(2)), их эта модель не покрывает.

Примеры
-------
  python3 tangram.py pieces                     # разбивка квадрата на доли
  python3 tangram.py targets                    # список встроенных фигур
  python3 tangram.py solve house                # собрать "домик"
  python3 tangram.py solve all --max 3          # все встроенные фигуры
  python3 tangram.py convex                     # все 13 выпуклых фигур
  python3 tangram.py solve --poly "0,0 8,0 8,2 0,2" --max 20
  python3 tangram.py random -n 24 --seed 7      # 24 новые фигуры
  python3 tangram.py random -n 12 --puzzle      # силуэты + ответы
  python3 tangram.py random -n 12 --symmetric --no-holes
"""

import argparse
import math
import os
import random
import sys

# --------------------------------------------------------------------------
# Доли (как на фото: квадрат 4x4, ось y вверх)
# --------------------------------------------------------------------------

PIECES = [
    # name, kind, color, polygon
    ("L1", "large",  "#1f5a2c", [(0, 0), (4, 0), (2, 2)]),          # тёмно-зелёный, низ
    ("L2", "large",  "#e8a530", [(4, 0), (4, 4), (2, 2)]),          # оранжевый, справа
    ("M",  "medium", "#e0457b", [(0, 4), (0, 2), (2, 4)]),          # розовый, верх-лево
    ("SQ", "square", "#2f62d9", [(2, 2), (3, 3), (2, 4), (1, 3)]),  # синий квадрат
    ("S1", "small",  "#6cc08b", [(2, 4), (4, 4), (3, 3)]),          # светло-зелёный
    ("S2", "small",  "#b8222b", [(1, 1), (2, 2), (1, 3)]),          # красный (у шва)
    ("P",  "parallelogram", "#d93a3a", [(0, 0), (1, 1), (1, 3), (0, 2)]),  # красный
]
PIECE_BY_NAME = {p[0]: p for p in PIECES}

TARGETS = {
    "square":        [(0, 0), (4, 0), (4, 4), (0, 4)],
    "triangle":      [(0, 0), (8, 0), (4, 4)],
    "rectangle":     [(2, 0), (6, 4), (4, 6), (0, 2)],
    "parallelogram": [(0, 0), (4, 0), (8, 4), (4, 4)],
    "hexagon":       [(2, 0), (4, 0), (6, 2), (4, 4), (2, 4), (0, 2)],
    "boat":          [(2, 0), (6, 0), (8, 2), (6, 2), (4, 4), (2, 2), (0, 2)],
}

# --------------------------------------------------------------------------
# Геометрия решётки (точки в масштабе x6 = центры треугольников)
# --------------------------------------------------------------------------

SCALE = 6
OFFSETS = [(0, -2), (2, 0), (0, 2), (-2, 0)]  # S, E, N, W
TRANSFORMS = [
    lambda x, y: (x, y), lambda x, y: (-y, x),
    lambda x, y: (-x, -y), lambda x, y: (y, -x),
    lambda x, y: (-x, y), lambda x, y: (y, x),
    lambda x, y: (x, -y), lambda x, y: (-y, -x),
]


def point_in_poly(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            # x-координата пересечения, сравнение без деления
            lhs = (px - x1) * (y2 - y1)
            rhs = (x2 - x1) * (py - y1)
            if (lhs < rhs) == (y2 > y1):
                inside = not inside
    return inside


def rasterize(poly6):
    """Полигон (координаты x6) -> frozenset центров элементарных треугольников."""
    xs = [p[0] for p in poly6]
    ys = [p[1] for p in poly6]
    cx0, cx1 = min(xs) // SCALE, max(xs) // SCALE
    cy0, cy1 = min(ys) // SCALE, max(ys) // SCALE
    cells = set()
    for cx in range(cx0, cx1 + 1):
        for cy in range(cy0, cy1 + 1):
            for ox, oy in OFFSETS:
                px, py = cx * SCALE + 3 + ox, cy * SCALE + 3 + oy
                if point_in_poly(px, py, poly6):
                    cells.add((px, py))
    return frozenset(cells)


def scaled(poly):
    return [(x * SCALE, y * SCALE) for x, y in poly]


def normalize(poly6, cells):
    mx = min(x for x, _ in cells) // SCALE * SCALE
    my = min(y for _, y in cells) // SCALE * SCALE
    return ([(x - mx, y - my) for x, y in poly6],
            frozenset((x - mx, y - my) for x, y in cells))


def neighbours(p):
    """Треугольники, имеющие с p общую сторону."""
    x, y = p
    for ox, oy in OFFSETS:
        if (x % SCALE - 3, y % SCALE - 3) == (ox, oy):
            cx, cy = x - ox, y - oy
            yield (x + ox, y + oy)            # через сторону клетки
            yield (cx - oy, cy + ox)          # соседи внутри клетки
            yield (cx + oy, cy - ox)
            return


def orientations(name, allow_flip=True):
    """Все различные положения доли: список (poly6, cells), нормализованных."""
    poly6 = scaled(PIECE_BY_NAME[name][3])
    seen, out = set(), []
    for i, tf in enumerate(TRANSFORMS):
        if i >= 4 and not allow_flip:
            break
        tp = [tf(x, y) for x, y in poly6]
        cells = rasterize(tp)
        tp, cells = normalize(tp, cells)
        if cells not in seen:
            seen.add(cells)
            out.append((tp, cells))
    return out


def shift(poly6, cells, dx, dy):
    return ([(x + dx, y + dy) for x, y in poly6],
            frozenset((x + dx, y + dy) for x, y in cells))


# --------------------------------------------------------------------------
# Алгоритм X (Кнут), реализация на словарях
# --------------------------------------------------------------------------

def algorithm_x(X, Y, solution=None):
    if solution is None:
        solution = []
    if not X:
        yield list(solution)
        return
    c = min(X, key=lambda col: len(X[col]))
    for r in list(X[c]):
        solution.append(r)
        cols = _select(X, Y, r)
        yield from algorithm_x(X, Y, solution)
        _deselect(X, Y, r, cols)
        solution.pop()


def _select(X, Y, r):
    cols = []
    for j in Y[r]:
        for i in X[j]:
            for k in Y[i]:
                if k != j:
                    X[k].remove(i)
        cols.append(X.pop(j))
    return cols


def _deselect(X, Y, r, cols):
    for j in reversed(Y[r]):
        X[j] = cols.pop()
        for i in X[j]:
            for k in Y[i]:
                if k != j:
                    X[k].add(i)


def symmetries(cells):
    """Преобразования решётки, переводящие набор треугольников сам в себя."""
    base = normalize_cells(cells)
    return [tf for tf in TRANSFORMS
            if normalize_cells([tf(x, y) for x, y in cells]) == base]


def normalize_cells(cells):
    mx = min(x for x, _ in cells) // SCALE * SCALE
    my = min(y for _, y in cells) // SCALE * SCALE
    return frozenset((x - mx, y - my) for x, y in cells)


def solution_key(placed, syms):
    """Ключ решения: одинаковые доли не различаем, повороты фигуры тоже."""
    best = None
    for tf in syms:
        allp = [tf(x, y) for _, _, c in placed for x, y in c]
        mx = min(x for x, _ in allp) // SCALE * SCALE
        my = min(y for _, y in allp) // SCALE * SCALE
        k = tuple(sorted((PIECE_BY_NAME[n][1],
                          tuple(sorted((tf(x, y)[0] - mx, tf(x, y)[1] - my) for x, y in c)))
                         for n, _, c in placed))
        if best is None or k < best:
            best = k
    return best


def solve(target_poly, allow_flip=True, limit=None, keep_symmetric=False):
    """Генератор решений. Решение = список (name, poly6, cells).

    По умолчанию решения, отличающиеся только поворотом/отражением всей
    фигуры или перестановкой одинаковых долей, считаются одним."""
    target = rasterize(scaled(target_poly))
    if len(target) != 64:
        raise ValueError(
            "площадь фигуры должна быть 16 (64 треугольника), сейчас %g"
            % (len(target) / 4))
    minx = min(x for x, _ in target) // SCALE * SCALE
    miny = min(y for _, y in target) // SCALE * SCALE
    maxx = max(x for x, _ in target)
    maxy = max(y for _, y in target)

    Y = {}
    for name, *_ in PIECES:
        for k, (poly6, cells) in enumerate(orientations(name, allow_flip)):
            w = max(x for x, _ in cells)
            h = max(y for _, y in cells)
            for dx in range(minx, maxx - w + SCALE, SCALE):
                for dy in range(miny, maxy - h + SCALE, SCALE):
                    _, moved = shift(poly6, cells, dx, dy)
                    if moved <= target:
                        Y[(name, k, dx, dy)] = [name] + sorted(moved)
    X = {col: set() for col in [p[0] for p in PIECES] + sorted(target)}
    for r, cols in Y.items():
        for c in cols:
            X[c].add(r)

    orient_cache = {name: orientations(name, allow_flip) for name, *_ in PIECES}
    syms = [TRANSFORMS[0]] if keep_symmetric else symmetries(target)
    seen = set()
    for sol in algorithm_x(X, Y):
        placed = []
        for name, k, dx, dy in sol:
            poly6, cells = shift(*orient_cache[name][k], dx, dy)
            placed.append((name, poly6, cells))
        key = solution_key(placed, syms)
        if key in seen:
            continue
        seen.add(key)
        yield placed
        if limit and len(seen) >= limit:
            return


# --------------------------------------------------------------------------
# Генерация новых фигур
# --------------------------------------------------------------------------

def contacts(cells, occupied):
    return sum(1 for p in cells for q in neighbours(p) if q in occupied)


def random_figure(rng, style="compact", allow_flip=True, max_size=None):
    names = [p[0] for p in PIECES]
    rng.shuffle(names)
    first = names[0]
    poly6, cells = rng.choice(orientations(first, allow_flip))
    placed = [(first, poly6, cells)]
    occupied = set(cells)

    for name in names[1:]:
        border = {q for p in occupied for q in neighbours(p) if q not in occupied}
        candidates = []
        for poly6, cells in orientations(name, allow_flip):
            shifts = set()
            for b in border:
                for s in cells:
                    dx, dy = b[0] - s[0], b[1] - s[1]
                    if dx % SCALE == 0 and dy % SCALE == 0:
                        shifts.add((dx, dy))
            for dx, dy in shifts:
                p2, c2 = shift(poly6, cells, dx, dy)
                if c2 & occupied:
                    continue
                if max_size is not None:
                    allc = occupied | c2
                    if (max(x for x, _ in allc) - min(x for x, _ in allc) > max_size * SCALE or
                            max(y for _, y in allc) - min(y for _, y in allc) > max_size * SCALE):
                        continue
                candidates.append((contacts(c2, occupied), p2, c2))
        if not candidates:
            return None
        if style == "compact":
            weights = [math.exp(1.2 * c) for c, _, _ in candidates]
        elif style == "loose":
            weights = [1.0 / c for c, _, _ in candidates]
        else:
            weights = None
        _, p2, c2 = rng.choices(candidates, weights=weights)[0]
        placed.append((name, p2, c2))
        occupied |= c2
    return placed


def perimeter_edges(placed):
    occ = set().union(*(c for _, _, c in placed))
    return sum(1 for p in occ for q in neighbours(p) if q not in occ)


def has_hole(placed):
    occ = set().union(*(c for _, _, c in placed))
    xs = [x for x, _ in occ]
    ys = [y for _, y in occ]
    x0, x1 = min(xs) - SCALE, max(xs) + SCALE
    y0, y1 = min(ys) - SCALE, max(ys) + SCALE
    start = (x0 // SCALE * SCALE + 1, y0 // SCALE * SCALE + 3)
    seen, stack = {start}, [start]
    while stack:
        p = stack.pop()
        for q in neighbours(p):
            if (q not in seen and q not in occ and
                    x0 <= q[0] <= x1 and y0 <= q[1] <= y1):
                seen.add(q)
                stack.append(q)
    total = 0
    for cx in range(x0 // SCALE, x1 // SCALE + 1):
        for cy in range(y0 // SCALE, y1 // SCALE + 1):
            for ox, oy in OFFSETS:
                q = (cx * SCALE + 3 + ox, cy * SCALE + 3 + oy)
                if x0 <= q[0] <= x1 and y0 <= q[1] <= y1:
                    total += 1
    return total - len(occ) != len(seen)


def figure_key(placed):
    """Канонический вид силуэта с точностью до поворотов/отражений/сдвигов."""
    occ = set().union(*(c for _, _, c in placed))
    best = None
    for tf in TRANSFORMS:
        pts = [tf(x, y) for x, y in occ]
        mx = min(x for x, _ in pts) // SCALE * SCALE
        my = min(y for _, y in pts) // SCALE * SCALE
        k = tuple(sorted((x - mx, y - my) for x, y in pts))
        if best is None or k < best:
            best = k
    return best



def is_symmetric(placed):
    occ = set().union(*(c for _, _, c in placed))
    return len(symmetries(occ)) > 1


DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def convex_shapes(max_side=8):
    """Перебор всех выпуклых многоугольников площади 16 со сторонами по
    8 направлениям решётки (стороны n_i шагов по направлению DIRS[i]).
    Возвращает список полигонов, разных с точностью до симметрии."""
    out, keys = [], set()
    R = range(max_side + 1)
    for n0 in R:
        for n1 in R:
            for n2 in R:
                for n3 in R:
                    for n5 in R:
                        for n7 in R:
                            n4 = n0 + n1 - n3 - n5 + n7
                            n6 = n1 + n2 + n3 - n5 - n7
                            if not (0 <= n4 <= max_side and 0 <= n6 <= max_side):
                                continue
                            n = (n0, n1, n2, n3, n4, n5, n6, n7)
                            poly, x, y = [], 0, 0
                            for (dx, dy), k in zip(DIRS, n):
                                if k:
                                    poly.append((x, y))
                                    x, y = x + dx * k, y + dy * k
                            if len(poly) < 3:
                                continue
                            a2 = sum(poly[i][0] * poly[i - 1][1] - poly[i - 1][0] * poly[i][1]
                                     for i in range(len(poly)))
                            if abs(a2) != 32:
                                continue
                            key = figure_key([(None, None, rasterize(scaled(poly)))])
                            if key not in keys:
                                keys.add(key)
                                out.append(poly)
    return out

# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------

def _poly_svg(poly6, ox, oy, s, fill, stroke, sw):
    pts = " ".join("%.2f,%.2f" % (ox + x * s, oy - y * s) for x, y in poly6)
    return ('<polygon points="%s" fill="%s" stroke="%s" stroke-width="%.2f" '
            'stroke-linejoin="round"/>' % (pts, fill, stroke, sw))


def figure_svg(placed, ox, oy, box, silhouette=False, labels=False):
    """Рисует фигуру, вписанную в квадрат box x box с левым верхним углом (ox, oy)."""
    xs = [x for _, poly, _ in placed for x, _ in poly]
    ys = [y for _, poly, _ in placed for _, y in poly]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    s = box * 0.88 / max(w, h)
    bx = ox + (box - w * s) / 2 - min(xs) * s
    by = oy + box - (box - h * s) / 2 + min(ys) * s
    out = []
    for name, poly6, _ in placed:
        if silhouette:
            out.append(_poly_svg(poly6, bx, by, s, "#222", "#222", 1.2))
        else:
            out.append(_poly_svg(poly6, bx, by, s, PIECE_BY_NAME[name][2], "#fff", 1.6))
            if labels:
                cx = sum(x for x, _ in poly6) / len(poly6)
                cy = sum(y for _, y in poly6) / len(poly6)
                out.append('<text x="%.1f" y="%.1f" font-size="%d" fill="#fff" '
                           'text-anchor="middle" dominant-baseline="middle" '
                           'font-family="sans-serif" font-weight="bold">%s</text>'
                           % (bx + cx * s, by - cy * s, max(10, box // 14), name))
    return "\n".join(out)


def gallery_svg(items, path, cols=4, box=220, title=None):
    """items: список (caption, placed, silhouette, labels)."""
    pad, cap = 16, 22
    top = 40 if title else 0
    rows = (len(items) + cols - 1) // cols
    W = cols * (box + pad) + pad
    H = top + rows * (box + cap + pad) + pad
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="0 0 %d %d">' % (W, H, W, H),
             '<rect width="100%" height="100%" fill="#f7f5f0"/>']
    if title:
        parts.append('<text x="%d" y="28" font-size="20" font-family="sans-serif" '
                     'fill="#333">%s</text>' % (pad, title))
    for i, (caption, placed, sil, labels) in enumerate(items):
        r, c = divmod(i, cols)
        x = pad + c * (box + pad)
        y = top + pad + r * (box + cap + pad)
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="8" fill="#fff" '
                     'stroke="#ddd"/>' % (x, y, box, box))
        parts.append(figure_svg(placed, x, y, box, sil, labels))
        parts.append('<text x="%d" y="%d" font-size="14" font-family="sans-serif" '
                     'fill="#444" text-anchor="middle">%s</text>'
                     % (x + box // 2, y + box + 16, caption))
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("записано:", path)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def base_layout():
    return [(n, scaled(poly), rasterize(scaled(poly))) for n, _, _, poly in PIECES]


def cmd_pieces(a):
    items = [("исходный квадрат", base_layout(), False, True)]
    for n, kind, _, poly in PIECES:
        p6 = scaled(poly)
        c = rasterize(p6)
        items.append(("%s: %s, площадь %g" % (n, kind, len(c) / 4), [(n, p6, c)], False, False))
    gallery_svg(items, os.path.join(a.out, "pieces.svg"), cols=4, title="Доли танграма")


def cmd_targets(a):
    for name, poly in TARGETS.items():
        print("%-14s %s" % (name, " ".join("%d,%d" % p for p in poly)))


def cmd_solve(a):
    if a.poly:
        poly = [tuple(int(v) for v in pt.split(",")) for pt in a.poly.split()]
        jobs = [("custom", poly)]
    elif a.target == "all":
        jobs = list(TARGETS.items())
    elif a.target in TARGETS:
        jobs = [(a.target, TARGETS[a.target])]
    else:
        sys.exit("неизвестная фигура: %s (см. 'targets')" % a.target)

    items = []
    for name, poly in jobs:
        try:
            sols = list(solve(poly, not a.no_flip, a.max, a.keep_symmetric))
        except ValueError as e:
            print("%s: %s" % (name, e))
            continue
        print("%-14s решений: %d%s" % (name, len(sols),
                                       "+" if a.max and len(sols) >= a.max else ""))
        if not sols:
            continue
        p6 = scaled(poly)
        items.append(("%s (силуэт)" % name, [("M", p6, rasterize(p6))], True, False))
        for i, s in enumerate(sols):
            items.append(("%s #%d" % (name, i + 1), s, False, a.labels))
    if items:
        fname = "solve_%s.svg" % (jobs[0][0] if len(jobs) == 1 else "all")
        gallery_svg(items, os.path.join(a.out, fname), cols=a.cols,
                    title="Сборка фигур (точное покрытие, алгоритм X)")


def cmd_convex(a):
    shapes = convex_shapes()
    items = []
    for poly in shapes:
        sols = list(solve(poly, not a.no_flip, a.max))
        if sols:
            items.append(("выпуклая #%d, решений %d%s" % (
                len(items) + 1, len(sols), "+" if a.max and len(sols) >= a.max else ""),
                sols[0], False, a.labels))
    print("многоугольников площади 16 проверено: %d, собираются: %d"
          % (len(shapes), len(items)))
    gallery_svg(items, os.path.join(a.out, "convex.svg"), cols=a.cols,
                title="Все выпуклые фигуры из 7 долей (найдены перебором)")


def cmd_random(a):
    rng = random.Random(a.seed)
    figures, keys = [], set()
    tries = 0
    while len(figures) < a.n and tries < a.n * (5000 if a.symmetric else 200):
        tries += 1
        f = random_figure(rng, a.style, not a.no_flip, a.max_size)
        if f is None or (a.symmetric and not is_symmetric(f)):
            continue
        if a.no_holes and has_hole(f):
            continue
        k = figure_key(f)
        if k in keys:
            continue
        keys.add(k)
        figures.append(f)
    figures.sort(key=perimeter_edges)
    items = []
    for i, f in enumerate(figures):
        cap = "#%d  периметр %d" % (i + 1, perimeter_edges(f))
        if a.puzzle:
            items.append(("задача " + cap, f, True, False))
        items.append(("ответ " + cap if a.puzzle else cap, f, False, a.labels))
    gallery_svg(items, os.path.join(a.out, "random.svg"),
                cols=a.cols if not a.puzzle else max(2, a.cols - a.cols % 2),
                title="Случайные фигуры из 7 долей (seed=%s, style=%s)" % (a.seed, a.style))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="out", help="папка для SVG (по умолчанию ./out)")
    ap.add_argument("--no-flip", action="store_true",
                    help="запретить переворачивать доли (параллелограмм)")
    ap.add_argument("--labels", action="store_true", help="подписывать доли")
    ap.add_argument("--cols", type=int, default=4)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("pieces", help="нарисовать доли и исходный квадрат")
    sub.add_parser("targets", help="список встроенных фигур")

    s = sub.add_parser("solve", help="собрать заданную фигуру")
    s.add_argument("target", nargs="?", default="all")
    s.add_argument("--poly", help='свой силуэт: "x,y x,y ..." (площадь 16)')
    s.add_argument("--max", type=int, default=8, help="сколько решений искать (0 = все)")
    s.add_argument("--keep-symmetric", action="store_true",
                   help="не склеивать решения, отличающиеся поворотом всей фигуры")

    c = sub.add_parser("convex", help="найти все выпуклые фигуры перебором")
    c.add_argument("--max", type=int, default=50, help="предел решений на фигуру")

    r = sub.add_parser("random", help="сгенерировать новые фигуры")
    r.add_argument("-n", type=int, default=16)
    r.add_argument("--seed", type=int, default=None)
    r.add_argument("--style", choices=["compact", "uniform", "loose"], default="compact")
    r.add_argument("--max-size", type=int, default=None,
                   help="ограничить габарит фигуры (в единицах, квадрат = 4)")
    r.add_argument("--no-holes", action="store_true", help="отбрасывать фигуры с дырками")
    r.add_argument("--symmetric", action="store_true",
                   help="оставлять только симметричные фигуры")
    r.add_argument("--puzzle", action="store_true", help="силуэт-задача + ответ")

    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    {"pieces": cmd_pieces, "targets": cmd_targets, "convex": cmd_convex,
     "solve": cmd_solve, "random": cmd_random}[a.cmd](a)


if __name__ == "__main__":
    main()
