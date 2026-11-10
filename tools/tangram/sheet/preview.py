"""Сверка: ячейка с фото листка рядом с найденной раскладкой."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
from crop_cells import cells
import tg45

PHOTO = '/root/.claude/uploads/746e9745-5d65-5192-98ab-5449622e39de/eaddfa52-image.jpg'


def render(fig, W=300, sil=False):
    im = Image.new("RGB", (W, W), "white")
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = fig.bounds()
    s = W * 0.85 / max(x1 - x0, y1 - y0, 4)
    ox = (W - (x1 - x0) * s) / 2 - x0 * s
    oy = (W + (y1 - y0) * s) / 2 + y0 * s
    for n in fig.order:
        pts = [(ox + x * s, oy - y * s) for x, y in fig.pieces[n]]
        d.polygon(pts, fill="#222" if sil else tg45.PIECES[n][1], outline="white" if not sil else "#222")
    d.text((5, 5), fig.key, fill="black")
    return im


def sheet(figs, out):
    cs = cells(PHOTO)
    W = 300
    im = Image.new("RGB", (W * 3, W * len(figs)), "white")
    for i, f in enumerate(figs):
        r, c = map(int, f.key.split("_")[1:3])
        im.paste(cs[(r, c)].resize((W, W)).convert("RGB"), (0, i * W))
        im.paste(render(f, W, True), (W, i * W))
        im.paste(render(f, W), (2 * W, i * W))
    im.save(out)
