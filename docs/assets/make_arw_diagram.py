#!/usr/bin/env python3
"""Generate arw-structure.svg + .png — byte-map block diagram of a Sony ARW file.

Every offset is read from the file: IFD0 and its next-IFD chain (IFD1 with
the thumbnail, IFD2 with the full-size JPEG), ExifIFD and Sony MakerNotes,
the preview JPEG at IFD0's 0x0201, and the sensor strip in the SubIFD.

Run:  python docs/assets/make_arw_diagram.py [<file.ARW>] [--out <stem>]
      default file: DSC00001.ARW from the local Lightroom cache;
      default output: docs/assets/arw-structure.svg/.png
"""
import os, sys, glob, struct, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))

def measure(path):
    d = open(path, "rb").read()
    def ifd(off):
        n = struct.unpack("<H", d[off:off + 2])[0]
        t = {}
        for k in range(n):
            tag, typ, cnt, val = struct.unpack("<HHII", d[off + 2 + 12 * k: off + 14 + 12 * k])
            t[tag] = (typ, cnt, val)
        return n, t, struct.unpack("<I", d[off + 2 + 12 * n: off + 6 + 12 * n])[0]
    def jpeg_dims(off):
        j = d[off:off + 200000]
        for m in (b"\xff\xc0", b"\xff\xc1", b"\xff\xc2"):
            q = j.find(m)
            if q != -1:
                h, w = struct.unpack(">HH", j[q + 5:q + 9])
                return w, h
        return None, None
    n0, t0, ifd1 = ifd(8)
    ne, te, _ = ifd(t0[0x8769][2])
    n1, t1, ifd2 = ifd(ifd1)
    n2, t2, _ = ifd(ifd2)
    ns, ts, _ = ifd(t0[0x014A][2])
    fw, fh = jpeg_dims(t2[0x0201][2])
    return dict(
        name=os.path.basename(path), size=len(d),
        ifd0_n=n0, exif_off=t0[0x8769][2], exif_n=ne,
        maker_off=te[0x927C][2], maker_len=te[0x927C][1],
        ifd1_off=ifd1, ifd1_n=n1, thumb_off=t1[0x0201][2], thumb_len=t1[0x0202][2],
        ifd2_off=ifd2, ifd2_n=n2, full_off=t2[0x0201][2], full_len=t2[0x0202][2], full_w=fw, full_h=fh,
        sub_off=t0[0x014A][2], sub_n=ns, strip_off=ts[0x0111][2], strip_len=ts[0x0117][2],
        strip_w=ts[0x0100][2], strip_h=ts[0x0101][2], strip_comp=ts[0x0103][2],
        prev_off=t0[0x0201][2], prev_len=t0[0x0202][2])

def default_arw():
    root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Adobe", "Lightroom CC", "Data")
    hits = glob.glob(os.path.join(root, "*", "originals", "*", "*", "DSC00001.ARW"))
    if not hits:
        sys.exit("pass an ARW path (DSC00001.ARW not found in the Lightroom cache)")
    return hits[0]

args = [a for a in sys.argv[1:] if not a.startswith("--")]
V = measure(args[0] if args else default_arw())
OUT = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
       else os.path.join(HERE, "arw-structure"))
hx = lambda v: f"0x{v:X}"
mb = lambda v: f"{v / 1e6:.1f} MB"
JPG = " (JPEG-coded)" if V["strip_comp"] == 7 else ""

W, H = 1240, 940

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
svg.append(f'<text x="42" y="68" font-size="13" fill="{C["dim"]}">{V["name"]} · {V["size"]:,} bytes ({hx(V["size"])}) · little-endian TIFF</text>')
svg.append(f'<text x="560" y="68" font-size="13" fill="{C["dim"]}">every offset below is read from the real file</text>')
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
block(LX, y, LW, 50, C["ifd0"], "IFD0 — the directory", f'{V["ifd0_n"]} entries · next-IFD → {hx(V["ifd1_off"])}'); blocks["ifd0"] = (y, 50); y += 58

off_label(OX, y + 22, hx(V["exif_off"]))
block(LX, y, LW, 44, C["exif"], "ExifIFD", f'{V["exif_n"]} standard Exif tags'); blocks["exif"] = (y, 44); y += 52

off_label(OX, y + 22, hx(V["maker_off"]))
block(LX, y, LW, 44, C["maker"], "Sony MakerNotes", f'{V["maker_len"]:,} B of Sony-private tags'); blocks["maker"] = (y, 44); y += 52

off_label(OX, y + 22, hx(V["ifd1_off"]))
block(LX, y, LW, 40, C["ifd1"], "IFD1 — thumbnail directory", f'{V["ifd1_n"]} entries · next-IFD → {hx(V["ifd2_off"])}'); blocks["ifd1"] = (y, 40); y += 48

off_label(OX, y + 20, hx(V["thumb_off"]))
block(LX, y, LW, 36, C["thumb"], "thumbnail JPEG", f'{V["thumb_len"]:,} B'); blocks["thumb"] = (y, 36); y += 44

off_label(OX, y + 22, hx(V["ifd2_off"]))
block(LX, y, LW, 40, C["ifd1"], "IFD2 — full-size preview directory", f'{V["ifd2_n"]} entries'); blocks["ifd2"] = (y, 40); y += 48

