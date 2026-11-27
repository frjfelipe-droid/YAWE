"""Gera o ícone do YAWE: bichinho de pérola holográfica numa caixa roxa com holofote.

Uso:  python android/tools/gen_icon.py   (precisa de: pip install pillow)
Saída: ícones do Android (legado + adaptável) e da versão web (static/icon-*.png).
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "android/app/src/main/res"
N = 1024  # tela de trabalho


def radial_mask(size, power=2.0):
    m = Image.new("L", (256, 256))
    m.putdata([int(255 * max(0.0, 1 - math.hypot(x - 127.5, y - 127.5) / 128) ** power) for y in range(256) for x in range(256)])
    return m.resize(size, Image.BILINEAR)


def blob(img, cx, cy, w, h, color, alpha):
    layer = Image.new("RGBA", (w, h), color + (0,))
    layer.putalpha(radial_mask((w, h)).point(lambda v: int(v * alpha / 255)))
    img.alpha_composite(layer, (int(cx - w / 2), int(cy - h / 2)))


def room(size=N, rounded=True):
    """Caixa roxa com holofote de cima e luz no chão."""
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    top, bottom = (54, 22, 128), (16, 6, 44)
    for y in range(size):
        t = y / size
        d.line([(0, y), (size, y)], fill=tuple(int(top[k] * (1 - t) + bottom[k] * t) for k in range(3)) + (255,))
    s = size / N
    # cone do holofote
    cone = Image.new("L", (size, size), 0)
    ImageDraw.Draw(cone).polygon([(size * 0.34, 0), (size * 0.66, 0), (size * 0.84, size * 0.84), (size * 0.16, size * 0.84)], fill=95)
    cone = cone.filter(ImageFilter.GaussianBlur(60 * s))
    light = Image.new("RGBA", (size, size), (200, 170, 255, 0)); light.putalpha(cone)
    img.alpha_composite(light)
    # lâmpada no topo
    blob(img, size / 2, -size * 0.02, int(size * 0.75), int(size * 0.2), (205, 160, 255), 230)
    # luz no chão (um "palco" redondo)
    blob(img, size / 2, size * 0.81, int(size * 0.72), int(size * 0.16), (150, 110, 255), 150)
    floor = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(floor).ellipse([size * 0.25, size * 0.77, size * 0.75, size * 0.85], fill=(140, 100, 245, 120))
    img.alpha_composite(floor.filter(ImageFilter.GaussianBlur(22 * s)))
    # brilhinhos no ar
    for (px, py) in [(0.2, 0.3), (0.78, 0.22), (0.83, 0.55), (0.16, 0.66), (0.66, 0.12)]:
        blob(img, size * px, size * py, int(16 * s), int(16 * s), (230, 210, 255), 160)
    if rounded:
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.23), fill=255)
        edge = Image.new("L", (size, size), 0)
        ImageDraw.Draw(edge).rounded_rectangle([4 * s, 4 * s, size - 1 - 4 * s, size - 1 - 4 * s], radius=int(size * 0.225), outline=90, width=int(5 * s))
        rim = Image.new("RGBA", (size, size), (190, 150, 255, 0)); rim.putalpha(edge.filter(ImageFilter.GaussianBlur(2 * s)))
        img.alpha_composite(rim)
        img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return img


def creature(size=N, scale=1.0):
    """O YAWE: um bichinho arredondado de pérola holográfica, com olhos escuros brilhantes."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s = size / N * scale
    cx, cy = size / 2, size * 0.46
    rx, ry = 228 * s, 248 * s
    pts = []
    for i in range(240):
        t = i / 240 * math.tau
        x, y = math.cos(t), math.sin(t)
        if y > 0:            # parte de baixo um pouco mais larga e achatada (forma fofa)
            x *= 1 + 0.07 * y
            y *= 0.9
        else:
            x *= 1 - 0.04 * (-y)
        pts.append((cx + x * rx, cy + y * ry))
    shape = Image.new("L", (size, size), 0)
    ImageDraw.Draw(shape).polygon(pts, fill=255)
    shape = shape.filter(ImageFilter.GaussianBlur(1.2 * s))

    # sombra no chão
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - 150 * s, size * 0.81 - 18 * s, cx + 150 * s, size * 0.81 + 18 * s], fill=(20, 6, 60, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20 * s)))
    # brilho em volta
    glow = Image.new("RGBA", (size, size), (190, 160, 255, 0)); glow.putalpha(shape.filter(ImageFilter.GaussianBlur(34 * s)).point(lambda v: int(v * 0.35)))
    img.alpha_composite(glow)

    # corpo: base perolada + reflexos holográficos
    body = Image.new("RGBA", (size, size), (246, 244, 255, 255))
    for (bx, by, w, h, col, a) in [
        (-0.7, 0.3, 360, 340, (255, 90, 190), 255),       # rosa
        (0.62, 0.25, 330, 340, (40, 225, 235), 255),      # ciano
        (0.0, 0.85, 460, 260, (140, 90, 255), 255),       # lilás embaixo
        (0.3, 0.62, 260, 220, (70, 120, 255), 230),       # azul
        (-0.3, 0.7, 200, 160, (200, 90, 255), 200),       # roxo
    ]:
        blob(body, cx + bx * rx, cy + by * ry, int(w * s), int(h * s), col, a)
    body = body.filter(ImageFilter.GaussianBlur(34 * s))
    blob(body, cx - 0.2 * rx, cy - 0.5 * ry, int(360 * s), int(250 * s), (255, 255, 255), 255)   # luz de cima
    # borda levemente lilás (volume)
    edge = ImageChops.subtract(shape, shape.filter(ImageFilter.GaussianBlur(26 * s)))
    rim = Image.new("RGBA", (size, size), (190, 175, 255, 0)); rim.putalpha(edge.point(lambda v: min(255, v * 3)))
    body.alpha_composite(rim)
    body.putalpha(shape)
    img.alpha_composite(body)

    # olhos: ovais escuros, olhando de lado, com brilho
    d = ImageDraw.Draw(img)
    for ex in (-0.02, 0.42):
        exx, eyy = cx + ex * rx, cy - 0.2 * ry
        ew, eh = 82 * s, 104 * s
        d.ellipse([exx - ew / 2, eyy - eh / 2, exx + ew / 2, eyy + eh / 2], fill=(26, 16, 52, 255))
        d.ellipse([exx - ew * 0.05, eyy - eh * 0.36, exx + ew * 0.32, eyy - eh * 0.06], fill=(255, 255, 255, 255))
    return img


