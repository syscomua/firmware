"""
Печатные материалы (A4, PDF):

  zadaniya.pdf  — по фигуре на лист: чёрный силуэт в натуральную величину набора
  otvety.pdf    — по фигуре на лист: цветная схема с номерами шагов + текст шагов
  detali.pdf    — детали для вырезания и контрольный квадрат (проверка масштаба)

  python3 print.py OUT_DIR [--side-cm 12] [--lines]

--side-cm  — сторона собранного квадрата вашего набора, см. Тогда силуэт на листе
             совпадает с деталями 1:1 и их можно выкладывать прямо на распечатку.
--lines    — в заданиях показать границы деталей (облегчённый вариант).
"""
import argparse
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import instructions  # noqa
from build import NAMES, ADAPTED  # noqa

COLORS = {"L1": "#1f5a2c", "L2": "#e8a530", "M": "#e0457b", "Q": "#2f62d9",
          "P": "#d93a3a", "S1": "#6cc08b", "S2": "#b8222b"}
LEVEL = {1: "легка", 2: "середня", 3: "складна"}
R = math.sqrt(2)
H = R / 2
BOX = {  # исходный квадрат (как на фото набора), сторона 2√2
    "L1": [(0, 0), (2 * R, 0), (R, R)],
    "L2": [(2 * R, 0), (2 * R, 2 * R), (R, R)],
    "M": [(0, 2 * R), (0, R), (R, 2 * R)],
    "Q": [(R, R), (3 * H, 3 * H), (R, 2 * R), (H, 3 * H)],
    "S1": [(R, 2 * R), (2 * R, 2 * R), (3 * H, 3 * H)],
    "S2": [(H, H), (R, R), (H, 3 * H)],
    "P": [(0, 0), (H, H), (H, 3 * H), (0, R)],
}

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Inter, "DejaVu Sans", sans-serif; color: #1b232c; }
.page { width: 210mm; height: 297mm; padding: 14mm 15mm; page-break-after: always;
        display: flex; flex-direction: column; gap: 6mm; overflow: hidden; }
