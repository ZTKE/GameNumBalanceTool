from pathlib import Path
import csv
import math
import re
import zipfile
from PIL import Image, ImageDraw, ImageFont


TSV = Path(r"C:\Users\w\xwechat_files\wxid_4kcdrac785ft12_a395\temp\RWTemp\2026-06\9e20f478899dc29eb19741386f9343c8\country_settings_5.tsv")
OUT = Path.cwd() / "original_ww1_flags_1000x600"
ZIP = Path.cwd() / "original_ww1_flags_1000x600.zip"
W, H = 1000, 600


DATA = """
OCEAN|field|#001B52,#0D4F8B,#C7E9FF|waves|
AAR|h|#EAF8FF,#71B7D9,#E13B2B,#F5C84C|compass|
CHL|canton|#143F88,#FFFFFF,#C92A2A,#F3C74B|star|
ARG|h|#74B9E8,#FFFFFF,#F2B632,#7A4D20|sun|
GBR|british|#102B63,#FFFFFF,#C9162C,#D6A44A|crown|
NZL|southern|#102B63,#C51F32,#FFFFFF,#8CC8FF|none|
AST|southern_gold|#102A5C,#E3B23C,#FFFFFF,#2E7D32|none|
URG|h|#FFFFFF,#3C7DCA,#F2C230,#A67C00|sun|
SAF|chevron|#1A5C35,#F2C94C,#111111,#C23B3B,#1E4D8C|star|
BRA|diamond|#1B7F3A,#F7D246,#1E4D8C,#FFFFFF|sun|
PAR|h|#C42032,#FFFFFF,#224B9B,#F2C94C|roundel|
POR|v|#1F7A3B,#B51D2A,#F5C242,#FFFFFF|shield|
BOL|h|#C7362F,#F2D34B,#2F7D3D,#FFFFFF|star|
FRA|v|#21468B,#FFFFFF,#C83232,#D8A62A|crown|
PRU|v|#C92A2A,#FFFFFF,#F0C24B,#6A3F22|sun|
COG|diag|#2D70B7,#F3C54A,#111111,#FFFFFF|star|
DEI|h|#B22234,#FFFFFF,#21468B,#F28C28|sun|
ECU|h|#F6D04D,#2446A8,#D22B2B,#FFFFFF|eagle|
COL|h|#F6D04D,#21468B,#C92A2A,#FFFFFF|eagle|
VEN|h|#F4D03F,#1F4AA8,#C92A2A,#FFFFFF|stars|
MLY|stripes|#C92A2A,#FFFFFF,#102B63,#F4D03F|crescent|
SPA|h_wide|#B31B2C,#F4C542,#632B16,#FFFFFF|shield|
HOL|h|#AE1C28,#FFFFFF,#21468B,#F28C28|crown|
ETH|h|#2F8F46,#F3D13B,#C83232,#FFFFFF|lion|
LIB|stripes|#B22234,#FFFFFF,#1F3C88,#F4D03F|star|
PHI|tri|#1F4AA8,#C83232,#FFFFFF,#F4C542|sun|
SIA|h_wide|#C83232,#FFFFFF,#203A7A,#F4D03F|sun|
PAN|quarter|#FFFFFF,#1F4AA8,#C83232,#F4D03F|stars|
RAJ|ensign|#8B1E2D,#102B63,#FFFFFF,#F4D03F|star|
COS|h_wide|#102B63,#FFFFFF,#C83232,#F4D03F|mountain|
BRM|field|#B51D2A,#21468B,#FFFFFF,#F4D03F|bird|
NIC|h|#1F6BC1,#FFFFFF,#F4D03F,#2F8F46|mountain|
YEM|h|#C83232,#FFFFFF,#111111,#2F8F46|crescent|
ELS|h|#1F6BC1,#FFFFFF,#F4D03F,#2F8F46|mountain|
HON|h|#1F6BC1,#FFFFFF,#F4D03F|stars|
GUA|v|#4AA3DF,#FFFFFF,#2F8F46,#F4D03F|bird|
MEX|v|#1B7F3A,#FFFFFF,#C83232,#8B5A2B|eagle|
SAU|field|#0B6E3B,#FFFFFF,#D8A62A|crescent|
OMA|v|#B51D2A,#FFFFFF,#0B6E3B,#D8A62A|swords|
DOM|cross|#1F4AA8,#C83232,#FFFFFF,#F4D03F|sun|
HAI|h|#2446A8,#C83232,#FFFFFF,#2F8F46|palm|
USA|stripes|#B22234,#FFFFFF,#1F3C88,#D8A62A|ring|
CUB|tri|#1F4AA8,#FFFFFF,#C83232,#F4D03F|star|
YUN|field|#D9902F,#143F88,#F4D03F,#111111|text:\\u6ec7|
JAP|field|#FFFFFF,#BC002D,#D8A62A|sun_offset|
CHI|canton_sun|#C83232,#102B63,#FFFFFF,#F4D03F|sun|
PER|h|#1F7A3B,#FFFFFF,#C83232,#F4D03F|lion_sun|
SZC|field|#E3C36A,#2446A8,#8B5A2B,#111111|text:\\u5ddd|
NEP|chevron|#C83232,#102B63,#FFFFFF,#F4D03F|mountain|
BHU|diag|#F4C542,#E17A21,#FFFFFF,#111111|dragon|
TIB|rays|#FFFFFF,#C83232,#2446A8,#F4D03F|mountain|
AFG|v|#111111,#B51D2A,#0B6E3B,#FFFFFF|mountain|
XSM|field|#0B6E3B,#FFFFFF,#C83232,#F4D03F|crescent|
SQI|field|#E5A43A,#111111,#FFFFFF|text:\\u9c81|
QIE|field|#F4C542,#102B63,#C83232,#111111|dragon|
GRE|cross_stripes|#1F6BC1,#FFFFFF,#D8A62A|star|
SOV|field|#B51D2A,#F4D03F,#111111|gear_star|
TUR|field|#C83232,#FFFFFF,#0B6E3B,#F4D03F|crescent|
PRC|field|#B51D2A,#F4D03F,#111111|gear_star|
ITA|v|#1B7F3A,#FFFFFF,#C83232,#2446A8|shield|
SIK|field|#2446A8,#C83232,#F4D03F,#FFFFFF|text:\\u65b0|
MAN|h|#F4D03F,#C83232,#2446A8,#111111,#FFFFFF|sun|
ALB|field|#B51D2A,#111111,#D8A62A|eagle|
CRO|h|#C83232,#FFFFFF,#2446A8,#111111|checker|
MEN|h|#2446A8,#FFFFFF,#C83232,#111111,#F4D03F|crescent|
BUL|h|#FFFFFF,#1B7F3A,#C83232,#D8A62A|lion|
CAN|v|#C83232,#FFFFFF,#D8A62A|leaf|
MON|v|#2446A8,#C83232,#F4D03F,#FFFFFF|sun|
ROM|v|#2446A8,#F4D03F,#C83232,#FFFFFF|crown|
SWI|cross|#C83232,#FFFFFF,#D8A62A|mountain|
HUN|h|#C83232,#FFFFFF,#1B7F3A,#D8A62A|crown|
AUS|h|#C83232,#FFFFFF,#111111,#D8A62A|eagle|
GER|h|#111111,#FFFFFF,#C83232,#D8A62A|eagle|
CZE|triangle|#FFFFFF,#C83232,#2446A8,#D8A62A|lion|
POL|h|#FFFFFF,#C83232,#D8A62A|eagle|
LUX|h|#C83232,#FFFFFF,#5BC0EB,#D8A62A|lion|
BEL|v|#111111,#F4D03F,#C83232,#FFFFFF|lion|
IRE|v|#1B7F3A,#FFFFFF,#E17A21,#D8A62A|harp|
LIT|h|#F4D03F,#1B7F3A,#C83232,#FFFFFF|horse|
DEN|nordic|#C83232,#FFFFFF,#D8A62A|crown|
SWE|nordic|#1F6BC1,#F4D03F,#FFFFFF|crowns|
LAT|h|#7A1E2C,#FFFFFF,#D8A62A|sun|
NOR|nordic2|#C83232,#FFFFFF,#102B63,#D8A62A|lion|
FIN|nordic|#FFFFFF,#1F6BC1,#D8A62A|star|
ICE|nordic2|#2446A8,#FFFFFF,#C83232,#D8A62A|mountain|
EST|h|#2446A8,#111111,#FFFFFF,#D8A62A|star|
JBS|field|#B51D2A,#0B6E3B,#F4D03F,#FFFFFF|crescent|
TAN|field|#F4D03F,#20A6A6,#C83232,#111111|text:\\u54c8\\u5bc6|
AZR|h|#2446A8,#C83232,#1B7F3A,#FFFFFF|crescent|
GEO|cross|#FFFFFF,#C83232,#111111|mountain|
MTR|h|#1B7F3A,#2446A8,#FFFFFF,#D8A62A|mountain|
KUB|h|#2446A8,#C83232,#1B7F3A,#D8A62A|horse|
DKB|h|#2446A8,#F4D03F,#C83232,#FFFFFF|spear|
UKR|bicolor|#2446A8,#F4D03F,#D8A62A|trident|
SER|h|#C83232,#2446A8,#FFFFFF,#D8A62A|eagle|
GAL|quarter|#2446A8,#F4D03F,#C83232,#FFFFFF|crown|
WHR|h|#FFFFFF,#C83232,#2446A8,#D8A62A|horse|
KHI|field|#0B6E3B,#111111,#F4D03F,#FFFFFF|crescent|
BUK|field|#0B6E3B,#FFFFFF,#111111,#F4D03F|crescent|
TRK|h|#2446A8,#FFFFFF,#0B6E3B,#F4D03F|crescent|
""".strip()


