"""Flat reference illustrations for the Kushalaya catalog (640x640 WebP, no text, no logos).

Regenerate: python backend/scripts/draw_catalog_images.py frontend/public/marketing/products/catalog [names...]
File names are what app/livewell/commerce.py catalog_image_url() expects."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
S = 2
N = 640

BG = (238, 242, 246)
STD, ST, STH = (118, 131, 144), (178, 190, 201), (236, 240, 244)
WH, OL = (250, 251, 252), (96, 110, 124)
TEAL, TEALL = (31, 128, 120), (128, 200, 190)
ORG, RED, REDD = (232, 131, 58), (214, 69, 65), (170, 48, 46)
WOOD, WOODD = (200, 154, 108), (160, 116, 76)
BLUE, BLUED = (74, 124, 192), (46, 84, 140)
YEL, GLOW = (248, 206, 96), (255, 238, 176)
DK, GR, RUB = (58, 66, 76), (204, 210, 216), (84, 92, 102)
GREEN = (76, 170, 110)


class D:
    def __init__(self):
        self.img = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
        self.sh = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.ds = ImageDraw.Draw(self.sh)

    @staticmethod
    def s(v):
        return [c * S for c in v]

    def shadow(self, cx, cy, w, h, a=60):
        self.ds.ellipse(self.s((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)), fill=(60, 80, 100, a))

    def rect(self, x0, y0, x1, y1, fill, r=0, ol=OL, w=3):
        self.d.rounded_rectangle(self.s((x0, y0, x1, y1)), radius=r * S, fill=fill, outline=ol, width=int(w * S) if ol else 0)

    def circ(self, cx, cy, r, fill, ol=OL, w=3):
        self.d.ellipse(self.s((cx - r, cy - r, cx + r, cy + r)), fill=fill, outline=ol, width=int(w * S) if ol else 0)

    def ell(self, x0, y0, x1, y1, fill, ol=OL, w=3):
        self.d.ellipse(self.s((x0, y0, x1, y1)), fill=fill, outline=ol, width=int(w * S) if ol else 0)

    def poly(self, pts, fill, ol=OL, w=3):
        p = [(x * S, y * S) for x, y in pts]
        self.d.polygon(p, fill=fill)
        if ol:
            self.line(pts + [pts[0]], w, ol)

    def line(self, pts, w, fill):
        p = [(x * S, y * S) for x, y in pts]
        self.d.line(p, fill=fill, width=int(w * S))
        r = w * S / 2
        for x, y in p:
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def arc(self, x0, y0, x1, y1, a0, a1, w, fill):
        self.d.arc(self.s((x0, y0, x1, y1)), a0, a1, fill=fill, width=int(w * S))

    def tube(self, pts, w=22, c=(STD, ST, STH)):
        self.line(pts, w, c[0])
        self.line(pts, w * 0.66, c[1])
        self.line([(x - w * 0.12, y - w * 0.14) for x, y in pts], w * 0.2, c[2])

    def flange(self, cx, cy, r=30):
        self.circ(cx, cy, r, ST, STD, 3)
        self.circ(cx, cy, r * 0.55, STH, None)

    def glow(self, cx, cy, r, col=GLOW, a=150):
        g = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse(self.s((cx - r, cy - r, cx + r, cy + r)), fill=col + (a,))
        g = g.filter(ImageFilter.GaussianBlur(r * S * 0.35))
        self.img = Image.alpha_composite(g, self.img)
        self.d = ImageDraw.Draw(self.img)

    def beam(self, pts, a=110):
        g = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(g).polygon([(x * S, y * S) for x, y in pts], fill=GLOW + (a,))
        g = g.filter(ImageFilter.GaussianBlur(14 * S))
        self.img = Image.alpha_composite(g, self.img)
        self.d = ImageDraw.Draw(self.img)

    def wall(self, y=520):
        """Faint wall/floor split for installed items."""
        self.ds.rectangle(self.s((0, y, N, y + 2)), fill=(120, 140, 160, 40))

    def save(self, name):
        base = Image.new("RGBA", self.img.size, BG + (255,))
        sh = self.sh.filter(ImageFilter.GaussianBlur(10 * S))
        out = Image.alpha_composite(Image.alpha_composite(base, sh), self.img)
        out = out.convert("RGB").resize((N, N), Image.LANCZOS)
        out.save(OUT / f"{name}.webp", "WEBP", quality=80, method=6)


def bez(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def rot(cx, cy, w, h, ang):
    a = math.radians(ang)
    out = []
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        out.append((cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)))
    return out


def wheel(d, cx, cy, r, spokes=True):
    d.circ(cx, cy, r, DK, None)
    d.circ(cx, cy, r * 0.78, GR if spokes else RUB, None)
    if spokes:
        for k in range(8):
            a = math.radians(k * 22.5)
            d.line([(cx - r * 0.75 * math.cos(a), cy - r * 0.75 * math.sin(a)), (cx + r * 0.75 * math.cos(a), cy + r * 0.75 * math.sin(a))], 2, STD)
    d.circ(cx, cy, r * 0.16, ST, STD, 2)


def screen(d, x0, y0, x1, y1):
    d.rect(x0, y0, x1, y1, (196, 226, 214), 8, DK, 3)
    for i, yy in enumerate((y0 + (y1 - y0) * 0.3, y0 + (y1 - y0) * 0.62)):
        d.rect(x0 + 14, yy - 7, x1 - 14 - i * 30, yy + 7, (60, 100, 90), 3, None)


# ---------------------------------------------------------------- bathroom
def bth_002(d):
    d.tube([(220, 150), (220, 440), (470, 440)], 26)
    d.flange(220, 150); d.flange(220, 440); d.flange(470, 440)
    d.shadow(345, 470, 300, 40, 40)


def bth_004(d):
    d.wall(540)
    d.shadow(240, 560, 150, 34)
    d.ell(185, 540, 295, 575, ST, STD)
    d.tube([(240, 555), (240, 250), (470, 250)], 26)
    d.flange(470, 250)


def bth_006(d):
    d.shadow(320, 520, 380, 60)
    d.rect(150, 330, 490, 470, WH, 30)
    d.ell(150, 250, 490, 400, WH)
    d.ell(230, 285, 410, 365, (214, 222, 230))
    d.rect(120, 300, 170, 330, ST, 10, STD); d.rect(470, 300, 520, 330, ST, 10, STD)
    d.tube([(140, 315), (140, 480)], 18); d.tube([(500, 315), (500, 480)], 18)


def bth_007(d):
    d.shadow(320, 560, 420, 50)
    for x in (170, 470):
        d.tube([(x - 30, 555), (x - 30, 320)], 20)
        d.tube([(x + 30, 555), (x + 30, 320)], 20)
        d.rect(x - 60, 300, x + 60, 335, DK, 14, None)
        d.ell(x - 48, 545, x - 12, 565, RUB, None); d.ell(x + 12, 545, x + 48, 565, RUB, None)
    d.tube([(230, 420), (410, 420)], 18)


def bth_009(d):
    d.poly([(80, 470), (560, 470), (480, 230), (160, 230)], (226, 233, 238), OL)
    for k in range(1, 6):
        t = k / 6
        d.line([(80 + 480 * t, 470), (160 + 320 * t, 230)], 2, (190, 200, 208))
    for k in range(1, 4):
        y = 230 + 240 * k / 4
        x0 = 160 - 80 * k / 4
        d.line([(x0, y), (N - x0, y)], 2, (190, 200, 208))
    for i, (cx, cy) in enumerate(((220, 300), (320, 300), (420, 300), (200, 400), (320, 400), (440, 400))):
        d.poly(rot(cx, cy, 120, 22, -20), RUB, DK, 2)


def bth_010(d):
    d.tube([(430, 120), (430, 500)], 18)
    d.flange(430, 120, 22); d.flange(430, 500, 22)
    hose = bez((300, 380), (240, 560), (500, 600), (430, 500))
    d.line(hose, 10, STD); d.line(hose, 5, ST)
    d.line([(300, 380), (360, 230)], 26, ST); d.line([(300, 380), (360, 230)], 12, STH)
    d.circ(370, 205, 48, ST, STD, 4)
    d.circ(370, 205, 34, STH, None)
    for k in range(7):
        a = k * math.pi * 2 / 7
        d.circ(370 + 20 * math.cos(a), 205 + 20 * math.sin(a), 4, STD, None)


def bth_011(d):
    d.rect(170, 160, 470, 360, WH, 26)
    for cx, col in ((250, BLUE), (390, RED)):
        d.circ(cx, 260, 60, ST, STD, 4)
        d.circ(cx, 260, 40, STH, None)
        d.rect(cx - 8, 210, cx + 8, 255, col, 4, None)
    d.tube([(320, 360), (320, 440), (360, 470)], 34)
    d.shadow(320, 380, 300, 30, 40)


def bth_012(d):
    d.shadow(320, 540, 480, 50)
    d.rect(330, 300, 600, 520, (232, 238, 243), 40)
    d.rect(80, 300, 560, 345, WH, 14)
    d.rect(80, 200, 120, 300, WH, 10)
    for x in (110, 250, 400, 540):
        d.tube([(x, 345), (x, 535)], 16)
        d.ell(x - 14, 528, x + 14, 545, RUB, None)
    for x in range(140, 540, 40):
        d.circ(x, 322, 5, GR, None)


def bth_013(d):
    d.shadow(320, 330, 330, 330, 40)
    d.rect(160, 170, 480, 490, WH, 30)
    d.circ(320, 330, 120, (226, 232, 238), OL, 3)
    for k in range(1, 6):
        d.circ(320, 330, 120 - k * 20, None, (170, 180, 190), 3)
    d.circ(320, 330, 18, ST, STD)


# ---------------------------------------------------------------- bedroom
def bed_002(d):
    d.shadow(320, 520, 520, 50)
    d.rect(70, 400, 570, 460, WOOD, 10, WOODD)
    for x in (100, 540):
        d.rect(x - 12, 455, x + 12, 520, WOODD, 4, None)
    d.poly([(95, 400), (300, 400), (300, 360), (140, 230), (95, 260)], (210, 228, 242), OL)
    d.rect(300, 350, 555, 400, (210, 228, 242), 14)
    d.poly([(130, 255), (175, 225), (210, 255), (165, 285)], WH, OL)
    d.line([(300, 400), (240, 470), (180, 400)], 6, STD)


def bed_003(d):
    for cx in (210, 430):
        d.shadow(cx, 535, 190, 40)
        d.poly([(cx - 90, 530), (cx + 90, 530), (cx + 55, 330), (cx - 55, 330)], DK, RUB)
        d.ell(cx - 55, 315, cx + 55, 345, RUB, DK)
        d.ell(cx - 32, 320, cx + 32, 340, (40, 46, 54), None)
    d.rect(405, 170, 455, 335, WOOD, 6, WOODD)


def bed_005(d):
    d.shadow(320, 500, 520, 60)
    d.poly([(80, 470), (520, 470), (580, 340), (140, 340)], (96, 150, 210), BLUED)
    d.poly([(80, 470), (520, 470), (520, 500), (80, 500)], BLUED, BLUED)
    d.poly([(520, 470), (580, 340), (580, 370), (520, 500)], (40, 72, 120), None)
    for t in (0.33, 0.66):
        d.line([(80 + 440 * t, 470), (140 + 440 * t, 340)], 3, BLUED)


# ---------------------------------------------------------------- living
def liv_001(d):
    d.shadow(320, 500, 440, 60)
    for x in (190, 450):
        d.rect(x - 14, 330, x + 14, 495, WOODD, 6, None)
    d.ell(110, 270, 530, 380, WOOD, WOODD, 4)
    d.ell(110, 255, 530, 365, (214, 172, 128), WOODD, 3)


def liv_002(d):
    d.poly([(80, 330), (430, 330), (430, 560), (80, 560)], WOOD, WOODD)
    d.poly([(80, 300), (450, 300), (450, 330), (80, 330)], WOODD, None)
    d.poly([(430, 330), (450, 300), (450, 560), (430, 560)], (130, 92, 60), None)
    d.ell(380, 260, 500, 380, (226, 232, 236), OL, 4)
    d.ell(400, 280, 480, 360, (244, 247, 249), None)


def liv_003(d):
    d.shadow(320, 470, 520, 60)
    d.poly([(70, 470), (540, 470), (590, 330), (120, 330)], (236, 236, 228), OL)
    for k in range(1, 12):
        t = k / 12
        d.line([(70 + 470 * t, 470), (120 + 470 * t, 330)], 2, (200, 196, 182))
    for k in range(1, 5):
        t = k / 5
        d.line([(70 + 50 * t, 470 - 140 * t), (540 + 50 * t, 470 - 140 * t)], 2, (200, 196, 182))
    d.poly([(70, 470), (380, 470), (430, 330), (120, 330)], (176, 74, 66), REDD)
    d.poly([(100, 450), (350, 450), (390, 350), (138, 350)], (226, 160, 92), None)
    d.poly([(380, 470), (430, 330), (470, 390), (440, 480)], (150, 60, 56), REDD)


def liv_004(d):
    d.shadow(320, 545, 460, 50)
    d.rect(150, 140, 490, 420, (98, 140, 150), 60, (60, 96, 104))
    d.rect(110, 280, 210, 470, (84, 124, 134), 40, (60, 96, 104))
    d.rect(430, 280, 530, 470, (84, 124, 134), 40, (60, 96, 104))
    d.rect(190, 340, 450, 440, (118, 162, 170), 30, (60, 96, 104))
    d.rect(200, 460, 440, 520, (98, 140, 150), 24, (60, 96, 104))
    for x in (150, 490):
        d.rect(x - 10, 470, x + 10, 540, WOODD, 4, None)


# ---------------------------------------------------------------- entry
def ext_001(d):
    steps = [(80, 520, 560), (160, 440, 560), (240, 360, 560), (320, 280, 560)]
    d.shadow(330, 560, 500, 30, 40)
    for x0, y0, x1 in steps:
        d.rect(x0, y0, x1, y0 + 80, (214, 206, 196), 4, (150, 140, 128))
        d.rect(x0, y0, x1, y0 + 10, (190, 180, 168), 2, None)
    for x, y in ((130, 520), (290, 360), (450, 200)):
        pass
    for (x, y) in ((120, 520), (280, 360), (400, 280)):
        d.tube([(x, y), (x, y - 140)], 16)
    d.tube([(90, 400), (430, 120 + 20)], 22)


def ext_002(d):
    d.shadow(320, 470, 500, 40)
    d.rect(80, 380, 560, 410, WOODD, 4, None)
    d.poly([(80, 470), (320, 380), (320, 470)], RUB, DK)
    d.poly([(320, 380), (560, 470), (320, 470)], RUB, DK)
    for k in range(1, 6):
        t = k / 6
        d.line([(80 + 240 * t, 470 - 90 * t), (80 + 240 * t, 470)], 3, DK)
        d.line([(320 + 240 * t, 380 + 90 * t), (320 + 240 * t, 470)], 3, DK)


def ext_003(d):
    d.beam([(260, 260), (380, 260), (520, 600), (120, 600)])
    d.rect(250, 120, 390, 170, DK, 12, None)
    d.poly([(240, 170), (400, 170), (380, 270), (260, 270)], (70, 78, 88), DK)
    d.rect(270, 250, 370, 275, GLOW, 8, YEL)
    d.ell(296, 275, 344, 320, WH, OL)


def ext_004(d):
    d.poly([(170, 120), (470, 120), (510, 250), (130, 250)], BLUED, DK)
    for k in range(1, 4):
        t = k / 4
        d.line([(170 + 300 * t - 40 * t + 40 * t, 120), (130 + 380 * t, 250)], 2, (110, 150, 210))
    d.line([(150, 185), (490, 185)], 2, (110, 150, 210))
    d.rect(300, 250, 340, 300, DK, 4, None)
    d.beam([(220, 420), (420, 420), (560, 620), (80, 620)])
    d.rect(200, 300, 440, 430, (70, 78, 88), 20, DK)
    for x in range(230, 420, 30):
        for y in (340, 385):
            d.circ(x + 6, y, 9, GLOW, YEL, 2)


# ---------------------------------------------------------------- hallway
def hal_001(d):
    d.glow(320, 300, 230)
    d.circ(320, 300, 120, WH, OL, 4)
    d.circ(320, 300, 84, GLOW, YEL, 3)
    d.ell(290, 400, 350, 440, (232, 236, 240), OL)


def hal_002(d):
    d.circ(200, 380, 130, (226, 232, 238), OL, 4)
    d.circ(200, 380, 50, BG, OL, 3)
    for r in (70, 90, 110):
        d.circ(200, 380, r, None, (200, 206, 214), 6)
    strip = [(200, 250), (330, 230), (470, 210), (580, 190)]
    d.glow(450, 210, 160, GLOW, 120)
    d.line(strip, 22, WH); d.line(strip, 22, None or (240, 242, 244))
    for k in range(12):
        t = k / 11
        x = 220 + 350 * t
        y = 248 - 58 * t
        d.circ(x, y, 6, YEL, None)


def hal_003(d):
    d.wall(500)
    d.shadow(320, 330, 520, 30, 40)
    for x in (130, 320, 510):
        d.rect(x - 22, 330, x + 22, 360, ST, 8, STD)
        d.tube([(x, 310), (x, 345)], 12)
    d.line([(60, 295), (580, 295)], 34, WOODD)
    d.line([(60, 290), (580, 290)], 24, WOOD)
    d.line([(60, 282), (580, 282)], 5, (226, 190, 150))


# ---------------------------------------------------------------- kitchen
def kit_001(d):
    d.rect(110, 90, 530, 300, WH, 10)
    d.rect(130, 110, 510, 280, (236, 240, 244), 6, (200, 206, 212))
    d.line([(150, 300), (190, 430)], 10, STD); d.line([(490, 300), (450, 430)], 10, STD)
    d.rect(170, 420, 470, 445, ST, 6, STD)
    for x, col in ((215, ORG), (285, GREEN), (355, RED), (420, YEL)):
        d.rect(x - 24, 340, x + 24, 420, col, 10, OL)
        d.rect(x - 26, 330, x + 26, 346, DK, 4, None)
    d.shadow(320, 460, 320, 30, 40)


def kit_002(d):
    d.shadow(320, 520, 420, 50)
    for y, w in ((440, 380), (300, 320)):
        d.ell(320 - w / 2, y - 40, 320 + w / 2, y + 40, WOOD, WOODD)
        d.ell(320 - w / 2, y - 52, 320 + w / 2, y + 28, (222, 182, 140), WOODD)
    d.tube([(320, 300), (320, 420)], 14)


def kit_002_items(d):
    for x, y, col in ((210, 330, ORG), (290, 340, GREEN), (380, 330, RED), (430, 345, YEL),
                      (240, 200, BLUE), (320, 210, ORG), (390, 200, GREEN)):
        d.rect(x - 24, y, x + 24, y + 70, col, 10, OL)
        d.rect(x - 26, y - 10, x + 26, y + 6, DK, 4, None)


def kit_003(d):
    d.shadow(200, 560, 220, 40)
    d.rect(110, 260, 290, 555, RED, 60, REDD)
    d.rect(150, 210, 250, 270, RED, 14, REDD)
    d.rect(180, 175, 220, 215, ST, 6, STD)
    d.rect(110, 360, 290, 380, REDD, 2, None)
    d.rect(370, 220, 530, 380, WH, 22)
    for k in range(4):
        d.rect(400, 250 + k * 18, 500, 258 + k * 18, (196, 204, 212), 4, None)
    d.circ(450, 345, 11, GREEN, None)
    d.line([(220, 195), (320, 150), (360, 300)], 6, DK)


def kit_004(d):
    d.shadow(320, 410, 380, 60)
    d.ell(140, 250, 500, 400, WH, OL, 4)
    d.ell(140, 230, 500, 380, (244, 246, 248), OL, 3)
    for k in range(10):
        a = math.radians(k * 36 + 10)
        d.line([(320 + 120 * math.cos(a), 305 + 50 * math.sin(a)), (320 + 150 * math.cos(a), 305 + 62 * math.sin(a))], 5, (190, 198, 206))
    d.ell(270, 285, 370, 325, (226, 230, 236), OL, 3)
    d.circ(390, 272, 7, RED, None)


def kit_005(d):
    d.shadow(320, 570, 220, 40)
    d.rect(240, 220, 400, 565, RED, 50, REDD)
    d.rect(250, 330, 390, 420, (240, 240, 240), 6, None)
    d.rect(285, 150, 355, 225, DK, 10, None)
    d.line([(355, 165), (450, 140)], 14, DK)
    d.line([(300, 150), (380, 110)], 10, DK)
    hose = bez((285, 180), (180, 200), (170, 400), (230, 470))
    d.line(hose, 14, DK)
    d.circ(320, 270, 22, WH, DK, 3)
    d.line([(320, 270), (332, 258)], 3, RED)


def kit_006(d):
    d.shadow(320, 470, 300, 40)
    d.rect(190, 170, 450, 450, WH, 40)
    d.rect(230, 210, 410, 290, (196, 226, 214), 10, DK, 3)
    for k in range(3):
        d.rect(250 + k * 50, 230, 285 + k * 50, 270, (60, 100, 90), 4, None)
    for k in range(4):
        d.rect(240, 320 + k * 26, 400, 330 + k * 26, (200, 206, 212), 5, None)
    d.circ(320, 425, 10, GREEN, None)


# ---------------------------------------------------------------- balcony
def bal_001(d):
    d.poly([(60, 520), (580, 520), (520, 300), (120, 300)], (214, 206, 196), (150, 140, 128))
    d.poly([(60, 520), (330, 520), (300, 300), (120, 300)], (110, 140, 130), (80, 110, 100))
    for x in range(140, 320, 18):
        for y in range(320, 510, 20):
            d.circ(x - (y - 300) * 0.22 + 10, y, 2.5, (150, 180, 170), None)
    d.rect(360, 300, 520, 350, ORG, 16, OL)
    d.line([(440, 350), (440, 400), (500, 470)], 10, DK)
    d.shadow(440, 520, 160, 30, 40)


def bal_002(d):
    d.poly([(40, 560), (600, 560), (560, 470), (80, 470)], (214, 206, 196), (150, 140, 128))
    d.tube([(70, 230), (570, 230)], 26)
    d.tube([(70, 300), (570, 300)], 12)
    for x in range(90, 571, 48):
        d.tube([(x, 230), (x, 480)], 12)


# ---------------------------------------------------------------- mobility
def mob_001(d):
    d.shadow(320, 560, 420, 40)
    for x0, x1 in ((150, 210), (430, 490)):
        d.tube([(x0, 555), (x0 + 20, 220), (x1 - 20, 220), (x1, 555)], 18)
        d.tube([(x0 + 8, 420), (x1 - 8, 420)], 14)
        d.rect(x0 + 10, 205, x1 - 10, 235, DK, 12, None)
        for x in (x0, x1):
            d.ell(x - 14, 548, x + 14, 566, RUB, None)
    d.tube([(185, 300), (455, 300)], 16)


def mob_002(d):
    d.shadow(320, 570, 440, 40)
    d.tube([(160, 520), (220, 200)], 18)
    d.tube([(470, 520), (420, 250)], 18)
    d.tube([(220, 200), (180, 190)], 18)
    d.rect(150, 175, 205, 205, DK, 12, None)
    d.rect(240, 330, 450, 360, (60, 110, 140), 10, (40, 80, 100))
    d.tube([(210, 345), (460, 345)], 12)
    d.line([(200, 210), (250, 270), (420, 280)], 4, DK)
    wheel(d, 160, 525, 42, False)
    wheel(d, 470, 525, 42, False)


def mob_003(d):
    d.shadow(320, 560, 460, 40)
    wheel(d, 270, 420, 140)
    d.tube([(210, 160), (230, 330), (420, 330), (450, 470)], 16)
    d.tube([(210, 160), (170, 160)], 16)
    d.rect(200, 300, 420, 340, DK, 10, None)
    d.rect(195, 170, 240, 320, DK, 10, None)
    d.tube([(400, 330), (390, 480)], 14)
    d.rect(440, 470, 500, 485, DK, 4, None)
    wheel(d, 420, 530, 30, False)


def mob_004(d):
    d.shadow(320, 560, 460, 40)
    d.tube([(180, 160), (210, 340), (440, 340), (470, 470)], 16)
    d.tube([(180, 160), (140, 160)], 16)
    d.rect(190, 310, 440, 350, (60, 110, 140), 10, None)
    d.rect(180, 170, 230, 330, (60, 110, 140), 10, None)
    d.tube([(220, 350), (220, 500), (430, 500)], 14)
    d.rect(460, 470, 520, 485, DK, 4, None)
    for x in (220, 430):
        wheel(d, x, 520, 42, False)


def mob_005(d):
    d.shadow(330, 570, 120, 26)
    d.line([(330, 560), (330, 210)], 22, WOODD)
    d.line([(330, 560), (330, 210)], 14, WOOD)
    d.arc(330, 120, 450, 300, 180, 360, 22, WOODD)
    d.arc(334, 124, 446, 296, 180, 360, 12, WOOD)
    d.ell(310, 555, 350, 580, RUB, None)


def mob_006(d):
    d.shadow(320, 560, 280, 40)
    d.tube([(320, 470), (320, 170), (250, 150)], 20)
    d.rect(200, 135, 270, 165, DK, 12, None)
    d.tube([(220, 545), (280, 470), (360, 470), (420, 545)], 16)
    d.tube([(280, 470), (260, 545)], 14); d.tube([(360, 470), (380, 545)], 14)
    for x in (220, 260, 380, 420):
        d.ell(x - 14, 538, x + 14, 556, RUB, None)


def mob_007(d):
    d.shadow(320, 480, 540, 40)
    d.poly([(60, 470), (580, 330), (580, 360), (60, 480)], STD, STD)
    d.poly([(60, 470), (580, 330), (580, 300), (60, 455)], ST, STD)
    for k in range(1, 14):
        t = k / 14
        d.line([(60 + 520 * t, 461 - 147 * t), (60 + 520 * t, 470 - 140 * t)], 3, STD)
    d.line([(320, 392), (320, 410)], 6, DK)
    d.rect(300, 370, 340, 384, DK, 4, None)


# ---------------------------------------------------------------- smart home
def smt_001(d):
    d.shadow(320, 520, 220, 40)
    d.rect(240, 120, 400, 510, DK, 50, None)
    d.circ(320, 210, 46, (30, 34, 40), STD, 4)
    d.circ(320, 210, 20, (60, 90, 120), None)
    d.circ(320, 410, 52, (90, 98, 108), None)
    d.circ(320, 410, 40, None, TEALL, 6)


def smt_002(d):
    d.rect(150, 60, 490, 600, WOOD, 6, WOODD)
    d.rect(240, 130, 400, 470, DK, 24, None)
    d.rect(262, 160, 378, 300, (40, 46, 54), 10, None)
    for r in range(4):
        for c in range(3):
            d.circ(285 + c * 35, 182 + r * 32, 8, TEALL, None)
    d.circ(320, 345, 28, ST, STD)
    d.line([(320, 345), (460, 345)], 26, STD); d.line([(320, 345), (460, 345)], 16, ST)
    d.circ(320, 430, 9, GREEN, None)


def smt_003(d):
    d.shadow(320, 540, 220, 40)
    d.ell(230, 500, 410, 545, WH, OL)
    d.rect(305, 400, 335, 510, WH, 10)
    d.circ(320, 300, 120, WH, OL, 4)
    d.circ(320, 300, 70, DK, None)
    d.circ(320, 300, 40, (40, 60, 90), STD, 4)
    d.circ(305, 285, 10, (140, 170, 210), None)
    d.circ(390, 230, 7, RED, None)


def smt_004(d):
    d.poly([(320, 120), (520, 230), (320, 330), (120, 230)], (226, 232, 238), None)
    d.shadow(320, 400, 260, 60, 40)
    d.poly([(220, 230), (420, 230), (440, 360), (320, 440), (200, 360)], WH, OL)
    d.ell(270, 300, 370, 400, (236, 238, 240), OL)
    for k in range(3):
        d.arc(270 + k * 8, 300 + k * 8, 370 - k * 8, 400 - k * 8, 200, 340, 2, (190, 196, 204))
    d.circ(320, 260, 7, RED, None)


def smt_005(d):
    d.rect(60, 60, 330, 600, WOOD, 6, WOODD)
    d.rect(340, 60, 400, 600, (226, 220, 210), 4, (180, 170, 156))
    d.rect(250, 260, 320, 400, WH, 14)
    d.rect(350, 290, 400, 370, WH, 12)
    d.circ(285, 285, 7, GREEN, None)
    d.circ(220, 330, 12, ST, STD)
    for k, r in enumerate((60, 90)):
        d.arc(320 - r, 330 - r, 320 + r, 330 + r, 100, 260, 4, TEALL)


def smt_006(d):
    d.shadow(450, 500, 220, 40)
    d.rect(370, 330, 530, 490, WH, 30)
    d.circ(450, 390, 10, GREEN, None)
    for r in (30, 52):
        d.arc(450 - r, 300 - r, 450 + r, 300 + r, 225, 315, 6, TEAL)
    d.rect(180, 110, 280, 560, (60, 110, 140), 40, (40, 80, 100))
    d.shadow(230, 340, 200, 200, 50)
    d.rect(140, 250, 320, 430, DK, 50, None)
    d.circ(230, 340, 62, RED, None)
    d.circ(214, 324, 16, (232, 120, 116), None)


def smt_007(d):
    d.shadow(320, 520, 360, 60)
    d.rect(150, 380, 490, 500, WH, 30)
    d.ell(150, 320, 490, 440, WH, OL)
    for k in range(7):
        a = math.radians(k * 360 / 7 - 90)
        d.ell(320 + 120 * math.cos(a) - 26, 380 + 42 * math.sin(a) - 12, 320 + 120 * math.cos(a) + 26, 380 + 42 * math.sin(a) + 12,
              (ORG, GREEN, BLUE, RED, YEL, TEALL, (180, 140, 210))[k], OL, 2)
    d.circ(320, 380, 26, TEAL, None)
    d.rect(250, 450, 390, 475, (196, 226, 214), 6, DK, 2)


def smt_008(d):
    d.shadow(320, 530, 260, 50)
    d.rect(220, 200, 420, 520, (70, 78, 88), 40, DK)
    d.ell(220, 170, 420, 230, (90, 98, 108), DK)
    d.ell(232, 178, 408, 222, None, TEALL, 6)
    for y in range(270, 500, 18):
        for x in range(240, 401, 18):
            d.circ(x + (9 if (y // 18) % 2 else 0), y, 3, (100, 108, 118), None)


def smt_009(d):
    d.ell(140, 430, 500, 520, (170, 210, 240), (120, 170, 210))
    d.ell(230, 330, 410, 410, WH, OL)
    d.rect(230, 370, 410, 450, WH, 0, None)
    d.line([(230, 370), (230, 450)], 3, OL); d.line([(410, 370), (410, 450)], 3, OL)
    d.ell(230, 410, 410, 490, WH, OL)
    d.circ(320, 370, 9, BLUE, None)
    d.poly([(470, 140), (510, 220), (430, 220)], (90, 160, 220), None)
    d.circ(470, 235, 40, (90, 160, 220), None)


def smt_010(d):
    kit_004(d)
    d.ell(140, 230, 500, 380, None, TEALL, 6)
    for r in (50, 80, 110):
        d.arc(320 - r, 160 - r, 320 + r, 160 + r, 225, 315, 8, TEAL)


def smt_011(d):
    d.shadow(320, 340, 340, 340, 40)
    d.rect(160, 170, 480, 490, WH, 40)
    d.circ(320, 330, 110, REDD, None)
    d.circ(320, 322, 100, RED, None)
    d.circ(290, 290, 24, (232, 120, 116), None)


def smt_012(d):
    d.rect(250, 60, 390, 580, (60, 110, 140), 40, (40, 80, 100))
    d.shadow(320, 330, 260, 260, 50)
    d.rect(200, 210, 440, 450, DK, 60, None)
    d.rect(222, 232, 418, 428, (226, 238, 232), 46, None)
    d.poly([(320, 400), (270, 320), (370, 320)], RED, None)
    d.circ(320, 300, 52, RED, None)
    d.circ(320, 300, 22, WH, None)


# ---------------------------------------------------------------- emergency
def emg_001(d):
    d.shadow(320, 330, 400, 460, 40)
    d.rect(140, 90, 500, 560, WH, 18)
    d.rect(140, 90, 500, 170, RED, 18, None)
    d.rect(140, 140, 500, 170, RED, 0, None)
    d.rect(305, 105, 335, 155, WH, 3, None); d.rect(295, 115, 345, 145, WH, 3, None)
    for k in range(5):
        y = 220 + k * 66
        d.circ(190, y, 18, TEALL, None)
        d.rect(230, y - 10, 450 - (k % 2) * 60, y + 10, (204, 210, 216), 6, None)


def emg_002(d):
    d.shadow(320, 520, 440, 50)
    d.rect(250, 150, 390, 210, None, 20, DK, 14)
    d.rect(110, 200, 530, 500, RED, 36, REDD)
    d.rect(110, 280, 530, 296, REDD, 0, None)
    d.rect(290, 300, 350, 460, WH, 8, None)
    d.rect(240, 350, 400, 410, WH, 8, None)


def emg_003(d):
    d.beam([(400, 250), (400, 390), (640, 520), (640, 120)])
    d.shadow(300, 420, 360, 40)
    d.rect(100, 280, 360, 360, DK, 30, None)
    d.poly([(350, 270), (420, 240), (420, 400), (350, 370)], (80, 88, 98), DK)
    d.ell(405, 240, 440, 400, GLOW, YEL)
    d.rect(200, 268, 250, 290, ORG, 8, None)


def emg_004(d):
    d.glow(320, 250, 180)
    d.ell(200, 120, 440, 370, (255, 250, 230), OL, 4)
    d.rect(255, 350, 385, 450, WH, 10)
    for k in range(4):
        d.rect(262, 365 + k * 18, 378, 371 + k * 18, (210, 214, 218), 3, None)
    d.rect(275, 450, 365, 500, ST, 8, STD)
    d.rect(420, 410, 520, 460, WH, 8, OL, 3)
    d.rect(520, 425, 532, 445, OL, 2, None)
    for k in range(3):
        d.rect(430 + k * 28, 420, 452 + k * 28, 450, GREEN, 3, None)


def emg_005(d):
    d.shadow(330, 520, 420, 50)
    d.rect(140, 140, 500, 500, (64, 120, 170), 20, BLUED)
    d.rect(140, 110, 300, 160, (64, 120, 170), 14, BLUED)
    d.rect(170, 170, 520, 480, WH, 14)
    d.circ(345, 320, 80, (232, 90, 90), None)
    d.rect(330, 270, 360, 370, WH, 4, None); d.rect(295, 305, 395, 335, WH, 4, None)


def emg_006(d):
    d.shadow(320, 520, 460, 50)
    d.rect(110, 180, 530, 500, WH, 40)
    d.rect(140, 120, 300, 200, DK, 30, None)
    d.rect(150, 210, 290, 470, (232, 236, 240), 20, OL, 2)
    for r in range(4):
        for c in range(3):
            d.rect(320 + c * 64, 215 + r * 66, 370 + c * 64, 265 + r * 66, (210, 220, 228) if r < 3 else RED, 12, OL, 2)
    for k in range(3):
        d.circ(220, 260 + k * 75, 26, (180, 200, 220), OL, 2)


# ---------------------------------------------------------------- health
def hlt_001(d):
    d.shadow(250, 520, 300, 50)
    d.rect(120, 260, 380, 500, WH, 30)
    screen(d, 150, 290, 350, 400)
    d.circ(250, 450, 26, TEAL, None)
    hose = bez((380, 440), (450, 450), (430, 330), (470, 300))
    d.line(hose, 8, DK)
    d.rect(430, 140, 560, 330, (60, 90, 130), 30, BLUED)
    d.rect(450, 170, 540, 220, (90, 130, 180), 10, None)


def hlt_002(d):
    d.shadow(320, 470, 380, 50)
    d.rect(150, 290, 490, 450, (60, 110, 140), 60, (40, 80, 100))
    d.rect(140, 210, 480, 330, WH, 50)
    screen(d, 210, 230, 410, 310)
    d.rect(460, 330, 520, 370, (40, 80, 100), 10, None)


def hlt_003(d):
    d.shadow(300, 530, 300, 50)
    d.rect(170, 160, 410, 510, WH, 40)
    screen(d, 200, 200, 380, 330)
    d.circ(250, 420, 24, TEAL, None); d.circ(330, 420, 24, (210, 218, 226), OL, 2)
    d.rect(270, 90, 310, 170, ORG, 6, OL)
    d.rect(450, 280, 510, 470, (230, 236, 242), 24)
    d.rect(468, 230, 492, 290, (120, 196, 230), 6, OL)


def hlt_004(d):
    d.shadow(320, 470, 520, 50)
    d.rect(80, 230, 560, 450, WH, 20)
    cols = (ORG, YEL, BLUE)
    for r in range(3):
        for c in range(7):
            x = 100 + c * 64
            y = 250 + r * 64
            d.rect(x, y, x + 56, y + 56, cols[r], 10, OL, 2)


# ---------------------------------------------------------------- services (one per category)
def house(d, cx, cy, s=1.0, fill=WH):
    d.poly([(cx - 130 * s, cy), (cx, cy - 110 * s), (cx + 130 * s, cy)], TEAL, None)
    d.rect(cx - 100 * s, cy, cx + 100 * s, cy + 150 * s, fill, 6)
    d.rect(cx - 25 * s, cy + 70 * s, cx + 25 * s, cy + 150 * s, WOOD, 4, WOODD)


def svc(d):
    house(d, 240, 300)
    d.shadow(240, 460, 300, 40)
    d.rect(360, 180, 540, 460, WH, 16)
    d.rect(410, 160, 490, 200, DK, 10, None)
    for k in range(4):
        y = 240 + k * 52
        d.line([(385, y), (398, y + 12), (420, y - 12)], 7, TEAL)
        d.rect(435, y - 6, 515, y + 6, GR, 5, None)


def wel(d):
    d.shadow(320, 500, 360, 50)
    d.poly([(170, 300), (470, 300), (430, 470), (210, 470)], WH, OL)
    d.arc(430, 320, 530, 420, 270, 90, 18, OL)
    d.rect(150, 470, 490, 500, (226, 232, 238), 14)
    d.circ(285, 230, 40, RED, None); d.circ(355, 230, 40, RED, None)
    d.poly([(248, 245), (392, 245), (320, 320)], RED, None)


def hm(d):
    house(d, 320, 320, 1.15, (232, 238, 243))
    d.shadow(320, 520, 360, 40)
    d.poly(rot(320, 380, 300, 34, -40), ST, STD)
    d.circ(205, 477, 40, ST, STD); d.circ(205, 477, 16, (232, 238, 243), None)
    d.poly(rot(320, 380, 260, 26, 40), ORG, OL)
    d.poly(rot(420, 470, 70, 14, 40), STD, None)


def nur(d):
    d.shadow(320, 520, 440, 50)
    d.rect(250, 170, 390, 230, None, 20, DK, 14)
    d.rect(110, 220, 530, 500, (60, 110, 140), 40, (40, 80, 100))
    d.circ(320, 360, 80, WH, None)
    d.rect(300, 310, 340, 410, RED, 4, None); d.rect(270, 340, 370, 380, RED, 4, None)


def phy(d):
    d.shadow(320, 520, 520, 50)
    d.poly([(80, 500), (540, 500), (580, 420), (120, 420)], (98, 160, 150), TEAL)
    for x in (230, 420):
        d.rect(x - 70, 330, x + 70, 350, STD, 6, None)
        d.rect(x - 70, 300, x - 40, 380, DK, 8, None)
        d.rect(x + 40, 300, x + 70, 380, DK, 8, None)
    d.circ(450, 180, 90, ORG, (200, 100, 40))
    d.arc(380, 110, 520, 250, 200, 320, 5, (250, 190, 140))


def dx(d):
    d.shadow(320, 520, 440, 50)
    tube_pts = bez((180, 160), (120, 400), (330, 470), (360, 300))
    d.line(tube_pts, 12, DK)
    d.line([(180, 160), (150, 120)], 8, STD); d.line([(180, 160), (230, 120)], 8, STD)
    d.circ(360, 270, 42, ST, STD, 4); d.circ(360, 270, 24, STH, None)
    d.rect(450, 170, 510, 470, WH, 26)
    d.rect(450, 330, 510, 470, RED, 26, None)
    d.rect(445, 160, 515, 190, BLUE, 8, None)


def pm(d):
    house(d, 260, 290)
    d.shadow(300, 470, 380, 40)
    d.circ(420, 330, 90, (220, 236, 240), DK, 16)
    d.line([(485, 395), (560, 470)], 24, DK)
    d.line([(380, 300), (410, 330), (460, 290)], 10, TEAL)


def trn(d):
    d.shadow(320, 480, 520, 40)
    d.poly([(80, 430), (90, 350), (190, 340), (250, 260), (430, 260), (500, 340), (560, 360), (560, 430)], WH, OL)
    d.poly([(270, 280), (330, 280), (330, 340), (220, 340)], (180, 210, 240), OL, 2)
    d.poly([(350, 280), (420, 280), (470, 340), (350, 340)], (180, 210, 240), OL, 2)
    d.rect(80, 380, 560, 400, TEAL, 0, None)
    for x in (180, 450):
        wheel(d, x, 440, 46, False)


DRAW = {
    "bth-002": bth_002, "bth-004": bth_004, "bth-006": bth_006, "bth-007": bth_007, "bth-009": bth_009,
    "bth-010": bth_010, "bth-011": bth_011, "bth-012": bth_012, "bth-013": bth_013,
    "bed-002": bed_002, "bed-003": bed_003, "bed-005": bed_005,
    "liv-001": liv_001, "liv-002": liv_002, "liv-003": liv_003, "liv-004": liv_004,
    "ext-001": ext_001, "ext-002": ext_002, "ext-003": ext_003, "ext-004": ext_004,
    "hal-001": hal_001, "hal-002": hal_002, "hal-003": hal_003,
    "kit-001": kit_001, "kit-002": lambda d: (kit_002(d), kit_002_items(d)), "kit-003": kit_003,
    "kit-004": kit_004, "kit-005": kit_005, "kit-006": kit_006,
    "bal-001": bal_001, "bal-002": bal_002,
    "mob-001": mob_001, "mob-002": mob_002, "mob-003": mob_003, "mob-004": mob_004,
    "mob-005": mob_005, "mob-006": mob_006, "mob-007": mob_007,
    "smt-001": smt_001, "smt-002": smt_002, "smt-003": smt_003, "smt-004": smt_004, "smt-005": smt_005, "smt-006": smt_006,
    "smt-007": smt_007, "smt-008": smt_008, "smt-009": smt_009, "smt-010": smt_010, "smt-011": smt_011,
    "smt-012": smt_012,
    "emg-001": emg_001, "emg-002": emg_002, "emg-003": emg_003, "emg-004": emg_004, "emg-005": emg_005,
    "emg-006": emg_006,
    "hlt-001": hlt_001, "hlt-002": hlt_002, "hlt-003": hlt_003, "hlt-004": hlt_004,
    "svc-service": svc, "wel-service": wel, "hm-service": hm, "nur-service": nur, "phy-service": phy,
    "dx-service": dx, "pm-service": pm, "trn-service": trn,
}

if __name__ == "__main__":
    only = sys.argv[2:] or list(DRAW)
    for name in only:
        d = D()
        DRAW[name](d)
        d.save(name)
    total = sum(f.stat().st_size for f in OUT.glob("*.webp"))
    print(len(list(OUT.glob("*.webp"))), "files", total // 1024, "KB")
