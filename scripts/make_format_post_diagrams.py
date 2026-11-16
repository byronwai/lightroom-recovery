r"""Diagrams for the "Three files and a photo" post, as SVG + PNG.

Writes docs/assets/formats-*.svg + .png (Chrome/Edge headless):
  formats-ifd-entry       the 12-byte TIFF IFD entry
  formats-xmp-envelopes   one XMP payload, four envelopes
  formats-acr-presence    when the export writes an .acr
  formats-mask-binding    XMP MaskDigest -> ACR record -> placed raster
  formats-lifecycle       cache -> export -> trio -> re-import

Run:  python scripts/make_format_post_diagrams.py --acr <dir>/DSC03049.acr
      the binding diagram is read from that .acr and its sibling .xmp
      (needs tifffile + imagecodecs)
"""
import os, sys, io, struct, base64, subprocess, tempfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "assets")
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY, RED = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899", "#ff7b72"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

class Svg:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
                  f'viewBox="0 0 {w} {h}" font-family="{SANS}">',
                  f'<rect width="{w}" height="{h}" fill="{BG}"/>',
                  '<defs>' + "".join(
                      f'<marker id="a{n}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
                      f'markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{c}"/></marker>'
                      for n, c in (("t", TXT), ("o", ORANGE), ("g", GREEN), ("p", PURPLE), ("d", DIM), ("b", BLUE)))
                  + '</defs>']

    def box(self, x, y, w, h, border, fill=PANEL, rx=12, dash="", sw=2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                      f'stroke="{border}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
        self.s.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-family="{font}" '
                      f'font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, color=TXT, marker="t", dash="", sw=2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        m = f' marker-end="url(#a{marker})"' if marker else ""
        self.s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{sw}"{d}{m}/>')

    def path(self, d, color=TXT, marker="t", dash="", sw=2):
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.s.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{dd} marker-end="url(#a{marker})"/>')

    def raw(self, s): self.s.append(s)

    def save(self, name):
        self.s.append("</svg>")
        svg = os.path.join(OUT, name + ".svg")
        open(svg, "w", encoding="utf-8").write("\n".join(self.s))
        with tempfile.TemporaryDirectory() as td:
            shot = os.path.join(td, "shot.png")
            subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", f"--screenshot={shot}",
                            f"--window-size={self.w},{self.h}", "--force-device-scale-factor=1",
                            "--default-background-color=00000000", "file:///" + svg.replace("\\", "/")],
                           check=True, capture_output=True, timeout=120)
            shutil.copy(shot, os.path.join(OUT, name + ".png"))
        print("written:", os.path.join(OUT, name + ".png"))

def title(g, t, sub):
    g.text(40, 50, t, 26, TXT, SANS, "bold")
    g.text(40, 80, sub, 14.5, DIM)

# ---------------------------------------------------------------- IFD entry
def ifd_entry():
    g = Svg(1240, 520)
    title(g, "A TIFF directory entry: 12 bytes", "every IFD is a count followed by these; the last field is the whole pointer-chase trick")
    X0, Y, CW, CH = 150, 150, 78, 70
    fields = [(0, 2, "tag", "what this is", "0x0100 = width", BLUE),
              (2, 4, "type", "byte, short, long…", "3 = SHORT", PURPLE),
              (4, 8, "count", "how many values", "1", GREEN),
              (8, 12, "value / offset", "the value, if it fits", "else: where it is", ORANGE)]
    for a, b, name, d1, d2, col in fields:
        x, w = X0 + a * CW, (b - a) * CW
        g.box(x, Y, w, CH, col, fill="#1b2230" if col != ORANGE else "#2a1d10", rx=6, sw=2.5 if col == ORANGE else 2)
        g.text(x + w / 2, Y + 43, name, 18, col, MONO, "bold", "middle")
        g.text(x + w / 2, Y + 104, d1, 14, TXT, SANS, "normal", "middle")
        g.text(x + w / 2, Y + 126, d2, 13, DIM, MONO, "normal", "middle")
        g.text(x + 4, Y - 12, f"+{a}", 13, DIM, MONO)
    for i in range(13):
        g.line(X0 + i * CW, Y + CH, X0 + i * CW, Y + CH + 8, EDGE_, None)
    vx = X0 + 8 * CW + 2 * CW
    g.line(vx - 60, Y + 140, 330, 360, ORANGE, "o")
    g.line(vx + 60, Y + 140, 900, 360, ORANGE, "o")
    g.box(130, 364, 400, 110, ORANGE, dash="6 4", sw=1.6)
    g.text(150, 398, "fits in 4 bytes: stored inline", 16, ORANGE, SANS, "bold")
    g.text(150, 426, "ImageWidth = 7168 → done, no jump", 14, TXT, MONO)
    g.text(150, 452, "(SHORT, LONG, a few bytes of ASCII)", 13, DIM)
    g.box(700, 364, 460, 110, ORANGE, dash="6 4", sw=1.6)
    g.text(720, 398, "bigger: the field is an offset", 16, ORANGE, SANS, "bold")
    g.text(720, 426, "StripOffsets → jump to 0x3D0000", 14, TXT, MONO)
    g.text(720, 452, "a sub-IFD, a JPEG, the sensor strip…", 13, DIM)
    g.save("formats-ifd-entry")