NOTES = {
    "GBR": "Altered imperial cross language: recognisable Britain, but not the real Union Jack.",
    "FRA": "French revolutionary colours with a gold crown/seal accent and hoist ribbon.",
    "GER": "Imperial black-white-red language with an abstract eagle, not a real state flag.",
    "JAP": "Off-centre rising sun with gold ring; avoids the plain real hinomaru.",
    "USA": "Early US palette with a circular star canton and diagonal accent, not the real stars and stripes.",
    "PRC": "Chinese socialist colour language using a star/gear mark, not the PRC state flag.",
}


def parse_specs():
    specs = []
    for line in DATA.splitlines():
        code, layout, colors, emblem, mark = line.split("|")
        emblem = emblem.encode("utf-8").decode("unicode_escape")
        mark = mark.encode("utf-8").decode("unicode_escape")
        specs.append(
            {
                "code": code,
                "layout": layout,
                "colors": colors.split(","),
                "emblem": emblem,
                "mark": mark,
            }
        )
    return specs


def color(value):
    value = value.strip().lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def safe_filename(text):
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", text)
    return text.strip().rstrip(".") or "unnamed"


def load_font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


FONT_BIG = load_font(190, True)
FONT_MED = load_font(105, True)


def star_points(cx, cy, outer, inner=None, points=5, rotation=-math.pi / 2):
    inner = inner or outer * 0.42
    pts = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = rotation + i * math.pi / points
        pts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return pts