def save(img, path, px):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((px, px), Image.LANCZOS).save(path, optimize=True)


def main():
    full = room(); full.alpha_composite(creature())
    square = room(rounded=False); square.alpha_composite(creature())
    # Android legado (já com cantos arredondados)
    for name, px in {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}.items():
        save(full, RES / f"mipmap-{name}/ic_launcher.png", px)
    # Android adaptável (8+): fundo e bichinho separados; o celular recorta no formato dele
    save(room(rounded=False), RES / "drawable-nodpi/ic_launcher_bg.png", 432)
    fg = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    small = creature(scale=1.0).resize((int(N * 0.7), int(N * 0.7)), Image.LANCZOS)   # dentro da área segura
    fg.alpha_composite(small, (int(N * 0.15), int(N * 0.15)))
    save(fg, RES / "drawable-nodpi/ic_launcher_fg.png", 432)
    anydpi = RES / "mipmap-anydpi-v26"; anydpi.mkdir(parents=True, exist_ok=True)
    (anydpi / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@drawable/ic_launcher_bg" />\n'
        '    <foreground android:drawable="@drawable/ic_launcher_fg" />\n'
        '</adaptive-icon>\n', encoding="utf-8")
    # Web / PWA (quadrado inteiro: o sistema recorta)
    save(square, ROOT / "static/icon-512.png", 512)
    save(square, ROOT / "static/icon-192.png", 192)
    full.resize((512, 512), Image.LANCZOS).save(ROOT / "android/tools/icon_preview.png")
    print("ícones gerados")


if __name__ == "__main__":
    main()