# ---------------------------------------------------------------- envelopes
def envelopes():
    g = Svg(1300, 600)
    title(g, "One XMP payload, four envelopes", "same develop settings, boxed differently depending on where they live")
    rows = [("settings\\ store", "cache, sha256-named", 130),
            ("auxiliary\\ store", "cache, a few copies", 240),
            ("export sidecar", "Lightroom export", 370),
            ("recovery output", "pipeline-written", 480)]
    for name, sub, y in rows:
        g.text(40, y + 30, name, 17, TXT, MONO, "bold")
        g.text(40, y + 54, sub, 13.5, DIM)
    def payload(x, y, w=330):
        g.box(x, y, w, 56, ORANGE, fill="#2a1d10", rx=8)
        g.text(x + w / 2, y + 34, "<x:xmpmeta> … crs:* sliders, masks", 15, ORANGE, MONO, "bold", "middle")
    payload(300, 130)
    g.text(660, 164, "bare: starts directly at <x:xmpmeta", 14, DIM)
    # auxiliary: length + zlib( frame + payload )
    g.box(300, 228, 110, 80, BLUE, rx=8)
    g.text(355, 262, "u32", 15, BLUE, MONO, "bold", "middle")
    g.text(355, 284, "length", 13, DIM, SANS, "normal", "middle")
    g.box(420, 220, 540, 96, PURPLE, fill="#171021", rx=10, dash="7 4")
    g.text(436, 240, "zlib (78 9c …)", 13, PURPLE, MONO, "bold")
    g.box(436, 250, 100, 56, GRAY, rx=6)
    g.text(486, 284, "12-B frame", 13, TXT, MONO, "normal", "middle")
    payload(548, 250, 400)
    g.text(980, 268, "double-boxed", 14, DIM)
    payload(300, 370)
    g.text(660, 404, "bare again: what Adobe's own export writes", 14, DIM)
    g.box(300, 480, 170, 56, GRAY, rx=8)
    g.text(385, 514, "<?xpacket ?>", 15, TXT, MONO, "normal", "middle")
    payload(480, 480)
    g.box(820, 480, 190, 56, GRAY, rx=8)
    g.text(915, 514, "<?xpacket end?>", 15, TXT, MONO, "normal", "middle")
    g.text(1030, 514, "wrapped, for", 14, DIM)
    g.text(1030, 534, "other XMP readers", 14, DIM)
    g.save("formats-xmp-envelopes")

# ---------------------------------------------------------------- presence
def presence():
    g = Svg(1240, 460)
    title(g, "When does the export write an .acr?", "84 export sidecars checked; the rule held for every one")
    g.box(40, 200, 220, 90, GRAY)
    g.text(150, 238, "export", 17, TXT, SANS, "bold", "middle")
    g.text(150, 264, "84 sidecars", 15, DIM, MONO, "normal", "middle")
    cx, cy = 470, 245
    g.raw(f'<polygon points="{cx},{cy-100} {cx+170},{cy} {cx},{cy+100} {cx-170},{cy}" fill="{PANEL}" stroke="{ORANGE}" stroke-width="2.5"/>')
    g.text(cx, cy - 8, "XMP has an", 16, TXT, SANS, "bold", "middle")
    g.text(cx, cy + 16, "AI mask?", 16, TXT, SANS, "bold", "middle")
    g.text(cx, cy + 42, 'crs:What="Mask/Image"', 12.5, DIM, MONO, "normal", "middle")
    g.line(260, 245, cx - 174, 245, DIM, "d")
    g.box(800, 120, 400, 110, GREEN, fill="#0e1a10", sw=3)
    g.text(820, 156, "ARW + XMP + ACR", 18, GREEN, MONO, "bold")
    g.text(820, 184, "77 of 77", 15, TXT)
    g.text(820, 208, "Remove and Generative Remove patches ride along (3 files)", 13.5, DIM)
    g.box(800, 270, 400, 110, GRAY)
    g.text(820, 306, "ARW + XMP", 18, TXT, MONO, "bold")
    g.text(820, 334, "7 of 7", 15, TXT)
    g.text(820, 358, "no AI mask, no raster, no ACR", 13.5, DIM)
    g.line(cx + 170, cy, 720, cy, DIM, None)
    g.path(f"M 720 {cy} L 720 175 L 796 175", GREEN, "g")
    g.text(734, 205, "yes", 15, GREEN, SANS, "bold")
    g.path(f"M 720 {cy} L 720 325 L 796 325", DIM, "d")
    g.text(734, 300, "no", 15, DIM, SANS, "bold")
    g.text(40, 430, "Gradient, radial, brush and range masks are stored as parameters and never produce a raster.", 14, DIM)
    g.save("formats-acr-presence")