def star(draw, cx, cy, radius, fill, points=5):
    draw.polygon(star_points(cx, cy, radius, points=points), fill=fill)


def sun(draw, cx, cy, radius, fill, rays=16, ray_len=26):
    for i in range(rays):
        angle = 2 * math.pi * i / rays
        pts = [
            (cx + math.cos(angle - 0.08) * radius, cy + math.sin(angle - 0.08) * radius),
            (cx + math.cos(angle) * (radius + ray_len), cy + math.sin(angle) * (radius + ray_len)),
            (cx + math.cos(angle + 0.08) * radius, cy + math.sin(angle + 0.08) * radius),
        ]
        draw.polygon(pts, fill=fill)
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fill)


def crescent(draw, cx, cy, radius, fill, cut):
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fill)
    draw.ellipse([cx - radius + radius * 0.55, cy - radius * 1.02, cx + radius * 1.55, cy + radius * 0.98], fill=cut)


def gear(draw, cx, cy, radius, fill, cut):
    pts = []
    teeth = 14
    for i in range(teeth * 2):
        rr = radius if i % 2 == 0 else radius * 0.78
        angle = -math.pi / 2 + i * math.pi / teeth
        pts.append((cx + math.cos(angle) * rr, cy + math.sin(angle) * rr))
    draw.polygon(pts, fill=fill)
    draw.ellipse([cx - radius * 0.42, cy - radius * 0.42, cx + radius * 0.42, cy + radius * 0.42], fill=cut)


def shield(draw, cx, cy, w, h, fill, outline=None):
    x0, y0 = cx - w / 2, cy - h / 2
    pts = [(x0, y0), (x0 + w, y0), (x0 + w * 0.90, y0 + h * 0.62), (cx, y0 + h), (x0 + w * 0.10, y0 + h * 0.62)]
    draw.polygon(pts, fill=fill, outline=outline)


def crown(draw, cx, cy, w, h, fill, accent):
    x0, y0 = cx - w / 2, cy - h / 2
    pts = [
        (x0, y0 + h),
        (x0 + w, y0 + h),
        (x0 + w * 0.88, y0 + h * 0.35),
        (x0 + w * 0.66, y0 + h * 0.62),
        (cx, y0),
        (x0 + w * 0.34, y0 + h * 0.62),
        (x0 + w * 0.12, y0 + h * 0.35),
    ]
    draw.polygon(pts, fill=fill)
    draw.rectangle([x0 + w * 0.12, y0 + h * 0.74, x0 + w * 0.88, y0 + h * 0.92], fill=accent)


