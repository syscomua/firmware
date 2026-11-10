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


def html(pages, css_extra=""):
    return ('<!doctype html><html><head><meta charset="utf-8"><style>%s%s</style></head><body>%s'
            '</body></html>' % (CSS, css_extra, "\n".join(pages)))


MAP_CSS = """
@page { size: %(w)gmm %(h)gmm; margin: 0; }
.map { width: %(w)gmm; height: %(h)gmm; padding: %(pad)gmm; page-break-after: always;
       display: flex; flex-direction: column; gap: %(gap)gmm; overflow: hidden; }
.map h1 { font-size: %(h1)gpt; }
.legend { display: flex; flex-wrap: wrap; gap: 1.5mm %(gap)gmm; font-size: %(fs)gpt; color: #333; }
.grid { flex: 1; display: grid; grid-template-columns: repeat(%(cols)d, 1fr);
        grid-template-rows: repeat(%(rows)d, 1fr); gap: %(gap)gmm; min-height: 0; }
.cell { border: 0.3mm solid #d5dbe2; border-radius: 2mm; padding: %(cp)gmm; display: flex;
        flex-direction: column; min-height: 0; }
.cell .pic { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }
.cell .cap { font-size: %(fs)gpt; font-weight: 600; display: flex; justify-content: space-between; }
.cell .cap span { color: #5b6774; font-weight: 400; }
"""


def same_scale_svg(sol, labels, ext):
    """Кольорова схема фігури, вписана в клітинку; номери кроків однакового розміру."""
    x0, y0, x1, y1 = bounds(sol)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ext = max(x1 - x0, y1 - y0, 3.2) * 1.01  # фігура на всю клітинку, підписи однакові
    out = ['<svg xmlns="http://www.w3.org/2000/svg" style="width:100%%;height:100%%" '
           'viewBox="%.3f %.3f %.3f %.3f" preserveAspectRatio="xMidYMid meet">'
           % (cx - ext / 2, -cy - ext / 2, ext, ext)]
    for n, pts in sol.items():
        p = " ".join("%.4f,%.4f" % (x, -y) for x, y in pts)
        out.append('<polygon points="%s" fill="%s" stroke="#fff" stroke-width="%.3f" '
                   'stroke-linejoin="round"/>' % (p, COLORS[n], ext * 0.008))
    fs = ext * 0.062
    for n, t in labels.items():
        pts = sol[n]
        mx = sum(x for x, _ in pts) / len(pts)
        my = sum(y for _, y in pts) / len(pts)
        out.append('<circle cx="%.3f" cy="%.3f" r="%.3f" fill="#fff"/>' % (mx, -my, fs * 0.7))
        out.append('<text x="%.3f" y="%.3f" font-size="%.3f" font-weight="700" fill="#111" '
                   'text-anchor="middle" dominant-baseline="central" '
                   'font-family="Inter, sans-serif">%s</text>' % (mx, -my, fs, t))
    out.append("</svg>")
    return "".join(out)


def map_pages(figs, cols, rows, title):
    per = cols * rows
    legend = "".join('<span><span class="sw" style="background:%s"></span>%s</span>'
                     % (COLORS[n], instructions.NAMES[n][0]) for n in
                     ["L1", "L2", "M", "Q", "P", "S1", "S2"])
    ext = max(max(b[2] - b[0], b[3] - b[1]) for b in (bounds(f[3]) for f in figs)) * 1.04
    pages = []
    for start in range(0, len(figs), per):
        chunk = figs[start:start + per]
        cells = []
        for num, key, name, sol in chunk:
            sv = same_scale_svg(sol, {}, ext)
            cells.append('<div class="cell"><div class="pic">%s</div>'
                         '<div class="cap">%s<span>№ %d</span></div></div>' % (sv, name, num))
        part = ""
        if len(figs) > per:
            part = " (аркуш %d з %d)" % (start // per + 1, (len(figs) + per - 1) // per)
        pages.append('<section class="map"><div class="head"><h1>%s%s</h1>'
                     '</div>'
                     '<div class="legend">%s</div><div class="grid">%s</div></section>'
                     % (title, part, legend, "".join(cells)))
    return pages


def to_pdf(html_path, pdf_path):
    js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();"
          "const p=await b.newPage();await p.goto('file://'+process.argv[1]);"
          "await p.pdf({path:process.argv[2],printBackground:true,"
          "preferCSSPageSize:true});await b.close();})();")
    subprocess.run(["node", "-e", js, os.path.abspath(html_path), os.path.abspath(pdf_path)],
                   check=True)


CARD_CSS = """
@page { size: 148mm 210mm; margin: 0; }
.card { width: 148mm; height: 210mm; padding: 10mm; page-break-after: always;
        display: flex; flex-direction: column; gap: 4mm; overflow: hidden; }
.card h1 { font-size: 24pt; margin: 0; }
.card .pic { flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }
.card .foot { font-size: 9pt; }
"""


def card_pages(figs):
    pages = []
    for num, key, name, sol in figs:
        sv = same_scale_svg(sol, {}, None)
        pages.append('<section class="card"><div class="head"><h1>%s</h1>'
                     '<span class="num">№ %d</span></div><div class="pic">%s</div>'
                     '<div class="foot"><span>Складіть фігуру з усіх семи деталей</span>'
                     '<span>Танграм</span></div></section>' % (name, num, sv))
    return pages


def fname(num, name):
    return "%02d_%s" % (num, name.replace(" ", "_"))