# ---------------------------------------------------------------- binding
def binding(acr, mask_name="Sky"):
    """XMP MaskDigest -> ACR table entry -> record -> raster placed at Origin, read from real files."""
    import re, numpy as np, tifffile
    from PIL import Image
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from acr_reader import read_table, classify
    xmp = open(os.path.splitext(acr)[0] + ".xmp", "rb").read().decode("utf-8", "replace")
    el = next(e.group(0) for e in re.finditer(r'<[^<>]*crs:What="Mask/Image"[^<>]*>', xmp)
              if re.search(r'crs:MaskName="%s' % mask_name, e.group(0)))
    at = dict(re.findall(r'crs:(\w+)="([^"]*)"', el))
    md5 = at["MaskDigest"].upper()
    data = open(acr, "rb").read()
    entries = read_table(data)[3]
    idx = next(i for i, e in enumerate(entries) if e[0] == md5)
    _, size, off = entries[idx]
    _, tif, _ = classify(data[off:off + size])
    arr = tifffile.imread(io.BytesIO(tif))
    rh_, rw_ = arr.shape[:2]
    im = Image.fromarray(np.asarray(arr, dtype=np.uint8)); im.thumbnail((400, 400))
    buf = io.BytesIO(); im.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    ox, oy = map(int, at["Origin"].split(","))
    fw, fh = map(int, at["FullMaskSize"].split(","))
    name = os.path.basename(os.path.splitext(acr)[0])
    short = f"{md5[:16]}…{md5[-4:]}"

    g = Svg(1440, 600)
    title(g, "How a raster finds its mask: by MD5",
          f"{name} record {idx} (a {mask_name} mask), followed from the XMP into the .acr and back onto the canvas")
    g.box(40, 120, 420, 300, PURPLE)
    g.text(60, 152, "XMP  (the decisions)", 15, PURPLE, SANS, "bold")
    lines = [('<rdf:li crs:What="Mask/Image"', TXT), (f'  crs:MaskName="{at.get("MaskName", "")}"', DIM),
             (f'  crs:MaskSubType="{at.get("MaskSubType", "")}"', DIM),
             ('  crs:MaskDigest=', ORANGE), (f'    "{short}"', ORANGE),
             (f'  crs:FullMaskSize="{at["FullMaskSize"]}"', BLUE), (f'  crs:Origin="{at["Origin"]}" />', BLUE)]
    for i, (s, c) in enumerate(lines):
        g.text(60, 190 + i * 30, s, 14.5, c, MONO, "bold" if c != DIM else "normal")
    g.box(540, 120, 400, 140, ORANGE)
    g.text(560, 152, f"ACR record table, entry {idx}", 15, ORANGE, SANS, "bold")
    g.text(560, 186, f"md5    {short}", 14.5, ORANGE, MONO, "bold")
    g.text(560, 214, f"size   {size:,}", 14.5, TXT, MONO)
    g.text(560, 242, f"offset 0x{off:X}", 14.5, TXT, MONO)
    g.box(540, 290, 400, 130, GREEN)
    g.text(560, 322, f"record {idx} @ 0x{off:X}", 15, GREEN, SANS, "bold")
    g.text(560, 354, "02 00 00 00 01 00 00 00 00×8", 14, TXT, MONO)
    g.text(560, 382, f"TIFF {rw_}x{rh_}, 1 ch, JPEG-XL", 14, TXT, MONO)
    g.text(560, 406, "md5(signature + TIFF) = entry md5", 13, DIM)
    g.line(462, 296, 536, 186, ORANGE, "o")
    g.text(500, 296, "same", 13, ORANGE, SANS, "bold", "middle")
    g.text(500, 314, "value", 13, ORANGE, SANS, "bold", "middle")
    g.line(740, 260, 740, 286, TXT, "t")
    CX, CY, S = 1020, 150, 1 / 8.0
    g.text(CX, 140, f"FullMaskSize canvas {fw}x{fh} (1/8 scale, sensor orientation)", 13, BLUE)
    g.box(CX, CY, fw * S, fh * S, BLUE, fill="#0b1520", rx=2, dash="5 4", sw=1.5)
    rx, ry, rw, rh = CX + ox * S, CY + oy * S, rw_ * S, rh_ * S
    g.raw(f'<image x="{rx}" y="{ry}" width="{rw}" height="{rh}" preserveAspectRatio="none" href="data:image/png;base64,{b64}"/>')
    g.box(rx, ry, rw, rh, GREEN, fill="none", rx=0, sw=2)
    g.text(CX, CY + fh * S + 22, f"raster {rw_}x{rh_} at Origin ({ox}, {oy})", 13, GREEN, MONO)
    g.line(944, 355, rx + 30, CY + 150, GREEN, "g")
    g.text(40, 470, "Every one of the 311 records in 77 files matched an XMP reference, and every reference matched a record.", 14.5, TXT)
    g.text(40, 498, "The table is sorted by MD5, not by XMP order (77 of 77 files), so position means nothing; the MD5 is the link.", 14.5, DIM)
    g.text(40, 526, "The local cache stores the same record as auxiliary\\<md5>, byte for byte.", 14.5, DIM)
    g.save("formats-mask-binding")