def eagle(draw, cx, cy, scale, fill, accent):
    s = scale
    draw.polygon([(cx, cy - 35 * s), (cx - 98 * s, cy - 88 * s), (cx - 205 * s, cy - 35 * s), (cx - 120 * s, cy - 12 * s), (cx - 190 * s, cy + 42 * s), (cx - 72 * s, cy + 28 * s)], fill=fill)
    draw.polygon([(cx, cy - 35 * s), (cx + 98 * s, cy - 88 * s), (cx + 205 * s, cy - 35 * s), (cx + 120 * s, cy - 12 * s), (cx + 190 * s, cy + 42 * s), (cx + 72 * s, cy + 28 * s)], fill=fill)
    draw.ellipse([cx - 44 * s, cy - 55 * s, cx + 44 * s, cy + 80 * s], fill=fill)
    draw.ellipse([cx - 24 * s, cy - 96 * s, cx + 24 * s, cy - 52 * s], fill=fill)
    draw.polygon([(cx - 18 * s, cy + 55 * s), (cx - 65 * s, cy + 130 * s), (cx, cy + 105 * s), (cx + 65 * s, cy + 130 * s), (cx + 18 * s, cy + 55 * s)], fill=fill)
    shield(draw, cx, cy + 22 * s, 54 * s, 66 * s, accent)


def lion(draw, cx, cy, scale, fill, accent):
    s = scale
    draw.ellipse([cx - 95 * s, cy - 42 * s, cx + 42 * s, cy + 42 * s], fill=fill)
    draw.rectangle([cx - 58 * s, cy + 25 * s, cx + 60 * s, cy + 72 * s], fill=fill)
    draw.ellipse([cx + 36 * s, cy - 58 * s, cx + 98 * s, cy + 4 * s], fill=fill)
    for dx in [-45, -5, 35, 70]:
        draw.rectangle([cx + dx * s, cy + 55 * s, cx + (dx + 16) * s, cy + 125 * s], fill=fill)
    draw.arc([cx - 135 * s, cy - 110 * s, cx - 40 * s, cy + 10 * s], 190, 325, fill=fill, width=max(3, int(12 * s)))
    draw.ellipse([cx + 58 * s, cy - 30 * s, cx + 70 * s, cy - 18 * s], fill=accent)


def mountain(draw, cx, cy, w, h, fill, snow):
    x0, base = cx - w / 2, cy + h / 2
    p1 = [(x0, base), (x0 + w * 0.34, cy - h * 0.35), (x0 + w * 0.68, base)]
    p2 = [(x0 + w * 0.28, base), (x0 + w * 0.70, cy - h * 0.50), (x0 + w, base)]
    draw.polygon(p1, fill=fill)
    draw.polygon(p2, fill=fill)
    draw.polygon([(x0 + w * 0.34, cy - h * 0.35), (x0 + w * 0.26, cy - h * 0.05), (x0 + w * 0.42, cy - h * 0.08)], fill=snow)
    draw.polygon([(x0 + w * 0.70, cy - h * 0.50), (x0 + w * 0.60, cy - h * 0.10), (x0 + w * 0.80, cy - h * 0.12)], fill=snow)


def bird(draw, cx, cy, scale, fill, accent):
    s = scale
    draw.polygon([(cx, cy - 40 * s), (cx - 105 * s, cy + 25 * s), (cx - 20 * s, cy + 10 * s), (cx - 55 * s, cy + 82 * s), (cx, cy + 35 * s), (cx + 55 * s, cy + 82 * s), (cx + 20 * s, cy + 10 * s), (cx + 105 * s, cy + 25 * s)], fill=fill)
    draw.ellipse([cx - 20 * s, cy - 62 * s, cx + 20 * s, cy - 22 * s], fill=fill)
    draw.polygon([(cx + 18 * s, cy - 44 * s), (cx + 58 * s, cy - 34 * s), (cx + 18 * s, cy - 24 * s)], fill=accent)


def horse(draw, cx, cy, scale, fill, accent):
    s = scale
    draw.ellipse([cx - 95 * s, cy - 40 * s, cx + 45 * s, cy + 45 * s], fill=fill)
    draw.rectangle([cx - 55 * s, cy + 25 * s, cx + 55 * s, cy + 70 * s], fill=fill)
    draw.ellipse([cx + 35 * s, cy - 80 * s, cx + 95 * s, cy - 20 * s], fill=fill)
    for dx in [-45, -5, 35, 65]:
        draw.line([cx + dx * s, cy + 55 * s, cx + (dx - 20) * s, cy + 130 * s], fill=fill, width=max(4, int(13 * s)))
    draw.arc([cx - 135 * s, cy - 90 * s, cx - 50 * s, cy + 20 * s], 190, 330, fill=fill, width=max(4, int(10 * s)))
    draw.polygon([(cx + 65 * s, cy - 68 * s), (cx + 85 * s, cy - 115 * s), (cx + 95 * s, cy - 58 * s)], fill=accent)