.head { display: flex; justify-content: space-between; align-items: baseline; }
.num { font-size: 11pt; color: #5b6774; }
h1 { font-size: 26pt; margin: 0; font-weight: 700; }
.task { font-size: 14pt; line-height: 1.4; }
.stage { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }
.foot { font-size: 9.5pt; color: #5b6774; display: flex; justify-content: space-between; }
ol { margin: 0; padding-left: 7mm; font-size: 12pt; line-height: 1.4; display: flex;
     flex-direction: column; gap: 1.8mm; flex: 0 0 auto; }
.sw { display: inline-block; width: 4mm; height: 4mm; border-radius: 1mm; margin-right: 1.5mm;
      vertical-align: -0.5mm; }
.row { display: flex; gap: 8mm; align-items: flex-start; }
.note { font-size: 10.5pt; color: #5b6774; }
"""


def bounds(pieces):
    xs = [x for p in pieces.values() for x, _ in p]
    ys = [y for p in pieces.values() for _, y in p]
    return min(xs), min(ys), max(xs), max(ys)


def svg(pieces, unit_mm, max_w, max_h, mode, labels=None):
    """mode: sil | lines | color. Возвращает (svg, масштаб относительно 1:1)."""
    x0, y0, x1, y1 = bounds(pieces)
    w, h = (x1 - x0) * unit_mm, (y1 - y0) * unit_mm
    k = min(1.0, max_w / w, max_h / h)
    u = unit_mm * k
    W, Hh = (x1 - x0) * u, (y1 - y0) * u
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%.2fmm" height="%.2fmm" '
           'viewBox="0 0 %.3f %.3f">' % (W + 2, Hh + 2, W + 2, Hh + 2)]
    for n, pts in pieces.items():
        p = " ".join("%.3f,%.3f" % (1 + (x - x0) * u, 1 + (y1 - y) * u) for x, y in pts)
        if mode == "sil":
            out.append('<polygon points="%s" fill="#111" stroke="#111" stroke-width="0.25" '
                       'stroke-linejoin="round"/>' % p)
        elif mode == "lines":
            out.append('<polygon points="%s" fill="#222" stroke="#fff" stroke-width="0.6" '
                       'stroke-linejoin="round"/>' % p)
        elif mode == "cut":
            out.append('<polygon points="%s" fill="%s" stroke="#111" stroke-width="0.35" '
                       'stroke-dasharray="1.5 1" stroke-linejoin="round"/>' % (p, COLORS[n]))
        else:
            out.append('<polygon points="%s" fill="%s" stroke="#fff" stroke-width="0.7" '
                       'stroke-linejoin="round"/>' % (p, COLORS[n]))
    if labels:
        fs = max(3.2, min(7, u * 0.45))
        for n, t in labels.items():
            pts = pieces[n]
            cx = sum(x for x, _ in pts) / len(pts)
            cy = sum(y for _, y in pts) / len(pts)
            X, Y = 1 + (cx - x0) * u, 1 + (y1 - cy) * u
            out.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#fff"/>' % (X, Y, fs * 0.72))
            out.append('<text x="%.2f" y="%.2f" font-size="%.2f" font-weight="700" fill="#111" '
                       'text-anchor="middle" dominant-baseline="central" '
                       'font-family="Inter, sans-serif">%s</text>' % (X, Y, fs, t))
    out.append("</svg>")
    return "\n".join(out), k


def load_figs():
    figs = json.load(open(os.path.join(HERE, "figures.json")))
    keys = sorted(figs, key=lambda s: tuple(map(int, s.split(","))))
    out = []
    for i, k in enumerate(keys):
        sol = {n: [tuple(p) for p in pts] for n, pts in figs[k]["solution"].items()}
        out.append((i + 1, k, NAMES[k], sol))
    return out


def scale_note(k, side_cm):
    if k >= 0.999:
        return "Масштаб 1:1 для набору зі стороною квадрата %g см" % side_cm
    return "Зменшено до %d%% — викладайте фігуру поруч із малюнком" % round(k * 100)


def page_task(num, key, name, sol, unit, side_cm, lines):
    steps = instructions.plan(sol)
    level = LEVEL[instructions.difficulty(sol)]
    s, k = svg(sol, unit, 180, 215, "lines" if lines else "sil")
    return """<section class="page">
<div class="head"><h1>%s</h1><span class="num">№ %d · %s</span></div>
<div class="task">Складіть таку фігуру з усіх семи деталей. Деталі не повинні налазити одна на одну.</div>
<div class="stage">%s</div>
<div class="foot"><span>%s</span><span>Танграм</span></div>
</section>""" % (name, num, level, s, scale_note(k, side_cm))


def page_answer(num, key, name, sol, unit, side_cm):
    steps = instructions.plan(sol)
    labels = {st["piece"]: str(i + 1) for i, st in enumerate(steps)}
    s, k = svg(sol, unit, 180, 150, "color", labels)
    s = s.replace('<svg ', '<svg style="width:100%;height:100%" preserveAspectRatio="xMidYMid meet" ', 1)
    items = "".join('<li><span class="sw" style="background:%s"></span>%s</li>'
                    % (COLORS[st["piece"]], st["text"]) for st in steps)
    note = ""
    if key in ADAPTED:
        note = ('<div class="note">Фігуру складено за мотивами малюнка з аркуша, вона відрізняється '
                'від нього в деталях. Давайте пацієнтові силует із цього комплекту.</div>')
    return """<section class="page">
<div class="head"><h1>%s — відповідь</h1><span class="num">№ %d</span></div>
<div class="stage" style="flex:1 1 0;min-height:45mm">%s</div>
<ol>%s</ol>%s
<div class="foot"><span>Цифри на схемі — номер кроку</span><span>Танграм</span></div>
</section>""" % (name, num, s, items, note)


def page_pieces(unit, side_cm):
    s, _ = svg(BOX, unit, 180, 180, "cut")
    s2, _ = svg(BOX, unit, 180, 180, "sil")
    names = "".join('<li><span class="sw" style="background:%s"></span>%s</li>'
                    % (COLORS[n], instructions.NAMES[n][0]) for n in
                    ["L1", "L2", "M", "Q", "P", "S1", "S2"])
    return """<section class="page">
<div class="head"><h1>Деталі набору</h1><span class="num">сторона квадрата %g см</span></div>
<div class="task">Якщо свого набору немає — роздрукуйте цей аркуш на щільному папері та виріжте деталі по пунктиру.
Якщо набір є — прикладіть складений квадрат до контуру нижче: він має збігтися. Якщо не збігається,
роздрукуйте матеріали заново з вашим розміром (параметр --side-cm).</div>
<div class="stage">%s</div>
<ol style="list-style:none;padding:0">%s</ol>
</section>
<section class="page">
<div class="head"><h1>Контрольний квадрат</h1><span class="num">%g × %g см</span></div>
<div class="task">Складіть квадрат з усіх семи деталей просто на цьому контурі.
Це гарне перше завдання й перевірка, що друк у натуральну величину.</div>
<div class="stage">%s</div>
<div class="foot"><span>Під час друку оберіть «Фактичний розмір» / 100%%, без «Вмістити на сторінку».</span><span>Танграм</span></div>
</section>""" % (side_cm, s, names, side_cm, side_cm, s2)


def html(pages):
    return ('<!doctype html><html><head><meta charset="utf-8"><style>%s</style></head><body>%s'
            '</body></html>' % (CSS, "\n".join(pages)))


def to_pdf(html_path, pdf_path):
    js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
          "const p=await b.newPage();await p.goto('file://'+process.argv[1]);"
          "await p.pdf({path:process.argv[2],format:'A4',printBackground:true,"
          "preferCSSPageSize:true});await b.close();})();")
    subprocess.run(["node", "-e", js, os.path.abspath(html_path), os.path.abspath(pdf_path)],
                   check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--side-cm", type=float, default=12)
    ap.add_argument("--lines", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    unit = a.side_cm * 10 / (2 * R)  # мм на единицу (катет маленького треугольника)
    figs = load_figs()
    jobs = {
        "zadaniya": [page_task(*f, unit, a.side_cm, a.lines) for f in figs],
        "otvety": [page_answer(*f, unit, a.side_cm) for f in figs],
        "detali": [page_pieces(unit, a.side_cm)],
    }
    for name, pages in jobs.items():
        hp = os.path.join(a.out, name + ".html")
        open(hp, "w", encoding="utf-8").write(html(pages))
        to_pdf(hp, os.path.join(a.out, name + ".pdf"))
        if not os.environ.get("KEEP_HTML"):
            os.remove(hp)
        print("записано:", os.path.join(a.out, name + ".pdf"))


if __name__ == "__main__":
    main()