# ---------------------------------------------------------------- lifecycle
def lifecycle():
    g = Svg(1440, 540)
    title(g, "From cache to export to re-import", "what lives where, and what the .acr changes when the edit comes back")
    g.box(40, 120, 380, 330, EDGE_)
    g.text(60, 152, "LrCC local cache", 15, DIM, SANS, "bold")
    g.box(60, 172, 340, 110, ORANGE)
    g.text(80, 206, "settings\\<sha256>", 16, ORANGE, MONO, "bold")
    g.text(80, 234, "bare develop XMPs", 14, TXT)
    g.text(80, 258, "named by sha256 of the content", 13, DIM)
    g.box(60, 310, 340, 120, PURPLE)
    g.text(80, 344, "auxiliary\\<md5>", 16, PURPLE, MONO, "bold")
    g.text(80, 372, "AI-mask rasters, Remove patches", 14, TXT)
    g.text(80, 396, "one record per file, named by", 13, DIM)
    g.text(80, 416, "md5 = the XMP's MaskDigest", 13, DIM)
    g.box(500, 230, 200, 100, GRAY)
    g.text(600, 270, "export", 17, TXT, SANS, "bold", "middle")
    g.text(600, 296, "original + settings", 13.5, DIM, SANS, "normal", "middle")
    g.line(400, 227, 496, 262, ORANGE, "o")
    g.line(400, 370, 496, 300, PURPLE, "p")
    g.text(474, 410, "packed into", 13, PURPLE, SANS, "normal", "middle")
    g.text(474, 428, "the .acr table", 13, PURPLE, SANS, "normal", "middle")
    g.box(780, 190, 300, 180, GREEN, fill="#0e1a10", sw=3)
    g.text(800, 226, "trio on disk", 16, GREEN, SANS, "bold")
    g.text(800, 260, "DSCxxxxx.ARW", 15, TXT, MONO)
    g.text(800, 288, "DSCxxxxx.xmp  (bare)", 15, TXT, MONO)
    g.text(800, 316, "DSCxxxxx.acr  (if AI masks)", 15, GREEN, MONO, "bold")
    g.text(800, 348, "same folder, same base name", 13, DIM)
    g.line(700, 280, 776, 280, TXT, "t")
    g.box(1160, 150, 240, 100, GREEN)
    g.text(1180, 184, "with the .acr", 15, GREEN, SANS, "bold")
    g.text(1180, 212, "masks restored exactly", 14, TXT)
    g.text(1180, 234, "from the stored rasters", 13, DIM)
    g.box(1160, 310, 240, 120, GRAY)
    g.text(1180, 344, "without it", 15, TXT, SANS, "bold")
    g.text(1180, 372, "masks recomputed", 14, TXT)
    g.text(1180, 396, "AI models re-run on the XMP", 13, DIM)
    g.text(1180, 416, "close, not always identical", 13, DIM)
    g.line(1080, 250, 1156, 205, GREEN, "g")
    g.line(1080, 310, 1156, 360, DIM, "d")
    g.text(1240, 290, "re-import", 14, DIM, SANS, "bold", "middle")
    g.save("formats-lifecycle")

if __name__ == "__main__":
    acr = sys.argv[sys.argv.index("--acr") + 1]
    ifd_entry(); envelopes(); presence(); binding(acr); lifecycle()