def dragon(draw, cx, cy, scale, fill, accent):
    s = scale
    pts = [(cx - 150 * s, cy + 40 * s), (cx - 80 * s, cy - 55 * s), (cx + 25 * s, cy - 25 * s), (cx + 110 * s, cy - 70 * s), (cx + 150 * s, cy - 5 * s), (cx + 65 * s, cy + 28 * s), (cx - 20 * s, cy + 5 * s), (cx - 105 * s, cy + 90 * s)]
    draw.line(pts, fill=fill, width=max(6, int(28 * s)), joint="curve")
    draw.ellipse([cx + 120 * s, cy - 95 * s, cx + 175 * s, cy - 40 * s], fill=fill)
    draw.polygon([(cx + 172 * s, cy - 73 * s), (cx + 215 * s, cy - 62 * s), (cx + 172 * s, cy - 52 * s)], fill=accent)


def harp(draw, cx, cy, scale, fill, accent):
    s = scale
    draw.arc([cx - 65 * s, cy - 105 * s, cx + 80 * s, cy + 110 * s], 80, 280, fill=fill, width=max(4, int(14 * s)))
    draw.line([cx + 34 * s, cy - 78 * s, cx + 34 * s, cy + 88 * s], fill=fill, width=max(4, int(14 * s)))
    for i in range(7):
        x = cx - 42 * s + i * 12 * s
        draw.line([x, cy - 50 * s, cx + 30 * s, cy + 70 * s], fill=accent, width=max(1, int(3 * s)))


def center_text(draw, text, cx, cy, fill, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - (bbox[3] - bbox[1]) / 2), text, font=font, fill=fill)


def stripes_h(draw, colors, ratios=None):
    ratios = ratios or [1] * len(colors)
    total, y = sum(ratios), 0
    for c, r in zip(colors, ratios):
        height = H * r / total
        draw.rectangle([0, y, W, y + height + 1], fill=color(c))
        y += height


def stripes_v(draw, colors, ratios=None):
    ratios = ratios or [1] * len(colors)
    total, x = sum(ratios), 0
    for c, r in zip(colors, ratios):
        width = W * r / total
        draw.rectangle([x, 0, x + width + 1, H], fill=color(c))
        x += width


def diagonal(draw, fill, border=None, up=False, width=115):
    if up:
        pts = [(-120, H - width), (0, H - width), (W + 120, -width), (W + 120, width), (W, width), (-120, H + width)]
        pts_b = [(-150, H - width - 25), (0, H - width - 25), (W + 150, -width - 25), (W + 150, width + 25), (W, width + 25), (-150, H + width + 25)]
    else:
        pts = [(-120, -width), (0, -width), (W + 120, H - width), (W + 120, H + width), (W, H + width), (-120, width)]
        pts_b = [(-150, -width - 25), (0, -width - 25), (W + 150, H - width - 25), (W + 150, H + width + 25), (W, H + width + 25), (-150, width + 25)]
    if border:
        draw.polygon(pts_b, fill=color(border))
    draw.polygon(pts, fill=color(fill))


