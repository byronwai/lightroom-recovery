#!/usr/bin/env python3
"""Generate arw-structure.svg — byte-map block diagram of a Sony ARW file.

All offsets are real, parsed from DSC00001.ARW (38,268,928 bytes, LE TIFF):
header 0x0000, IFD0 0x0008 (20 entries), ExifIFD 0x11CC (45), MakerNotes
0x1472 (38,252 B), IFD1 0x0AABC, thumbnail JPEG 0x0ABCE (8,130 B),
SubIFD 0x21D22 (40 entries, StripOffsets -> 0x1EA000, 36,259,568 B),
embedded preview JPEG 0x300A2 (177,176 B), EOF 0x247F000.
"""
import os

W, H = 1240, 820

C = {  # palette (matches the repo's scoreboard chart)
    "ifd0":  "#2E9BD6", "exif": "#8E6FC8", "maker": "#7A8899",
    "ifd1":  "#7A8899", "thumb": "#F2A93B", "sub": "#E8555A",
    "jpeg":  "#F2A93B", "strip": "#5ABF8A", "text": "#1F2733", "dim": "#6B7686",
}
MONO = "Consolas, 'Cascadia Mono', Menlo, monospace"
SANS = "'Segoe UI', 'PingFang TC', 'Microsoft JhengHei', sans-serif"

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

