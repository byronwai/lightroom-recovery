r"""Anatomy of a .acr file — byte-map block diagram (SVG + PNG), read from a real file.

Left: the file top to bottom (header, record table, every record, padding).
Right: the header and table entries zoomed, the first raster record's TIFF
tags, and how to walk the format.

Run:  python scripts/make_acr_structure_image.py <file.acr> [--out <stem>]
      the docs' figure is made from DSC03049.acr; default output
      docs/assets/acr-structure.svg/.png (Chrome/Edge headless)
"""
import os, sys, struct, subprocess, tempfile, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acr_reader import read_table, classify, tiff_info  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY, RED = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899", "#ff7b72"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit("usage: make_acr_structure_image.py <file.acr> [--out <stem>]")
PATH = args[0]
OUT = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
       else os.path.join(ROOT, "docs", "assets", "acr-structure"))
data = open(PATH, "rb").read()
ver, fmt, reserved, entries = read_table(data)
N = len(entries)
recs = []
for md5, size, off in entries:
    kind, body, _ = classify(data[off:off + size])
    info = tiff_info(body) if kind == "raster" else None
    recs.append(dict(md5=md5, size=size, off=off, kind=kind, info=info, blen=len(body)))
name = os.path.basename(PATH)

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

ROW = 64 if N <= 5 else max(40, int(720 / N) - 8)
W = 1320
H = max(1180, 300 + 64 + 64 + N * (ROW + 8) + 160)
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{SANS}">',
     f'<rect width="{W}" height="{H}" fill="{BG}"/>']

def box(x, y, w, h, border, fill=PANEL, rx=10, dash="", sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=14, fill=TXT, font=SANS, weight="normal", anchor="start"):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-family="{font}" '
             f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

text(40, 50, "Anatomy of a .acr file — the mask-raster container", 28, TXT, SANS, "bold")
text(40, 80, f"{name} · {len(data):,} bytes · {N} records · every offset read from the file", 15, DIM, MONO)

# ---------------- left: linear map ----------------
LX, LW = 60, 470
box(LX - 14, 110, LW + 28, H - 150, EDGE_)
text(LX, 138, "LINEAR MAP", 14, DIM, SANS, "bold")
SX, SW_, SY, SH = LX + LW + 6, 14, 160, H - 330
first = 20 + 32 * N
colour = lambda r: ORANGE if r["kind"] != "raster" else (GREEN if r["info"][0x0115][1] == 1 else BLUE)
segs = [(0, first, PURPLE)] + [(r["off"], r["off"] + r["size"], colour(r)) for r in recs]
for a, b, c in segs:
    y0, y1 = SY + SH * a / len(data), SY + SH * b / len(data)
    S.append(f'<rect x="{SX}" y="{y0:.1f}" width="{SW_}" height="{max(1.5, y1 - y0):.1f}" fill="{c}"/>')
text(SX + 22, SY + 8, "to", 11, DIM)
text(SX + 22, SY + 22, "scale", 11, DIM)

y = 160
def block(label, sub, off, size, color, h):
    global y
    box(LX, y, LW, h, color)
    big = h >= 56
    text(LX + 16, y + (28 if big else h / 2 + 5), label, 15.5 if big else 14, color, MONO, "bold")
    if big:
        text(LX + 16, y + 52, sub, 12.5, DIM, MONO)
    else:
        text(LX + 130, y + h / 2 + 5, sub, 12, DIM, MONO)
    text(LX + LW - 14, y + (28 if big else h / 2 + 5), f"@0x{off:X}", 13, PURPLE, MONO, "bold", "end")
    if big:
        text(LX + LW - 14, y + 52, size, 12, DIM, MONO, "normal", "end")
    y += h + 8

block("header", f"magic · version · fmt · N={N} · reserved", 0, "20 B", PURPLE, 56)
block("record table", f"{N} x 32 B: md5 | u64 size | u64 offset", 0x14, f"{32 * N} B", ORANGE, 56)
prev = first
for i, r in enumerate(recs):
    if r["off"] > prev:
        text(LX + 16, y + 6, f"+ {r['off'] - prev} B zero padding", 11, DIM, MONO); y += 14
    if r["kind"] == "raster":
        t = r["info"]
        sub = f"{t[0x0100][1]}x{t[0x0101][1]} · {t[0x0115][1]}-ch {'mask' if t[0x0115][1] == 1 else 'RGB patch'}"
        col = GREEN if t[0x0115][1] == 1 else BLUE
    else:
        sub = f"zlib → {r['blen']:,} B XMP packet"
        col = ORANGE
    block(f"record {i}", sub, r["off"], f"{r['size']:,} B", col, ROW)
    prev = r["off"] + r["size"]
if len(data) > prev:
    text(LX + 16, y + 6, f"+ {len(data) - prev} B zero padding", 11, DIM, MONO); y += 14
text(LX, y + 22, f"EOF  0x{len(data):X}", 13.5, DIM, MONO, "bold")
text(LX, y + 46, f"first record at 20 + 32 x N = 0x{first:X} · green: 1-ch mask,", 12.5, DIM)
text(LX, y + 66, "blue: 3-ch RGB patch, orange: zlib XMP record", 12.5, DIM)