def draw_layout(draw, spec):
    c, layout, code = spec["colors"], spec["layout"], spec["code"]
    if layout == "h":
        stripes_h(draw, c)
    elif layout == "h_wide":
        stripes_h(draw, [c[0], c[1], c[0]], [1, 2, 1])
    elif layout == "v":
        stripes_v(draw, c[:3])
    elif layout == "field":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        if code == "OCEAN":
            for i in range(4):
                y = 120 + i * 105
                draw.arc([-80, y - 40, W + 80, y + 90], 180, 360, fill=color(c[1]), width=14)
    elif layout == "canton":
        stripes_h(draw, [c[1], c[1], c[2]])
        draw.rectangle([0, 0, 340, 300], fill=color(c[0]))
        diagonal(draw, c[3], c[1], up=True, width=30)
    elif layout == "canton_sun":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.rectangle([0, 0, 410, 300], fill=color(c[1]))
        diagonal(draw, c[3], c[1], up=True, width=25)
    elif layout == "british":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        for up in (False, True):
            diagonal(draw, c[1], None, up=up, width=50)
            diagonal(draw, c[2], None, up=up, width=24)
        draw.rectangle([0, 245, W, 355], fill=color(c[1]))
        draw.rectangle([445, 0, 555, H], fill=color(c[1]))
        draw.rectangle([0, 270, W, 330], fill=color(c[2]))
        draw.rectangle([470, 0, 530, H], fill=color(c[2]))
    elif layout in ("southern", "southern_gold"):
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        if layout == "southern":
            draw.rectangle([0, 0, 360, 230], fill=color(c[1]))
            draw.line([15, 15, 345, 215], fill=color(c[2]), width=34)
            draw.line([15, 215, 345, 15], fill=color(c[2]), width=34)
            draw.line([0, 115, 360, 115], fill=color(c[0]), width=34)
            draw.line([180, 0, 180, 230], fill=color(c[0]), width=34)
            star_fill = color(c[1])
        else:
            diagonal(draw, c[1], c[2], width=75)
            star_fill = color(c[1])
        for x, y, r in [(700, 155, 36), (805, 270, 31), (655, 395, 28), (865, 405, 29), (880, 145, 21)]:
            star(draw, x, y, r, star_fill, 7)
    elif layout == "chevron":
        stripes_h(draw, c[:3])
        draw.polygon([(0, 0), (425, 300), (0, H)], fill=color(c[1]))
        draw.polygon([(0, 60), (330, 300), (0, H - 60)], fill=color(c[0]))
    elif layout == "diamond":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.polygon([(500, 70), (870, 300), (500, 530), (130, 300)], fill=color(c[1]))
        draw.ellipse([365, 165, 635, 435], fill=color(c[2]))
    elif layout == "diag":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        diagonal(draw, c[1], c[3], up=True, width=85)
    elif layout == "stripes":
        stripes_h(draw, [c[0], c[1]] * 5)
        draw.rectangle([0, 0, 360, 320], fill=color(c[2]))
    elif layout == "tri":
        stripes_h(draw, [c[0], c[1], c[0]])
        draw.polygon([(0, 0), (405, 300), (0, H)], fill=color(c[2]))
    elif layout == "quarter":
        draw.rectangle([0, 0, 500, 300], fill=color(c[0]))
        draw.rectangle([500, 0, W, 300], fill=color(c[1]))
        draw.rectangle([0, 300, 500, H], fill=color(c[2]))
        draw.rectangle([500, 300, W, H], fill=color(c[0] if len(c) < 4 else c[3]))
    elif layout == "ensign":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.rectangle([0, 0, 360, 250], fill=color(c[1]))
        draw.line([0, 125, 360, 125], fill=color(c[2]), width=28)
        draw.line([180, 0, 180, 250], fill=color(c[2]), width=28)
    elif layout == "cross":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.rectangle([0, 245, W, 355], fill=color(c[2] if len(c) > 2 else c[1]))
        draw.rectangle([445, 0, 555, H], fill=color(c[2] if len(c) > 2 else c[1]))
        draw.rectangle([0, 275, W, 325], fill=color(c[1]))
        draw.rectangle([475, 0, 525, H], fill=color(c[1]))
    elif layout == "cross_stripes":
        stripes_h(draw, [c[0], c[1]] * 4 + [c[0]])
        draw.rectangle([0, 0, 360, 300], fill=color(c[0]))
        draw.rectangle([0, 125, 360, 175], fill=color(c[1]))
        draw.rectangle([155, 0, 205, 300], fill=color(c[1]))
    elif layout == "rays":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        for i in range(14):
            x0 = i * W / 14
            draw.polygon([(500, 300), (x0, 0), (x0 + W / 14, 0)], fill=color(c[1] if i % 2 == 0 else c[2]))
            draw.polygon([(500, 300), (x0, H), (x0 + W / 14, H)], fill=color(c[1] if i % 2 == 0 else c[2]))
    elif layout == "nordic":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.rectangle([250, 0, 330, H], fill=color(c[1]))
        draw.rectangle([0, 250, W, 330], fill=color(c[1]))
    elif layout == "nordic2":
        draw.rectangle([0, 0, W, H], fill=color(c[0]))
        draw.rectangle([235, 0, 355, H], fill=color(c[1]))
        draw.rectangle([0, 240, W, 360], fill=color(c[1]))
        draw.rectangle([270, 0, 320, H], fill=color(c[2]))
        draw.rectangle([0, 275, W, 325], fill=color(c[2]))
    elif layout == "triangle":
        stripes_h(draw, c[:2])
        draw.polygon([(0, 0), (430, 300), (0, H)], fill=color(c[2]))
    elif layout == "bicolor":
        stripes_h(draw, c[:2])
    else:
        stripes_h(draw, c[:3])