off_label(OX, y + 28, hx(V["sub_off"]))
block(LX, y, LW, 56, C["sub"], "SubIFD", f'{V["sub_n"]} entries — holds THE PHOTO', True); blocks["sub"] = (y, 56); y += 64

off_label(OX, y + 22, hx(V["prev_off"]))
block(LX, y, LW, 44, C["jpeg"], "preview JPEG", f'{V["prev_len"]:,} B · what IFD0\'s 0x0201 points at'); blocks["jpeg"] = (y, 44); y += 52

off_label(OX, y + 22, hx(V["full_off"]))
block(LX, y, LW, 44, C["jpeg"], "full-size JPEG", f'{V["full_w"]}×{V["full_h"]}, unedited · {V["full_len"]:,} B'); blocks["full"] = (y, 44); y += 52

svg.append(f'<text x="{LX+LW//2}" y="{y+20}" font-size="12" fill="{C["dim"]}" '
           f'text-anchor="middle" font-family="{MONO}">⋮  — {mb(V["size"])} of file, not to scale —  ⋮</text>')
y += 34

share = V["strip_len"] / V["size"] * 100
off_label(OX, y + 40, hx(V["strip_off"]))
block(LX, y, LW, 84, C["strip"], "RAW sensor strip",
      f'{V["strip_len"]:,} B — {share:.1f}% of the file', True)
svg.append(f'<text x="{LX+16}" y="{y + 84//2 + 32}" font-size="11.5" fill="{C["dim"]}">'
           f'{V["strip_w"]}×{V["strip_h"]} · compression {V["strip_comp"]}{esc(JPG)}</text>')
blocks["strip"] = (y, 84); y += 92

off_label(OX, y + 18, hx(V["size"]))
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

# rows ordered to match the vertical order of their destination blocks (top→down)
r0 = card(RX, 108, RW, 152, C["ifd0"], "IFD0 — the 12-byte entries that point at everything", [
    f'0x8769  ExifIFD                → {hx(V["exif_off"])}',
    f'next-IFD  (thumbnail chain)    → {hx(V["ifd1_off"])}',
    f'0x0201  JPEGInterchangeFormat  → {hx(V["prev_off"])}   (len 0x0202 = {V["prev_len"]:,})',
    f'0x014A  SubIFDs                → {hx(V["sub_off"])}',
])

r1 = card(RX, 286, RW, 96, C["exif"], "ExifIFD — nested one level deeper", [
    f'0x927C  MakerNotes  → {hx(V["maker_off"])}   ({V["maker_len"]:,} B, Sony-private)',
])

rc = card(RX, 404, RW, 116, C["ifd1"], "IFD1 → IFD2 — the next-IFD chain", [
    f'IFD1  next-IFD                 → {hx(V["ifd2_off"])}  (IFD2)',
    f'IFD2  0x0201  JPEGInterchange  → {hx(V["full_off"])}  (len {V["full_len"]:,})',
    f'image {V["full_w"]} × {V["full_h"]} — the full frame, unedited',
])

r2 = card(RX, 544, RW, 140, C["sub"], "SubIFD — where the actual photo lives", [
    f'0x0111  StripOffsets          → {hx(V["strip_off"])}',
    f'0x0117  StripByteCounts       = {V["strip_len"]:,}',
    f'image {V["strip_w"]} × {V["strip_h"]} · compression = {V["strip_comp"]}{JPG}',
    "→ the RAW editors decode; previews are for humans",
])

ty = 712
svg.append(f'<g filter="url(#sh)"><rect x="{RX}" y="{ty}" width="{RW}" height="196" rx="8" fill="white" stroke="#D6DEE7"/></g>')
svg.append(f'<text x="{RX+14}" y="{ty+26}" font-size="13.5" font-weight="700" fill="{C["text"]}">Three things this picture says</text>')
tips = [
    ('A TIFF "chunk" is a 12-byte entry — [tag][type][count][value-or-pointer].',
     "Addressing is offset pointers and IFD chains, not a linear chunk stream like PNG."),
    ("The sensor data hides one IFD deeper than you expect.",
     f'IFD0 is mostly metadata; StripOffsets inside the SubIFD is the {mb(V["strip_len"])} payload.'),
    ("Every ARW ships a full-size unedited JPEG of itself, but not at IFD0's 0x0201.",
     f'IFD0 points at a {V["prev_len"] // 1000} KB preview; the {V["full_w"]}×{V["full_h"]} frame hangs off IFD2, two next-IFD hops on.'),
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
arrow(RX, rc[0], "ifd2",  "ifd1", dash=True)
arrow(RX, rc[1], "full",  "jpeg")
arrow(RX, r2[0], "strip", "strip")

svg.append(f'<text x="{RX}" y="{ty-10}" font-size="11" fill="{C["dim"]}">offsets in monospace are byte offsets into the file · arrow colour = destination block</text>')
svg.append("</svg>")

out = OUT + ".svg"
open(out, "w", encoding="utf-8").write("\n".join(svg))
print("svg written:", out)

BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
with tempfile.TemporaryDirectory() as td:
    shot = os.path.join(td, "shot.png")
    subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", f"--screenshot={shot}",
                    f"--window-size={W},{H}", "--force-device-scale-factor=1",
                    "file:///" + out.replace("\\", "/")], check=True, capture_output=True, timeout=120)
    shutil.copy(shot, OUT + ".png")
print("png written:", OUT + ".png")
