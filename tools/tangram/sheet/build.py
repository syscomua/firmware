"""
Сборка: auto.json / fuzzy.json / manual.py -> figures.json -> tangram.html

  python3 build.py merge AUTO.json [FUZZY.json key,key...]   # обновить figures.json
  python3 build.py html OUT.html                              # собрать страницу
"""
import json
import os
import sys

from shapely.geometry import Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import instructions  # noqa
import manual  # noqa

FIGS = os.path.join(HERE, "figures.json")

NAMES = {
    "0,0": "Аист", "0,1": "Заяц", "0,2": "Летящая птица", "0,3": "Домик", "0,4": "Лебедь",
    "0,5": "Параллелограмм",
    "1,0": "Прямоугольник", "1,1": "Собака", "1,2": "Гусь", "1,3": "Рыбка", "1,4": "Лиса",
    "1,5": "Ёлка",
    "2,0": "Кораблик", "2,1": "Голубь", "2,2": "Свеча", "2,3": "Самолёт", "2,4": "Петух",
    "2,5": "Кошка",
    "3,0": "Ёлочка", "3,1": "Квадрат", "3,2": "Человечек", "3,3": "Краб", "3,4": "Меч",
    "3,5": "Трапеция",
    "4,0": "Ракета", "4,1": "Бутылка", "4,2": "Ваза", "4,3": "Цветок", "4,4": "Ёлка с пеньком",
    "4,5": "Два ромба",
    "5,0": "Молния", "5,1": "Горы", "5,2": "Конь", "5,3": "Лестница", "5,4": "Утюг",
    "5,5": "Улитка",
    "6,0": "Ослик", "6,1": "Буква Т", "6,2": "Сердце", "6,3": "Кенгуру", "6,4": "Шестиугольник",
    "6,5": "Бантик",
    "7,0": "Цифра 1", "7,1": "Стульчик", "7,2": "Корона", "7,3": "Воронка", "7,4": "Котик",
    "7,5": "Фонарик",
}


def exactify(sol):
    """Подогнать каждую деталь к точной форме (убрать погрешность 1e-6)."""
    import math
    import tg45
    kinds = {"L1": "L", "L2": "L", "M": "M", "Q": "Q", "P": "P", "S1": "S", "S2": "S"}
    out = {}
    for n, pts in sol.items():
        best = None
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        for _, _, var in tg45.VARIANTS[kinds[n]]:
            vx = sum(x for x, _ in var) / len(var)
            vy = sum(y for _, y in var) / len(var)
            q = [(x - vx + cx, y - vy + cy) for x, y in var]
            d = max(min(math.dist(a, b) for b in pts) for a in q)
            if best is None or d < best[0]:
                best = (d, q)
        assert best[0] < 0.05, (n, best[0])
        out[n] = best[1]
    return out


# Фигуры, собранные «по мотивам» листка: силуэт упрощён или отличается в деталях
ADAPTED = {"6,0", "2,0", "4,0", "4,5", "7,5", "2,4"}


def check(sol):
    assert sorted(sol) == sorted(instructions.NAMES), sorted(sol)
    ps = {k: Polygon(v) for k, v in sol.items()}
    ks = list(ps)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            a = ps[ks[i]].intersection(ps[ks[j]]).area
            assert a < 1e-4, (ks[i], ks[j], a)
    tot = sum(p.area for p in ps.values())
    assert abs(tot - 8) < 1e-4, tot


def merge(args):
    figs = json.load(open(FIGS)) if os.path.exists(FIGS) else {}
    auto = json.load(open(args[0]))
    for k, v in auto.items():
        if figs.get(k, {}).get("source") in ("manual", "fuzzy", "fixed"):
            continue
        figs[k] = {"solution": v["solution"], "source": "photo"}
    if len(args) > 2:
        fz = json.load(open(args[1]))
        for k in args[2:]:
            figs[k] = {"solution": fz[k]["solution"], "source": "fuzzy"}
    for k, fn in manual.MANUAL.items():
        figs[k] = {"solution": fn(), "source": "manual"}
    fx = os.path.join(HERE, "fixes.json")
    if os.path.exists(fx):
        for k, v in json.load(open(fx)).items():
            figs[k] = {"solution": v["solution"], "source": "fixed"}
    for k, v in figs.items():
        v["solution"] = {n: [[round(x, 6), round(y, 6)] for x, y in pts]
                         for n, pts in exactify(v["solution"]).items()}
        v["solution"] = {n: [[round(x, 6), round(y, 6)] for x, y in pts]
                         for n, pts in v["solution"].items()}
        check(v["solution"])
    json.dump(figs, open(FIGS, "w"), ensure_ascii=False, indent=0, sort_keys=True)
    missing = [k for k in NAMES if k not in figs]
    print("фигур: %d, нет: %s" % (len(figs), " ".join(missing)))


def html(args):
    figs = json.load(open(FIGS))
    data = []
    for k in sorted(figs, key=lambda s: tuple(map(int, s.split(",")))):
        sol = {n: [tuple(p) for p in pts] for n, pts in figs[k]["solution"].items()}
        steps = instructions.plan(sol)
        r, c = k.split(",")
        data.append({
            "id": "f%s-%s" % (r, c),
            "name": NAMES[k],
            "level": instructions.difficulty(sol),
            "adapted": k in ADAPTED,
            "pieces": {n: [[round(x, 4), round(y, 4)] for x, y in pts] for n, pts in sol.items()},
            "steps": steps,
        })
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    out = tpl.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out = out.replace("Танграм: 48 фигур", "Танграм: %d фигур" % len(data))
    open(args[0], "w", encoding="utf-8").write(out)
    print("записано:", args[0], "фигур:", len(data))


if __name__ == "__main__":
    {"merge": merge, "html": html}[sys.argv[1]](sys.argv[2:])
