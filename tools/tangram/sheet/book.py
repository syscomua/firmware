"""
Книга «Танграм. 48 фігур» — один PDF A4 з розділами:

  Обкладинка, Зміст
  1. Як користуватися книгою
  2. Підготовка (деталі для вирізання, контрольний квадрат)
  3. Карта всіх фігур
  4. Завдання (48 силуетів у натуральну величину)
  5. Відповіді та покрокове складання
  Покажчик фігур

  python3 book.py OUT.pdf [--side-cm 12]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import instructions  # noqa
from build import ADAPTED  # noqa
from print import (BOX, COLORS, LEVEL, MAP_CSS, R, html, load_figs, map_pages,  # noqa
                   page_answer, page_pieces, page_task, svg, to_pdf)

BOOK_CSS = """
.page, .map { position: relative; }
.pn { position: absolute; bottom: 6mm; left: 0; right: 0; text-align: center;
      font-size: 9pt; color: #8a95a1; }
.chapter { justify-content: center; gap: 8mm; }
.chapter .k { font-size: 14pt; letter-spacing: .12em; text-transform: uppercase; color: #5b6774; }
.chapter h1 { font-size: 40pt; line-height: 1.1; }
.chapter p { font-size: 14pt; line-height: 1.5; max-width: 150mm; margin: 0; color: #333; }
.cover { justify-content: space-between; padding: 30mm 22mm; }
.cover h1 { font-size: 54pt; line-height: 1.05; }
.cover .sub { font-size: 17pt; color: #333; line-height: 1.4; }
.toc { font-size: 14pt; line-height: 1.5; width: 100%; border-collapse: collapse; }
.toc td { padding: 2.2mm 0; border-bottom: 0.3mm dotted #c3cad3; }
.toc td:last-child { text-align: right; font-variant-numeric: tabular-nums; width: 20mm; }
.text { font-size: 12.5pt; line-height: 1.55; display: flex; flex-direction: column; gap: 3.5mm; }
.text h2 { font-size: 16pt; margin: 3mm 0 0; }
.text p, .text ul { margin: 0; }
.text ul { padding-left: 6mm; display: flex; flex-direction: column; gap: 1.5mm; }
.idx { width: 100%; border-collapse: collapse; font-size: 10pt; }
.idx th { text-align: left; font-weight: 600; color: #5b6774; border-bottom: 0.4mm solid #1b232c;
          padding: 1.2mm 1mm; }
.idx td { padding: 1.6mm 1mm; border-bottom: 0.2mm solid #e1e5ea; font-variant-numeric: tabular-nums; }
.idx td.r, .idx th.r { text-align: right; }
.kit { display: grid; grid-template-columns: 1fr 1fr; gap: 2mm 8mm; font-size: 12pt; }
"""


def sections(page_html):
    """Розбити рядок з кількома <section> на окремі сторінки."""
    parts = re.findall(r"<section.*?</section>", page_html, flags=re.S)
    return parts or [page_html]


def cover(side_cm):
    pic, _ = svg(BOX, 30, 110, 110, "color")
    return """<section class="page cover">
<div style="display:flex;flex-direction:column;gap:8mm">
<div class="k" style="font-size:13pt;letter-spacing:.14em;color:#5b6774">РОЗВИВАЮЧА ГРА</div>
<h1>Танграм.<br>48 фігур</h1>
<div class="sub">Завдання-силуети, покрокове складання,<br>карта фігур і матеріали для друку</div>
</div>
<div class="stage" style="flex:0 0 auto">%s</div>
<div class="sub" style="font-size:11pt;color:#5b6774">Набір: квадрат зі стороною %g см, сім деталей</div>
</section>""" % (pic, side_cm)


def chapter(n, title, text):
    return """<section class="page chapter">
<div class="k">Розділ %d</div><h1>%s</h1><p>%s</p></section>""" % (n, title, text)


def toc(entries):
    rows = "".join("<tr><td>%s</td><td>%d</td></tr>" % (t, p) for t, p in entries)
    return """<section class="page"><h1>Зміст</h1>
<table class="toc">%s</table></section>""" % rows


def kit_list():
    return "".join('<div><span class="sw" style="background:%s"></span>%s</div>'
                   % (COLORS[n], instructions.NAMES[n][0])
                   for n in ["L1", "L2", "M", "Q", "P", "S1", "S2"])


def howto(side_cm):
    p1 = """<section class="page"><h1>Як користуватися книгою</h1><div class="text">
<p>Танграм — давня китайська головоломка. Квадрат розрізано на сім деталей, і з них
складають силуети тварин, людей, предметів і геометричних фігур.</p>
<h2>Правила</h2>
<ul>
<li>Кожну фігуру складають з <b>усіх семи</b> деталей.</li>
<li>Деталі не накладаються одна на одну.</li>
<li>Деталі можна повертати й перевертати.</li>
</ul>
<h2>Деталі набору</h2>
<div class="kit">%s</div>
<p>У книзі деталі завжди мають ці кольори: у схемах, підказках і текстах кроків.</p>
<h2>Три рівні підказки</h2>
<ul>
<li><b>Лише силует</b> — розділ 4. Найважчий рівень: пацієнт сам шукає, де яка деталь.</li>
<li><b>Кольорова схема</b> — розділ 3 (карта всіх фігур) або схема в розділі 5.
Пацієнт складає фігуру за зразком.</li>
<li><b>Покроково</b> — розділ 5. Одна деталь за крок: схема з номером кроку
і коротка фраза, куди покласти деталь.</li>
</ul>
</div></section>""" % kit_list()
    p2 = """<section class="page"><h1>Поради</h1><div class="text">
<h2>З чого почати</h2>
<p>Спершу складіть контрольний квадрат (розділ 2) — це найперше завдання.
Далі беріть фігури з позначкою «легка» в покажчику наприкінці книги, потім «середні»
й «складні».</p>
<h2>Силуети в натуральну величину</h2>
<p>Силуети в розділі 4 надруковано в масштабі 1:1 для набору з квадратом
<b>%g см</b>. Деталі можна викладати просто на аркуш. Якщо фігура не вмістилася
на сторінку, її зменшено — про це сказано внизу аркуша, і тоді фігуру складають поруч.</p>
<h2>Друк</h2>
<ul>
<li>Масштаб 100%% («Фактичний розмір»), без «Вмістити на сторінку».</li>
<li>Розділ 4 можна друкувати чорно-біло, розділи 3 і 5 — кольорові.</li>
<li>Аркуші із завданнями варто заламінувати або вкласти у файли.</li>
</ul>
<h2>Позначка «спрощена»</h2>
<p>Кілька фігур складено за мотивами малюнків з аркуша «Розвиваюча гра «Танграм»»:
загальний вигляд той самий, але деталі лежать трохи інакше. Давайте пацієнтові силует
із цієї книги.</p>
<h2>Зсув деталей</h2>
<p>У деяких фігурах деталь прикладено до сусідньої не кутик до кутика, а зі зсувом
уздовж спільної сторони. У тексті такого кроку сказано «зі зсувом» — звіряйтеся
з малюнком.</p>
</div></section>""" % side_cm
    return [p1, p2]


def index_pages(figs, task_page, ans_page):
    rows = []
    for num, key, name, sol in figs:
        lvl = LEVEL[instructions.difficulty(sol)]
        rows.append('<tr><td>%d</td><td>%s%s</td><td>%s</td><td class="r">%d</td><td class="r">%d</td></tr>'
                    % (num, name, " · спрощена" if key in ADAPTED else "", lvl,
                       task_page[num], ans_page[num]))
    head = ('<tr><th>№</th><th>Фігура</th><th>Складність</th>'
            '<th class="r">Завдання, с.</th><th class="r">Відповідь, с.</th></tr>')
    out = []
    per = 26
    for i in range(0, len(rows), per):
        out.append('<section class="page"><h1>Покажчик фігур</h1><table class="idx" style="font-size:11.5pt">%s%s</table>'
                   '</section>' % (head, "".join(rows[i:i + per])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--side-cm", type=float, default=12)
    a = ap.parse_args()
    unit = a.side_cm * 10 / (2 * R)
    figs = load_figs()

    # Порядок сторінок; номери рахуємо заздалегідь (кожна <section> — одна сторінка)
    chapters = [
        ("Як користуватися книгою", "Що таке танграм, правила, деталі набору, рівні підказки й поради.",
         howto(a.side_cm)),
        ("Підготовка", "Деталі для вирізання, якщо набору немає, і контрольний квадрат: "
         "перше завдання й перевірка, що друк у натуральну величину.",
         sections(page_pieces(unit, a.side_cm))),
        ("Карта всіх фігур", "Усі 48 фігур кольором на двох сторінках. Можна давати як зразок "
         "для складання або щоб пацієнт сам обрав фігуру.",
         map_pages(figs, 4, 6, "Карта всіх фігур")),
        ("Завдання", "48 силуетів, по одному на сторінку. Складіть фігуру з усіх семи деталей "
         "просто на силуеті.",
         [page_task(*f, unit, a.side_cm, False) for f in figs]),
        ("Відповіді та покрокове складання", "Для кожної фігури — кольорова схема з номерами "
         "кроків і покрокова інструкція.",
         [page_answer(*f, unit, a.side_cm) for f in figs]),
    ]
    # 1 обкладинка, 1 зміст, далі розділи (титул + сторінки), потім покажчик
    page = 3
    toc_entries = []
    task_page, ans_page = {}, {}
    for i, (title, _, pages) in enumerate(chapters):
        toc_entries.append(("%d. %s" % (i + 1, title), page))
        if title == "Завдання":
            for j, f in enumerate(figs):
                task_page[f[0]] = page + 1 + j
        if title.startswith("Відповіді"):
            for j, f in enumerate(figs):
                ans_page[f[0]] = page + 1 + j
        page += 1 + len(pages)
    toc_entries.append(("Покажчик фігур", page))

    body = [cover(a.side_cm), toc(toc_entries)]
    for i, (title, text, pages) in enumerate(chapters):
        body.append(chapter(i + 1, title, text))
        body.extend(pages)
    body.extend(index_pages(figs, task_page, ans_page))

    # номери сторінок (крім обкладинки)
    numbered = []
    for n, sec in enumerate(body, start=1):
        if n > 1:
            sec = sec[:sec.rindex("</section>")] + '<div class="pn">%d</div></section>' % n
        numbered.append(sec)

    css = MAP_CSS % dict(w=210, h=297, pad=8, gap=2, h1=18, fs=8, cols=4, rows=6, cp=0.8) + BOOK_CSS
    hp = os.path.splitext(a.out)[0] + ".html"
    open(hp, "w", encoding="utf-8").write(html(numbered, css))
    to_pdf(hp, a.out)
    if not os.environ.get("KEEP_HTML"):
        os.remove(hp)
    print("записано:", a.out, "сторінок:", len(numbered))


if __name__ == "__main__":
    main()