def draw_emblem(draw, spec):
    c, emblem, layout, mark = spec["colors"], spec["emblem"], spec["layout"], spec["mark"]
    cx, cy, scale = 500, 300, 1.0
    if layout in ("canton", "canton_sun"):
        cx, cy, scale = 175, 145, 0.75
    elif layout == "tri":
        cx, cy, scale = 145, 300, 0.85
    if emblem == "none" or emblem == "":
        return
    if emblem == "waves":
        return
    if emblem == "compass":
        sun(draw, cx, cy, 52 * scale, color(c[3]), 12, 26)
    elif emblem == "star":
        star(draw, cx, cy, 70 * scale, color(c[-1]), 5)
    elif emblem == "stars":
        for x, y in [(435, 300), (500, 265), (565, 300), (470, 345), (530, 345)]:
            star(draw, x, y, 26, color(c[-1]), 5)
    elif emblem == "sun":
        sun(draw, cx if emblem != "sun_offset" else 545, cy, 58 * scale, color(c[-1]), 16, 22)
    elif emblem == "sun_offset":
        sun(draw, 545, 300, 92, color(c[1]), 20, 34)
        draw.ellipse([445, 200, 645, 400], outline=color(c[2]), width=12)
    elif emblem == "crescent":
        crescent(draw, cx - 35 * scale, cy, 75 * scale, color(c[1]), color(c[0]))
        star(draw, cx + 80 * scale, cy, 38 * scale, color(c[1]), 5)
    elif emblem == "gear_star":
        gear(draw, 430, 300, 95, color(c[1]), color(c[0]))
        star(draw, 560, 300, 82, color(c[1]), 5)
        draw.line([180, 470, 820, 470], fill=color(c[2]), width=18)
    elif emblem == "roundel":
        shield(draw, cx, cy, 145 * scale, 170 * scale, color(c[-1]), color(c[2]))
        star(draw, cx, cy - 6 * scale, 38 * scale, color(c[1]), 6)
    elif emblem == "shield":
        shield(draw, cx, cy, 140 * scale, 170 * scale, color(c[-2]), color(c[-1]))
        crown(draw, cx, cy - 90 * scale, 82 * scale, 62 * scale, color(c[-1]), color(c[1]))
    elif emblem == "crown":
        crown(draw, cx, cy, 105 * scale, 78 * scale, color(c[-1]), color(c[1]))
    elif emblem == "eagle":
        eagle(draw, cx, cy + 10 * scale, 0.78 * scale, color(c[-1]), color(c[1]))
    elif emblem == "lion":
        lion(draw, cx, cy, 0.9 * scale, color(c[-1]), color(c[1]))
    elif emblem == "lion_sun":
        sun(draw, cx + 25, cy - 42, 45, color(c[-1]), 14, 18)
        lion(draw, cx - 10, cy + 45, 0.66, color(c[-1]), color(c[1]))
    elif emblem == "mountain":
        mountain(draw, cx, cy + 25 * scale, 240 * scale, 170 * scale, color(c[-2]), color(c[1]))
    elif emblem == "bird":
        bird(draw, cx, cy, 1.0 * scale, color(c[-1]), color(c[1]))
    elif emblem == "swords":
        draw.line([cx - 90, cy - 120, cx + 90, cy + 120], fill=color(c[-1]), width=18)
        draw.line([cx + 90, cy - 120, cx - 90, cy + 120], fill=color(c[-1]), width=18)
        crescent(draw, cx, cy, 50, color(c[-1]), color(c[1]))
    elif emblem == "palm":
        shield(draw, cx, cy, 150, 175, color(c[2]), color(c[3]))
        mountain(draw, cx, cy + 28, 115, 90, color(c[3]), color(c[2]))
        draw.line([cx, cy - 80, cx, cy + 40], fill=color(c[3]), width=12)
    elif emblem == "ring":
        for i in range(13):
            angle = 2 * math.pi * i / 13
            star(draw, 180 + math.cos(angle) * 95, 155 + math.sin(angle) * 76, 13, color(c[1]), 5)
        diagonal(draw, c[-1], c[1], up=True, width=22)
    elif emblem == "dragon":
        dragon(draw, cx, cy, 0.95 * scale, color(c[-2]), color(c[-1]))
    elif emblem == "checker":
        shield(draw, cx, cy, 160, 180, color(c[1]), color(c[-1]))
        x0, y0, sq = cx - 60, cy - 60, 30
        for yy in range(4):
            for xx in range(4):
                if (xx + yy) % 2 == 0:
                    draw.rectangle([x0 + xx * sq, y0 + yy * sq, x0 + (xx + 1) * sq, y0 + (yy + 1) * sq], fill=color(c[0]))
    elif emblem == "leaf":
        star(draw, cx, cy, 92, color(c[2]), 8)
        draw.polygon([(cx, cy - 140), (cx + 35, cy - 50), (cx + 125, cy - 60), (cx + 55, cy + 10), (cx + 90, cy + 120), (cx, cy + 55), (cx - 90, cy + 120), (cx - 55, cy + 10), (cx - 125, cy - 60), (cx - 35, cy - 50)], fill=color(c[0]))
    elif emblem == "harp":
        harp(draw, cx, cy, 1.0, color(c[-1]), color(c[1]))
    elif emblem == "horse":
        horse(draw, cx, cy, 0.78, color(c[-1]), color(c[1]))
    elif emblem == "spear":
        draw.line([250, 390, 760, 210], fill=color(c[-1]), width=18)
        star(draw, cx, cy, 58, color(c[-1]), 8)
    elif emblem == "trident":
        crown(draw, cx, cy - 92, 95, 70, color(c[-1]), color(c[1]))
        draw.line([cx, cy - 45, cx, cy + 105], fill=color(c[-1]), width=18)
        draw.arc([cx - 70, cy - 20, cx, cy + 105], 250, 60, fill=color(c[-1]), width=15)
        draw.arc([cx, cy - 20, cx + 70, cy + 105], 120, 290, fill=color(c[-1]), width=15)
    elif emblem.startswith("text:"):
        text = emblem.split(":", 1)[1]
        center_text(draw, text, cx, cy, color(c[-1]), FONT_BIG if len(text) <= 1 else FONT_MED)