svg = []
svg.append('<?xml version="1.0" encoding="UTF-8"?>')
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="{SANS}">')
# one arrowhead marker per colour (context-stroke is not portable across viewers)
svg.append('<defs>')
for key in ("ifd0", "exif", "maker", "ifd1", "sub", "jpeg", "strip"):
    svg.append(f'<marker id="arr-{key}" viewBox="0 0 10 10" refX="9" refY="5" '
               f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0,0 L10,5 L0,10 z" fill="{C[key]}"/></marker>')
svg.append('<filter id="sh" x="-8%" y="-8%" width="116%" height="120%">'
           '<feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#243B53" '
           'flood-opacity="0.14"/></filter></defs>')
svg.append(f'<rect width="{W}" height="{H}" fill="#FBFCFD"/>')
for gx in range(40, W, 40):
    svg.append(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{H}" stroke="#EDF1F5" stroke-width="1"/>')

# ---------- title ----------
svg.append(f'<text x="42" y="46" font-size="24" font-weight="700" fill="{C["text"]}">Sony ARW — a TIFF with the sensor data in a SubIFD</text>')
svg.append(f'<text x="42" y="68" font-size="13" fill="{C["dim"]}">DSC00001.ARW · 38,268,928 bytes (0x247F000) · little-endian TIFF</text>')
svg.append(f'<text x="512" y="68" font-size="13" fill="{C["dim"]}">every offset below is read from the real file</text>')
svg.append(f'<line x1="42" y1="84" x2="{W-42}" y2="84" stroke="#E3E9EF" stroke-width="1.5"/>')

# ---------- helpers ----------
def block(x, y, w, h, color, title, sub=None, big=False):
    svg.append('<g filter="url(#sh)">'
               f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{color}" '
               f'fill-opacity="0.10" stroke="{color}" stroke-opacity="0.35"/>'
               f'<rect x="{x}" y="{y}" width="5" height="{h}" rx="2.5" fill="{color}"/></g>')
    t = 17 if big else 14
    ty = y + h // 2 + (5 if not sub else -3)
    svg.append(f'<text x="{x+16}" y="{ty}" font-size="{t}" '
               f'font-weight="{700 if big else 600}" fill="{C["text"]}">{esc(title)}</text>')
    if sub:
        svg.append(f'<text x="{x+16}" y="{y + h//2 + 15}" font-size="11.5" fill="{C["dim"]}">{esc(sub)}</text>')

def off_label(x, y, txt):
    svg.append(f'<text x="{x}" y="{y}" font-size="11" font-family="{MONO}" '
               f'fill="{C["dim"]}" text-anchor="end">{txt}</text>')

# ---------- left column: the file, top to bottom ----------
LX, LW = 132, 300
OX = 124
blocks = {}

y = 108
off_label(OX, y + 22, "0x0000")
block(LX, y, LW, 40, C["ifd0"], "TIFF header", "49 49 2A 00 · II* + IFD0 ptr"); blocks["hdr"] = (y, 40); y += 48

off_label(OX, y + 22, "0x0008")
block(LX, y, LW, 50, C["ifd0"], "IFD0 — the directory", "20 entries · next-IFD → 0x0AABC"); blocks["ifd0"] = (y, 50); y += 58

off_label(OX, y + 22, "0x11CC")
block(LX, y, LW, 44, C["exif"], "ExifIFD", "45 standard Exif tags"); blocks["exif"] = (y, 44); y += 52

off_label(OX, y + 22, "0x1472")
block(LX, y, LW, 44, C["maker"], "Sony MakerNotes", "38,252 B of Sony-private tags"); blocks["maker"] = (y, 44); y += 52

off_label(OX, y + 22, "0x0AABC")
block(LX, y, LW, 40, C["ifd1"], "IFD1 — thumbnail directory", "14 entries"); blocks["ifd1"] = (y, 40); y += 48

off_label(OX, y + 20, "0x0ABCE")
block(LX, y, LW, 36, C["thumb"], "thumbnail JPEG", "8,130 B"); blocks["thumb"] = (y, 36); y += 44

off_label(OX, y + 28, "0x21D22")
block(LX, y, LW, 56, C["sub"], "SubIFD", "40 entries — holds THE PHOTO", True); blocks["sub"] = (y, 56); y += 64

off_label(OX, y + 22, "0x300A2")
block(LX, y, LW, 44, C["jpeg"], "embedded preview JPEG", "full-size, unedited · 177,176 B"); blocks["jpeg"] = (y, 44); y += 52

svg.append(f'<text x="{LX+LW//2}" y="{y+20}" font-size="12" fill="{C["dim"]}" '
           f'text-anchor="middle" font-family="{MONO}">⋮  — 38 MB of file, not to scale —  ⋮</text>')
y += 34

off_label(OX, y + 40, "0x1EA000")
block(LX, y, LW, 74, C["strip"], "RAW sensor strip",
      "36,259,568 B — 94.8% of the file · 7168×5120 · compression 7 (JPEG-coded)", True)
blocks["strip"] = (y, 74); y += 82

off_label(OX, y + 18, "0x247F000")
svg.append(f'<text x="{LX+16}" y="{y+18}" font-size="12" fill="{C["dim"]}" font-family="{MONO}">EOF</text>'); y += 30

svg.append(f'<text x="{LX}" y="{y+22}" font-size="11" fill="{C["dim"]}" font-weight="600">THE FILE — blocks ordered by byte offset</text>')

# ---------- right column: cards ----------
RX, RW = 560, 640

def card(x, y, w, h, color, title, rows):
    svg.append('<g filter="url(#sh)">'
               f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="white" '
               f'stroke="{color}" stroke-opacity="0.55"/>'
               f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="8" fill="{color}" fill-opacity="0.12"/>'
               f'<rect x="{x}" y="{y+18}" width="{w}" height="8" fill="white"/></g>')
    svg.append(f'<text x="{x+14}" y="{y+18}" font-size="13" font-weight="700" fill="{color}">{esc(title)}</text>')
    yy = y + 44
    row_ys = []
    for r in rows:
        svg.append(f'<text x="{x+14}" y="{yy}" font-size="12.5" fill="{C["text"]}" font-family="{MONO}">{esc(r)}</text>')
        row_ys.append(yy); yy += 21
    return row_ys

# rows ordered to match the vertical order of their destination blocks (top→down),
# so the arrow fan never crosses itself
r0 = card(RX, 108, RW, 152, C["ifd0"], "IFD0 — the 12-byte entries that point at everything", [
    "0x8769  ExifIFD                → 0x11CC",
    "next-IFD  (thumbnail chain)    → 0x0AABC",
    "0x0201  JPEGInterchangeFormat  → 0x300A2   (len 0x0202 = 177,176)",
    "0x014A  SubIFDs                → 0x21D22",
])

r1 = card(RX, 286, RW, 96, C["exif"], "ExifIFD — nested one level deeper", [
    "0x927C  MakerNotes  → 0x1472   (38,252 B, Sony-private)",
])

r2 = card(RX, 404, RW, 140, C["sub"], "SubIFD — where the actual photo lives", [
    "0x0111  StripOffsets          → 0x1EA000",
    "0x0117  StripByteCounts       = 36,259,568",
    "image 7168 × 5120 · compression = 7 (JPEG-coded)",
    "→ the RAW editors decode; previews are for humans",
])

ty = 578
svg.append(f'<g filter="url(#sh)"><rect x="{RX}" y="{ty}" width="{RW}" height="196" rx="8" fill="white" stroke="#D6DEE7"/></g>')
svg.append(f'<text x="{RX+14}" y="{ty+26}" font-size="13.5" font-weight="700" fill="{C["text"]}">Three things this picture says</text>')
tips = [
    ('A TIFF "chunk" is a 12-byte entry — [tag][type][count][value-or-pointer].',
     "Addressing is offset pointers and IFD chains, not a linear chunk stream like PNG."),
    ("The sensor data hides one IFD deeper than you expect.",
     "IFD0 is mostly metadata; StripOffsets inside the SubIFD is the 34.6 MB payload."),
    ("Every ARW ships a full-size unedited JPEG of itself at 0x0201.",
     "That embedded preview is what the recovery matcher correlates edited JPEGs against."),
]
yy = ty + 52
for bold, sub in tips:
    svg.append(f'<circle cx="{RX+20}" cy="{yy-4}" r="3.5" fill="#2E9BD6"/>')
    svg.append(f'<text x="{RX+32}" y="{yy}" font-size="12.5" font-weight="600" fill="{C["text"]}">{esc(bold)}</text>')
    svg.append(f'<text x="{RX+32}" y="{yy+17}" font-size="11.5" fill="{C["dim"]}">{esc(sub)}</text>')
    yy += 46

# ---------- arrows ----------
def arrow(x1, y1, name, key, dash=False, x2=LX + LW):
    y2 = blocks[name][0] + blocks[name][1] // 2
    mid = (x1 + x2) / 2
    d = "6 3" if dash else ""
    svg.append(f'<path d="M {x1-4} {y1-4} C {mid} {y1-4}, {mid} {y2}, {x2+10} {y2}" fill="none" '
               f'stroke="{C[key]}" stroke-width="1.8" stroke-dasharray="{d}" '
               f'marker-end="url(#arr-{key})" opacity="0.9"/>')

arrow(RX, r0[0], "exif",  "exif")
arrow(RX, r0[1], "ifd1",  "ifd1", dash=True)
arrow(RX, r0[2], "jpeg",  "jpeg")
arrow(RX, r0[3], "sub",   "sub")
arrow(RX, r1[0], "maker", "maker")
arrow(RX, r2[0], "strip", "strip")

svg.append(f'<text x="{RX}" y="{ty-10}" font-size="11" fill="{C["dim"]}">offsets in monospace are byte offsets into the file · arrow colour = destination block</text>')
svg.append("</svg>")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arw-structure.svg")
open(out, "w", encoding="utf-8").write("\n".join(svg))
print("svg written:", out)
