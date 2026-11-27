"""Gera os quadros do widget "YAWE vivo" (o personagem em um quarto, fazendo atividades).

Uso:  python android/tools/gen_live_frames.py   (precisa de: pip install pillow)
Saída: android/app/src/main/res/drawable-nodpi/live_*.png
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "app/src/main/res/drawable-nodpi"
W, H = 840, 360          # tamanho final (proporção de um widget 4x2)
S = 2                    # desenho em 2x e reduz no fim (bordas suaves)
BG_TOP, BG_BOTTOM = (20, 19, 30), (9, 9, 13)
C1, C2, C3 = (122, 107, 255), (95, 139, 255), (255, 143, 209)   # cores do YAWE
CX, CY, R = 300, 208, 92


def sc(v):
    return int(round(v * S))


_RADIAL = None


def _radial_mask():
    """Máscara 256x256: 255 no centro, chega a 0 exatamente na borda do círculo (sem "caixa")."""
    global _RADIAL
    if _RADIAL is None:
        data = []
        for y in range(256):
            for x in range(256):
                r = math.hypot(x - 127.5, y - 127.5) / 128.0
                t = max(0.0, 1.0 - r)
                data.append(int(255 * t * t * (3 - 2 * t)))   # smoothstep
        _RADIAL = Image.new("L", (256, 256)); _RADIAL.putdata(data)
    return _RADIAL


def radial(size, color, alpha=255):
    """Mancha circular suave (centro forte, borda transparente)."""
    mask = _radial_mask().resize((size, size), Image.BILINEAR).point(lambda v: int(v * alpha / 255))
    layer = Image.new("RGBA", (size, size), color + (0,))
    layer.putalpha(mask)
    return layer


def paste_center(base, layer, x, y):
    base.alpha_composite(layer, (int(x - layer.width / 2), int(y - layer.height / 2)))


def room(light=None, light_pos=(0.5, 0.0), light_size=1.2):
    img = Image.new("RGBA", (sc(W), sc(H)))
    d = ImageDraw.Draw(img)
    for y in range(sc(H)):
        t = y / sc(H)
        d.line([(0, y), (sc(W), y)], fill=tuple(int(BG_TOP[k] * (1 - t) + BG_BOTTOM[k] * t) for k in range(3)) + (255,))
    if light:
        paste_center(img, radial(sc(W * light_size), light, 120), sc(W * light_pos[0]), sc(H * light_pos[1]))
    # chão
    floor = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(floor).rectangle([0, sc(300), sc(W), sc(H)], fill=(255, 255, 255, 6))
    img.alpha_composite(floor)
    return img


def orb_sprite(eyes="open", look=(0, 0), squash=(1.0, 1.0), tint=None, tint_from=(0.6, 0.0)):
    """O YAWE: esfera de luz com olhos. Retorna (imagem, raio_x, raio_y) em pixels 2x."""
    rx, ry = sc(R * squash[0]), sc(R * squash[1])
    size = (rx * 2, ry * 2)
    body = Image.new("RGBA", size, C2 + (255,))
    for (bx, by, col, bs) in [(-0.35, 0.3, C1, 1.5), (0.4, -0.2, C3, 1.3), (0.15, 0.5, C2, 1.6), (-0.3, -0.45, C3, 1.1)]:
        paste_center(body, radial(int(rx * bs), col, 235), rx + bx * rx, ry + by * ry)
    body = body.filter(ImageFilter.GaussianBlur(sc(9)))
    paste_center(body, radial(int(rx * 1.3), (255, 255, 255), 130), rx * 0.62, ry * 0.5)
    if tint:
        paste_center(body, radial(int(rx * 2.4), tint, 170), rx + tint_from[0] * rx, ry + tint_from[1] * ry)
    # borda iluminada
    rim = Image.new("L", size, 0)
    ImageDraw.Draw(rim).ellipse([0, 0, size[0] - 1, size[1] - 1], outline=110, width=sc(5))
    rim = rim.filter(ImageFilter.GaussianBlur(sc(4)))
    white = Image.new("RGBA", size, (255, 255, 255, 0)); white.putalpha(rim)
    body.alpha_composite(white)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size[0] - 1, size[1] - 1], fill=255)
    body.putalpha(ImageChops.multiply(body.getchannel("A"), mask))
    # olhos
    d = ImageDraw.Draw(body)
    ew, eh = sc(R * 0.1), sc(R * 0.27)
    for side in (-1, 1):
        ex = rx + side * sc(R * 0.24) + sc(R * 0.16 * look[0])
        ey = ry - sc(R * 0.03) + sc(R * 0.12 * look[1])
        if eyes == "open":
            d.rounded_rectangle([ex - ew / 2, ey - eh / 2, ex + ew / 2, ey + eh / 2], radius=ew / 2, fill=(255, 255, 255, 255))
        elif eyes == "big":
            eh2 = eh * 1.2
            d.rounded_rectangle([ex - ew / 2, ey - eh2 / 2, ex + ew / 2, ey + eh2 / 2], radius=ew / 2, fill=(255, 255, 255, 255))
        elif eyes == "closed":   # dormindo: tracinhos para baixo
            d.arc([ex - sc(R * 0.09), ey - sc(R * 0.08), ex + sc(R * 0.09), ey + sc(R * 0.06)], 20, 160, fill=(255, 255, 255, 255), width=sc(5))
        elif eyes == "happy":    # ^ ^
            d.arc([ex - sc(R * 0.09), ey - sc(R * 0.02), ex + sc(R * 0.09), ey + sc(R * 0.16)], 200, 340, fill=(255, 255, 255, 255), width=sc(6))
        elif eyes == "blink":
            d.rounded_rectangle([ex - ew / 2, ey - sc(3), ex + ew / 2, ey + sc(3)], radius=sc(3), fill=(255, 255, 255, 255))
    return body, rx, ry


def place_orb(img, sprite, cx, cy, glow=C1, glow_alpha=110):
    body, rx, ry = sprite
    paste_center(img, radial(int(max(rx, ry) * 3.2), glow, glow_alpha), sc(cx), sc(cy))
    # sombra no chão
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([sc(cx) - rx * 0.8, sc(300) - sc(7), sc(cx) + rx * 0.8, sc(300) + sc(9)], fill=(0, 0, 0, 120))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(sc(6))))
    img.alpha_composite(body, (int(sc(cx) - rx), int(sc(cy) - ry)))


def draw_z(img, x, y, size, alpha):
    d = ImageDraw.Draw(img)
    s = sc(size)
    pts = [(sc(x), sc(y)), (sc(x) + s, sc(y)), (sc(x), sc(y) + s), (sc(x) + s, sc(y) + s)]
    d.line(pts, fill=(225, 225, 255, alpha), width=max(2, sc(size / 6)), joint="curve")


def steam(img, x, y, phase, alpha=150):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k, dx in enumerate((-9, 0, 9)):
        pts = [(sc(x + dx + 5 * math.sin((t / 8.0) + phase + k)), sc(y - t)) for t in range(0, 46, 2)]
        d.line(pts, fill=(255, 255, 255, alpha), width=sc(3), joint="curve")
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(sc(1.5))))


def mug(img, x, y, angle=0):
    w, h = 46, 50
    layer = Image.new("RGBA", (sc(w + 40), sc(h + 30)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    ox, oy = sc(8), sc(12)
    d.ellipse([ox + sc(w - 8), oy + sc(10), ox + sc(w + 16), oy + sc(36)], outline=(238, 228, 214, 255), width=sc(6))
    d.rounded_rectangle([ox, oy, ox + sc(w), oy + sc(h)], radius=sc(10), fill=(242, 232, 218, 255))
    d.ellipse([ox + sc(3), oy - sc(4), ox + sc(w - 3), oy + sc(8)], fill=(92, 58, 36, 255))
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(layer, (int(sc(x) - layer.width / 2), int(sc(y) - layer.height / 2)))


def tv(img, color):
    x0, y0, x1, y1 = 600, 120, 790, 245
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle([sc(x0 - 10), sc(y0 - 10), sc(x1 + 10), sc(y1 + 10)], radius=sc(18), fill=color + (120,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(sc(26))))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([sc(x0 - 6), sc(y0 - 6), sc(x1 + 6), sc(y1 + 6)], radius=sc(14), fill=(24, 24, 30, 255))
    screen = Image.new("RGBA", (sc(x1 - x0), sc(y1 - y0)), color + (255,))
    paste_center(screen, radial(sc(260), (255, 255, 255), 90), sc(60), sc(40))
    m = Image.new("L", screen.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, screen.width - 1, screen.height - 1], radius=sc(9), fill=255)
    screen.putalpha(m)
    img.alpha_composite(screen, (sc(x0), sc(y0)))
    d.line([(sc(695), sc(y1 + 6)), (sc(695), sc(292))], fill=(40, 40, 48, 255), width=sc(6))
    d.rounded_rectangle([sc(655), sc(288), sc(735), sc(298)], radius=sc(5), fill=(40, 40, 48, 255))


def phone(img, x, y, scroll, angle=-12):
    w, h = 64, 112
    layer = Image.new("RGBA", (sc(w + 20), sc(h + 20)), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    o = sc(10)
    d.rounded_rectangle([o, o, o + sc(w), o + sc(h)], radius=sc(12), fill=(28, 28, 34, 255))
    scr = [o + sc(4), o + sc(6), o + sc(w - 4), o + sc(h - 6)]
    d.rounded_rectangle(scr, radius=sc(9), fill=(150, 205, 255, 255))
    for i in range(6):   # conteúdo rolando
        yy = scr[1] + sc(10) + ((i * 22 + scroll * 11) % 100) * S
        if yy < scr[3] - sc(10):
            d.rounded_rectangle([scr[0] + sc(6), yy, scr[2] - sc(14 if i % 2 else 6), yy + sc(8)], radius=sc(4), fill=(255, 255, 255, 200))
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(layer, (int(sc(x) - layer.width / 2), int(sc(y) - layer.height / 2)))


def lamp_moon(img):
    d = ImageDraw.Draw(img)
    paste_center(img, radial(sc(160), (255, 236, 190), 110), sc(720), sc(70))
    d.ellipse([sc(700), sc(50), sc(740), sc(90)], fill=(255, 240, 205, 255))
    d.ellipse([sc(714), sc(44), sc(754), sc(84)], fill=BG_TOP + (255,))   # lua crescente


def finish(img, name):
    img = img.resize((W, H), Image.LANCZOS)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=40, fill=255)
    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    img.save(OUT / f"live_{name}.png", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Dormindo: respira (esfera achatada sobe/desce) e os "z" sobem
    for i, (sq, zs) in enumerate([((1.14, 0.84), [(0, 40)]), ((1.11, 0.88), [(1, 70), (0, 120)]), ((1.14, 0.84), [(2, 110), (1, 150)])]):
        img = room((80, 70, 160), (0.85, 0.1), 0.9)
        lamp_moon(img)
        place_orb(img, orb_sprite("closed", squash=sq), CX, 300 - R * sq[1], glow=(110, 90, 220), glow_alpha=70)
        for step, a in zs:
            draw_z(img, CX + 70 + step * 26, 150 - step * 34, 16 + step * 7, a)
        finish(img, f"sleep{i}")
    # Assistindo TV: luz da tela muda de cor no rosto
    for i, col in enumerate([(70, 120, 255), (160, 80, 255), (40, 200, 190), (255, 90, 150)]):
        img = room()
        tv(img, col)
        place_orb(img, orb_sprite("blink" if i == 2 else "open", look=(0.9, -0.1), tint=col, tint_from=(0.9, -0.1)), CX, CY, glow=col, glow_alpha=70)
        finish(img, f"tv{i}")
    # Tomando café: vapor sobe; depois um gole
    for i in range(3):
        img = room((255, 170, 90), (0.1, 0.05), 0.9)
        if i < 2:
            place_orb(img, orb_sprite("open", look=(0.5, 0.2)), CX, CY, glow=(255, 150, 110), glow_alpha=80)
            mug(img, CX + R * 1.05, CY + R * 0.55)
            steam(img, CX + R * 1.02, CY + R * 0.2, phase=i * 2.2)
        else:
            place_orb(img, orb_sprite("happy"), CX, CY - 4, glow=(255, 150, 110), glow_alpha=90)
            mug(img, CX + R * 0.78, CY + R * 0.18, angle=28)
            steam(img, CX + R * 0.95, CY - R * 0.2, phase=4.0, alpha=90)
        finish(img, f"coffee{i}")
    # No celular: tela ilumina por baixo, conteúdo rola
    for i in range(3):
        img = room()
        place_orb(img, orb_sprite("blink" if i == 2 else "open", look=(0.15, 0.95), tint=(170, 215, 255), tint_from=(0.1, 0.9)), CX, CY, glow=(120, 170, 255), glow_alpha=70)
        phone(img, CX + R * 0.62, CY + R * 0.78, scroll=i, angle=-18)
        finish(img, f"phone{i}")
    # Acordado: de pé, olhos grandes, pulando de leve
    for i, (dy, eyes) in enumerate([(-18, "big"), (-6, "big"), (-14, "happy")]):
        img = room((140, 110, 255), (0.4, 0.05), 1.1)
        place_orb(img, orb_sprite(eyes, look=(0.2, -0.1)), CX, CY + dy, glow=(150, 120, 255), glow_alpha=140)
        finish(img, f"awake{i}")
    print("quadros gerados em", OUT)


if __name__ == "__main__":
    main()