def finish(draw, colors, code):
    draw.rectangle([0, 0, 18, H], fill=color(colors[-1]))
    draw.rectangle([18, 0, 24, H], fill=color(colors[0]))
    if code != "OCEAN":
        draw.rectangle([0, 0, W - 1, H - 1], outline=(17, 17, 17), width=2)


def main():
    specs = parse_specs()
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()

    with TSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    if len(rows) != len(specs):
        raise RuntimeError(f"row count mismatch: {len(rows)} rows vs {len(specs)} specs")

    records = []
    for row, spec in zip(rows, specs):
        im = Image.new("RGB", (W, H), color(spec["colors"][0]))
        draw = ImageDraw.Draw(im)
        draw_layout(draw, spec)
        draw_emblem(draw, spec)
        finish(draw, spec["colors"], spec["code"])
        idx = int(row["id"])
        out_name = f"{idx:03d}_{safe_filename(row['name'])}_{spec['code']}_original.png"
        out_path = OUT / out_name
        im.save(out_path, "PNG", optimize=True)
        records.append(
            {
                "id": str(idx),
                "name": row["name"],
                "design_code": spec["code"],
                "layout": spec["layout"],
                "palette": ",".join(spec["colors"]),
                "output_png": str(out_path),
                "design_note": NOTES.get(spec["code"], "WWI-era inspired original flat flag variant; not copied from the reference mod or a real flag."),
            }
        )

    mapping = OUT / "mapping.tsv"
    with mapping.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()), delimiter="\t")
        writer.writeheader()
        writer.writerows(records)

    thumb_w, thumb_h, cols, label_h = 160, 96, 10, 22
    sheet = Image.new("RGB", (cols * thumb_w, ((len(records) + cols - 1) // cols) * (thumb_h + label_h)), (244, 244, 244))
    draw = ImageDraw.Draw(sheet)
    for i, rec in enumerate(records):
        with Image.open(rec["output_png"]) as im:
            thumb = im.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = (i % cols) * thumb_w
        y = (i // cols) * (thumb_h + label_h)
        sheet.paste(thumb, (x, y))
        draw.text((x + 4, y + thumb_h + 4), f"{int(rec['id']):03d} {rec['design_code']}", fill=(20, 20, 20))
    contact = OUT / "contact_sheet.png"
    sheet.save(contact, "PNG", optimize=True)

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(OUT.iterdir()):
            if p.is_file():
                archive.write(p, arcname=p.name)

    bad = []
    for rec in records:
        with Image.open(rec["output_png"]) as im:
            if im.size != (W, H):
                bad.append((rec["id"], im.size))
    print(f"generated={len(records)}")
    print(f"folder={OUT}")
    print(f"zip={ZIP}")
    print(f"mapping={mapping}")
    print(f"contact={contact}")
    print(f"bad={bad}")


if __name__ == "__main__":
    main()