# ---------------- right top: header + table ----------------
HX, HW = 640, 620
box(HX, 110, HW, 360, PURPLE)
text(HX + 20, 140, f"HEADER + RECORD TABLE  (0x00–0x{first - 1:X})", 14, PURPLE, SANS, "bold")
rows = [("0x00", "4 B", 'magic "ACR\\0"', TXT),
        ("0x04", "4 B", f"u32 version = {ver}", DIM),
        ("0x08", "4 B", f'source-format tag "{fmt}\\0"', TXT),
        ("0x0C", "4 B", f"u32 N = {N} — record count", ORANGE),
        ("0x10", "4 B", f"u32 {reserved} — reserved", DIM)]
for i, r in enumerate(recs[:3]):
    rows.append((f"0x{0x14 + 32 * i:X}", "32 B", f"entry {i}: {r['md5'][:8]}… | {r['size']:,} | 0x{r['off']:X}", BLUE))
if N > 3:
    rows.append((f"0x{0x14 + 96:X}", f"{32 * (N - 3)} B", f"entries 3–{N - 1}", BLUE))
yy = 166
for off, w_, desc, col in rows:
    text(HX + 20, yy, off, 13.5, PURPLE, MONO, "bold")
    text(HX + 76, yy, w_, 12.5, DIM, MONO)
    text(HX + 136, yy, desc, 13, col, MONO if col == BLUE else SANS)
    yy += 30
text(HX + 20, yy + 4, "md5 = md5(signature + TIFF), or md5(inflated bytes) for a zlib record", 12.5, DIM)

# ---------------- right middle: record zoom ----------------
r0 = next((i for i, r in enumerate(recs) if r["kind"] == "raster" and r["info"][0x0115][1] == 1), 0)
r = recs[r0]
t = r["info"]
box(HX, 500, HW, 380, GREEN)
text(HX + 20, 530, f"RECORD ZOOM  (record {r0} @ 0x{r['off']:X})", 14, GREEN, SANS, "bold")
text(HX + 20, 558, "+0x00  16 B signature:  02 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00", 13, TXT, MONO)
text(HX + 20, 586, "+0x10  TIFF — same layout as the auxiliary\\ type-02 records", 13, TXT, MONO)
text(HX + 20, 618, f"IFD0 ({len(t)} entries):", 13.5, GREEN, MONO, "bold")
tiles = t[0x0144][0]
ifd = [(f"0x0100 ImageWidth = {t[0x0100][1]}   0x0101 ImageLength = {t[0x0101][1]}", DIM),
       (f"0x0102 BitsPerSample = {t[0x0102][1]}   0x0115 SamplesPerPixel = {t[0x0115][1]}", DIM),
       (f"0x0103 Compression = {t[0x0103][1]} = JPEGXL_DNG", ORANGE),
       ("0x0106 Photometric = 1 (BlackIsZero) — a mask, not a picture", DIM),
       (f"0x0142 TileWidth = {t[0x0142][1]}   0x0143 TileLength = {t[0x0143][1]}"
        + (" (one tile)" if tiles == 1 else f" ({tiles} tiles)"), DIM),
       ("0x0144 TileOffsets → JPEG-XL tile data   0x0145 TileByteCounts", TXT)]
yy = 644
for line, col in ifd:
    text(HX + 36, yy, line, 12.5, col, MONO)
    yy += 26
text(HX + 20, yy + 10, "cropped to the mask (XMP Origin places it) · Remove patches: 3-ch 16-bit", 12, DIM)

# ---------------- right bottom: how to read ----------------
box(HX, 910, HW, 230, GRAY, dash="6 4", sw=1.6)
text(HX + 20, 940, "HOW TO WALK IT", 14, GRAY, SANS, "bold")
steps = ["1. verify magic ACR\\0 · read N @0x0C",
         "2. read N x 32-byte entries @0x14: md5, size, offset",
         "3. record = data[offset:offset+size]",
         "4. 02 00 00 00 01 …: strip 16 bytes, it is a TIFF",
         "5. u32 len + 78 9c: inflate, it is an XMP packet",
         "6. decode tiles: pip install tifffile imagecodecs (JXL)"]
for i, st in enumerate(steps):
    text(HX + 20, 968 + i * 26, st, 13, DIM, MONO)
text(HX + 20, 968 + len(steps) * 26 + 4, "automated: scripts/acr_reader.py <file.acr> --png", 13.5, TXT, MONO, "bold")

S.append("</svg>")
open(OUT + ".svg", "w", encoding="utf-8").write("\n".join(S))
with tempfile.TemporaryDirectory() as td:
    shot = os.path.join(td, "shot.png")
    subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", f"--screenshot={shot}",
                    f"--window-size={W},{H}", "--force-device-scale-factor=1",
                    "--default-background-color=00000000", "file:///" + (OUT + ".svg").replace("\\", "/")],
                   check=True, capture_output=True, timeout=120)
    shutil.copy(shot, OUT + ".png")
print("written:", OUT + ".svg")
print("written:", OUT + ".png")