README_TXT = """ТАНГРАМ — МАТЕРІАЛИ ДЛЯ ДРУКУ

1_Підготовка
  Деталі_та_контрольний_квадрат.pdf — деталі для вирізання (якщо немає набору)
  і контрольний квадрат. Спершу роздрукуйте його і прикладіть свій складений квадрат:
  контур має збігтися (розраховано на квадрат зі стороною %(side)g см).

2_Завдання
  Завдання_силуети_A4.pdf — 48 аркушів, чорний силует у натуральну величину.
  Друкувати чорно-біло. Пацієнт викладає деталі просто на аркуш.

3_Складання
  Відповіді_покроково_A4.pdf — 48 аркушів: кольорова схема з номерами кроків
  і покрокова інструкція. Для фахівця або як підказка.

4_Карта
  Карта_всіх_фігур_A2.pdf — плакат з усіма 48 фігурами кольором.
  Карта_всіх_фігур_2xA4.pdf — те саме на двох аркушах A4.

5_Картки
  Окрема картка A5 на кожну фігуру: назва та кольорова схема (PDF і PNG).

ДРУК: масштаб 100%% / «Фактичний розмір», без «Вмістити на сторінку».
"""


def pack(a, unit, figs, outdir):
    import shutil
    tmp = os.path.join(outdir, "_tmp")
    os.makedirs(tmp, exist_ok=True)
    root = os.path.join(outdir, "Танграм_матеріали")
    if os.path.exists(root):
        shutil.rmtree(root)
    layout = {
        "1_Підготовка/Деталі_та_контрольний_квадрат": ([page_pieces(unit, a.side_cm)], ""),
        "2_Завдання/Завдання_силуети_A4": ([page_task(*f, unit, a.side_cm, a.lines) for f in figs], ""),
        "3_Складання/Відповіді_покроково_A4": ([page_answer(*f, unit, a.side_cm) for f in figs], ""),
        "4_Карта/Карта_всіх_фігур_A2": (map_pages(figs, 6, 8, "Танграм: усі фігури"), MAP_CSS % dict(
            w=420, h=594, pad=12, gap=3, h1=34, fs=12, cols=6, rows=8, cp=1.5)),
        "4_Карта/Карта_всіх_фігур_2xA4": (map_pages(figs, 4, 6, "Танграм: усі фігури"), MAP_CSS % dict(
            w=210, h=297, pad=8, gap=2, h1=18, fs=8, cols=4, rows=6, cp=0.8)),
        "_tmp/cards": (card_pages(figs), CARD_CSS),
    }
    for rel, (pages, css) in layout.items():
        pdf = os.path.join(root if not rel.startswith("_tmp") else outdir, rel + ".pdf")
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        hp = os.path.join(tmp, "page.html")
        open(hp, "w", encoding="utf-8").write(html(pages, css))
        to_pdf(hp, pdf)
        print("записано:", pdf)
    cards = os.path.join(root, "5_Картки")
    os.makedirs(cards, exist_ok=True)
    subprocess.run(["pdfseparate", os.path.join(tmp, "cards.pdf"), os.path.join(tmp, "c-%d.pdf")],
                   check=True)
    for i, (num, key, name, sol) in enumerate(figs):
        base = os.path.join(cards, fname(num, name))
        shutil.move(os.path.join(tmp, "c-%d.pdf" % (i + 1)), base + ".pdf")
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-singlefile", base + ".pdf", base],
                       check=True, stderr=subprocess.DEVNULL)
    open(os.path.join(root, "Як_друкувати.txt"), "w", encoding="utf-8").write(
        README_TXT % dict(side=a.side_cm))
    shutil.rmtree(tmp)
    z = shutil.make_archive(root, "zip", outdir, "Танграм_матеріали")
    print("архів:", z)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--side-cm", type=float, default=12)
    ap.add_argument("--lines", action="store_true")
    ap.add_argument("--pack", action="store_true",
                    help="усе в одну папку Танграм_матеріали (+ zip), картки окремо")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    unit = a.side_cm * 10 / (2 * R)  # мм на единицу (катет маленького треугольника)
    figs = load_figs()
    if a.pack:
        pack(a, unit, figs, a.out)
        return
    jobs = {
        "zadaniya": [page_task(*f, unit, a.side_cm, a.lines) for f in figs],
        "otvety": [page_answer(*f, unit, a.side_cm) for f in figs],
        "detali": [page_pieces(unit, a.side_cm)],
        "karta_a2": map_pages(figs, 6, 8, "Танграм: усі фігури"),
        "karta_a4": map_pages(figs, 4, 6, "Танграм: усі фігури"),
    }
    extra = {
        "karta_a2": MAP_CSS % dict(w=420, h=594, pad=12, gap=3, h1=34, fs=12, cols=6, rows=8, cp=1.5),
        "karta_a4": MAP_CSS % dict(w=210, h=297, pad=8, gap=2, h1=18, fs=8, cols=4, rows=6, cp=0.8),
    }
    for name, pages in jobs.items():
        hp = os.path.join(a.out, name + ".html")
        open(hp, "w", encoding="utf-8").write(html(pages, extra.get(name, "")))
        to_pdf(hp, os.path.join(a.out, name + ".pdf"))
        if not os.environ.get("KEEP_HTML"):
            os.remove(hp)
        print("записано:", os.path.join(a.out, name + ".pdf"))


if __name__ == "__main__":
    main()
