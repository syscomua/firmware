"""Нарезка фото листка на 48 ячеек (для сверки фигур)."""
import sys
from PIL import Image, ImageOps

LX = [[100, 220, 345]] * 5 + [[118, 238, 360]] * 3
RX = [505, 632, 762]
LY = [115, 235, 378, 503, 621, 740, 859, 966]
RY = [100, 228, 372, 492, 621, 740, 866, 976]


def cells(path):
    im = ImageOps.exif_transpose(Image.open(path))
    k = im.size[0] / 1500
    out = {}
    for r in range(8):
        for c in range(6):
            vx = LX[r][c] if c < 3 else RX[c - 3]
            vy = LY[r] if c < 3 else RY[r]
            X, Y = 100 + vx * 1.278, 380 + vy * 1.277
            h = 58 * 1.278
            box = tuple(int(v * k) for v in (X - h, Y - h, X + h, Y + h))
            g = ImageOps.autocontrast(im.crop(box).convert("L"), cutoff=2)
            out[(r, c)] = g.resize((240, 240))
    return out


if __name__ == "__main__":
    cs = cells(sys.argv[1])
    sheet = Image.new("L", (6 * 250, 8 * 250), 255)
    for (r, c), g in cs.items():
        sheet.paste(g, (c * 250, r * 250))
    sheet.save(sys.argv[2])
