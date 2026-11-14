r"""Anatomy of a .acr file — byte-map block diagram (SVG + PNG).

All offsets/sizes are real, from DSC02091.acr (215,820 bytes, 4 records);
the layout was confirmed on 76 exported files.
Writes docs/assets/acr-structure.svg + .png (Chrome/Edge headless).
Run:  python scripts/make_acr_structure_image.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1320, 1180
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY, RED = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899", "#ff7b72"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="{SANS}">',
     f'<rect width="{W}" height="{H}" fill="{BG}"/>']

def box(x, y, w, h, border, fill=PANEL, rx=10, dash="", sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
             f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=14, fill=TXT, font=SANS, weight="normal", anchor="start"):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
             f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

text(40, 50, "Anatomy of a .acr file — the mask-raster container", 28, TXT, SANS, "bold")
text(40, 80, "DSC02091.acr · 215,820 bytes · 4 records · every offset real · layout confirmed on 76 files", 15, DIM, MONO)

# ================= left: linear map =================
LX, LW = 60, 470
box(LX - 14, 110, LW + 28, 1000, EDGE_)
text(LX, 138, "LINEAR MAP", 14, DIM, SANS, "bold")

# proportional mini-strip
SX, SW_, SY, SH = LX + LW + 6, 14, 160, 880
EOF_ = 0x34B0C
segs = [(0, 0x94, PURPLE, "hdr+table"), (0x94, 0xD76A, GREEN, "r0"),
        (0xD76C, 0x1AFD4, GREEN, "r1"), (0x1AFD4, 0x251C0, GREEN, "r2"),
        (0x251C0, EOF_, GREEN, "r3")]
for a, b, c, _ in segs:
    y0 = SY + SH * a / EOF_
    y1 = SY + SH * b / EOF_
    S.append(f'<rect x="{SX}" y="{y0:.1f}" width="{SW_}" height="{max(2, y1-y0):.1f}" fill="{c}"/>')
text(SX + 22, SY + 8, "to", 11, DIM)
text(SX + 22, SY + 22, "scale", 11, DIM)

y = 160
def block(label, sub, off, size, color, h=90):
    global y
    box(LX, y, LW, h, color)
    text(LX + 16, y + 28, label, 15.5, color, MONO, "bold")
    text(LX + 16, y + 52, sub, 12.5, DIM, MONO)
    text(LX + LW - 14, y + 28, f"@0x{off:X}", 13, PURPLE, MONO, "bold", "end")
    text(LX + LW - 14, y + 52, size, 12, DIM, MONO, "normal", "end")
    y += h + 14

block("header", "magic · version · fmt · N=4 · reserved", 0, "20 B", PURPLE, 64)
block("record table", "4 x 32 B: md5 | u64 size | u64 offset", 0x14, "128 B", ORANGE, 64)
block("record 0", "16 B sig + TIFF  1972x1920", 0x94, "54,998 B", GREEN, 78)
text(LX + 16, y - 2, "+ 2 B zero padding (records are 4-byte aligned)", 11.5, DIM, MONO); y += 12
block("record 1", "16 B sig + TIFF  2880x1920", 0xD76C, "55,400 B", GREEN, 78)
block("record 2", "16 B sig + TIFF  2117x1742", 0x1AFD4, "41,452 B", GREEN, 78)
block("record 3", "16 B sig + TIFF  1449x1743", 0x251C0, "63,820 B", GREEN, 78)
text(LX, y + 24, "EOF  0x34B0C", 13.5, DIM, MONO, "bold")
text(LX, y + 48, "first record at 20 + 32 x N (0x74 / 0x94 / 0xF4", 12.5, DIM)
text(LX, y + 68, "for 3 / 4 / 7 records) · each table md5 equals", 12.5, DIM)
text(LX, y + 88, "crs:MaskDigest or crs:pm_patch in the XMP", 12.5, DIM)

# ================= right top: header zoom =================
HX, HW = 640, 620
box(HX, 110, HW, 330, PURPLE)
text(HX + 20, 140, "HEADER + RECORD TABLE  (0x00–0x93)", 14, PURPLE, SANS, "bold")
hdr = [
    ("0x00", "4 B", 'magic "ACR\\0"', TXT),
    ("0x04", "4 B", "u32 version = 1", DIM),
    ("0x08", "4 B", 'source-format tag "ARW\\0"', TXT),
    ("0x0C", "4 B", "u32 N = 4 — record count", ORANGE),
    ("0x10", "4 B", "u32 0 — reserved", DIM),
    ("0x14", "32 B", "entry 0: md5[16] | u64 size | u64 offset = 0x94", BLUE),
    ("0x34", "32 B", "entry 1: md5 6D815A60… | 55,400 | 0xD76C", BLUE),
    ("0x54", "64 B", "entries 2–3 · md5 = md5(signature + TIFF)", BLUE),
]
yy = 166
for off, w_, desc, col in hdr:
    text(HX + 20, yy, off, 13.5, PURPLE, MONO, "bold")
    text(HX + 76, yy, w_, 12.5, DIM, MONO)
    text(HX + 128, yy, desc, 13, col)
    yy += 30

# ================= right middle: record zoom =================
box(HX, 470, HW, 400, GREEN)
text(HX + 20, 500, "RECORD ZOOM  (record 0 @ 0x94)", 14, GREEN, SANS, "bold")
text(HX + 20, 528, "+0x00  16 B signature:  02 00 00 00 01 00 00 00 00 00 00 00 00 00 00 00", 13, TXT, MONO)
text(HX + 20, 556, "+0x10  TIFF \u2014 same layout as the auxiliary\\ type-02 records", 13, TXT, MONO)

text(HX + 20, 588, "IFD0 (12 entries):", 13.5, GREEN, MONO, "bold")
ifd = [
    ("0x00FE NewSubfileType = 0", DIM),
    ("0x0100 ImageWidth = 1972   0x0101 ImageLength = 1920", DIM),
    ("0x0102 BitsPerSample = 8   0x0115 SamplesPerPixel = 1", DIM),
    ("0x0103 Compression = 52546 = JPEGXL_DNG", ORANGE),
    ("0x0106 Photometric = 1 (BlackIsZero) — a mask, not a picture", DIM),
    ("0x0142 TileWidth = 1972   0x0143 TileLength = 1920 (one tile)", DIM),
    ("0x0144 TileOffsets → JPEG-XL tile data   0x0145 TileByteCounts", TXT),
]
yy = 614
for line, col in ifd:
    text(HX + 36, yy, line, 12.5, col, MONO)
    yy += 26
text(HX + 20, yy + 6, "cropped to the mask (XMP Origin places it) · Remove patches: 3-ch 16-bit", 12, DIM)

# ================= right bottom: how to read =================
box(HX, 900, HW, 210, GRAY, dash="6 4", sw=1.6)
text(HX + 20, 930, "HOW TO WALK IT", 14, GRAY, SANS, "bold")
text(HX + 20, 958, "1. verify magic ACR\\0 · read N @0x0C", 13, DIM, MONO)
text(HX + 20, 986, "2. read N x 32-byte entries @0x14: md5, size, offset", 13, DIM, MONO)
text(HX + 20, 1014, "3. record = data[offset:offset+size]; md5 must match", 13, DIM, MONO)
text(HX + 20, 1042, "4. each TIFF is standalone — strip 16 bytes, save it", 13, DIM, MONO)
text(HX + 20, 1070, "5. decode tiles: pip install tifffile imagecodecs (JXL)", 13, DIM, MONO)
text(HX + 20, 1098, "automated: scripts/acr_reader.py <file.acr> --png", 13.5, TXT, MONO, "bold")

S.append("</svg>")
SVG = os.path.join(OUT, "acr-structure.svg")
with open(SVG, "w", encoding="utf-8") as f:
    f.write("\n".join(S))

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, "shot.png")
    subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}",
                    f"--screenshot={out}", f"--window-size={W},{H}",
                    "--force-device-scale-factor=1",
                    "--default-background-color=00000000",
                    "file:///" + SVG.replace("\\", "/")],
                   check=True, capture_output=True, timeout=120)
    import shutil; shutil.copy(out, os.path.join(OUT, "acr-structure.png"))
print("written:", SVG)
print("written:", os.path.join(OUT, "acr-structure.png"))
