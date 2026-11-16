r"""Render the internal structure of a Lightroom develop XMP file as PNG + SVG.

Every offset and value is measured from the XMP you pass; nothing is typed in.
Works for both a bare sidecar (starts at <x:xmpmeta, as Lightroom's export
and the settings\ store write it) and a packet-wrapped one (<?xpacket?>).

Output: docs/assets/xmp-structure.png / .svg
Run:    python scripts/make_xmp_structure_image.py <file.xmp>
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "assets")
os.makedirs(OUT, exist_ok=True)

BG     = "#0d1117"
NOTE   = "#8b949e"
HILITE = "#ffa657"
BAD    = "#ff7b72"
TITLE  = "#e6edf3"
XML    = "#7ee787"    # markup
ATTR   = "#79c0ff"    # attribute names
VAL    = "#e6edf3"    # values
OFF    = "#d2a8ff"    # byte offsets
DIM    = "#4d5761"

def off(n):   return [(f"{n:>6}  ", OFF)]
def gap():    return [("", NOTE)]

if len(sys.argv) < 2:
    sys.exit("usage: make_xmp_structure_image.py <file.xmp>")
PATH = sys.argv[1]
RAW = open(PATH, "rb").read()
X = RAW.decode("utf-8")
NAME = os.path.basename(PATH)
def at(s, start=0):
    i = X.find(s, start)
    return (len(X[:i].encode()) if i >= 0 else None), i
top = re.search(r"<rdf:Description\b[^>]*>", X, re.S).group(0)
attr = lambda k: (re.search(r'crs:%s="([^"]*)"' % k, top) or [None, "?"])[1]
n_crs = len(re.findall(r'\scrs:\w+="', top))
n_seq, n_desc = X.count("<rdf:Seq>"), X.count("<rdf:Description") - 1
groups = re.findall(r'crs:What="Correction"[^>]*?crs:CorrectionName="([^"]+)"|'
                    r'crs:CorrectionName="([^"]+)"[^>]*?crs:What="Correction"', X)
groups = [g[0] or g[1] for g in groups] or re.findall(r'crs:CorrectionName="([^"]+)"', X)
first_sync = (re.search(r'crs:CorrectionSyncID="([0-9A-F]+)"', X) or [None, ""])[1]
first_active = (re.search(r'crs:CorrectionActive="([^"]+)"', X) or [None, "?"])[1]
curve = re.search(r"<crs:ToneCurvePV2012>.*?</crs:ToneCurvePV2012>", X, re.S)
points = re.findall(r"<rdf:li>([^<]+)</rdf:li>", curve.group(0)) if curve else []
packet = X.lstrip().startswith("<?xpacket")

LINES = [[(f"Anatomy of a develop XMP sidecar — real file, real offsets ({NAME}, {len(RAW):,} B)", TITLE)], gap()]
if packet:
    LINES += [off(0) + [("<?xpacket ", XML), ("begin", ATTR), ("=", XML), ('"<BOM>"', VAL), (" ", XML), ("id", ATTR),
                        ("=", XML), ('"W5M0MpCehiHzreSzNTczkc9d"', VAL), ("?>", XML)],
              [("        ", NOTE), ("packet envelope — id is a fixed GUID; begin BOM allows UTF-8 detection", NOTE)]]
else:
    LINES += [[("        no <?xpacket?> envelope — a bare sidecar, exactly as Lightroom's export writes it", HILITE)]]
LINES += [
    off(at("<x:xmpmeta")[0]) + [("<x:xmpmeta ", XML), ("xmlns:x", ATTR), ("=", XML), ('"adobe:ns:meta/"', VAL), (" ", XML),
                                ("x:xmptk", ATTR), ("=", XML), ('"Adobe XMP Core 7.0-c000 …"', VAL), (">", XML)],
    [("        ", NOTE), ("wrapper + writing toolkit identity", NOTE)],
    off(at("<rdf:RDF")[0]) + [("<rdf:RDF ", XML), ("xmlns:rdf", ATTR), ("=", XML), ('"…/22-rdf-syntax-ns#"', VAL), (">", XML)],
    off(at("<rdf:Description")[0]) + [("<rdf:Description ", XML), ("rdf:about", ATTR), ("=", XML), ('""', VAL), (" ", XML),
                                      ("xmlns:crs", ATTR), ("=", XML), ('"…/camera-raw-settings/1.0/"', VAL), (">", XML)],
    [("        ", NOTE), ("one edit = one Description; crs = Camera Raw Settings namespace", NOTE)],
    gap(),
    [("        scalar attributes — the sliders (flat name=\"value\")", HILITE)],
    [("            crs:ProcessVersion", ATTR), ("=", XML), (f'"{attr("ProcessVersion")}"', VAL), ("   ", XML),
     ("crs:Version", ATTR), ("=", XML), (f'"{attr("Version")}"', VAL)],
    [("            crs:WhiteBalance", ATTR), ("=", XML), (f'"{attr("WhiteBalance")}"', VAL), ("  ", XML),
     ("crs:Temperature", ATTR), ("=", XML), (f'"{attr("Temperature")}"', VAL), ("  ", XML),
     ("crs:Tint", ATTR), ("=", XML), (f'"{attr("Tint")}"', VAL)],
    [("            crs:Exposure2012", ATTR), ("=", XML), (f'"{attr("Exposure2012")}"', VAL), ("  ", XML),
     ("crs:Vibrance", ATTR), ("=", XML), (f'"{attr("Vibrance")}"', VAL), ("  ", XML),
     ("crs:Saturation", ATTR), ("=", XML), (f'"{attr("Saturation")}"', VAL)],
    [(f"            … {n_crs} crs: scalar attributes in this file: tone, presence, HSL, detail, optics, crop", NOTE)],
    gap(),
    [("        arrays & structs — child elements, values in rdf containers", HILITE)],
]
if curve:
    LINES += [off(at("<crs:ToneCurvePV2012>")[0]) + [("  <crs:ToneCurvePV2012>", XML), ("      curves: rdf:Seq of \"x, y\" points", NOTE)],
              [("              <rdf:Seq>", XML)] + sum([[("<rdf:li>", XML), (pt, VAL), ("</rdf:li>", XML)] for pt in points], [])
              + [("</rdf:Seq>", XML)]]
if "<crs:RemoveAreas>" in X:
    LINES += [off(at("<crs:RemoveAreas>")[0]) + [("  <crs:RemoveAreas>", XML),
              ("            what Remove / Generative Remove erases: AI object mask + brush, by MaskDigest", NOTE)]]
if "<crs:MaskGroupBasedCorrections>" in X:
    LINES += [off(at("<crs:MaskGroupBasedCorrections>")[0]) + [("  <crs:MaskGroupBasedCorrections>   masks: Seq of nested Descriptions", HILITE)],
              [("              <rdf:li><rdf:Description ", XML), ("crs:What", ATTR), ("=", XML), ('"Correction"', VAL)],
              [("                crs:CorrectionName", ATTR), ("=", XML), (f'"{groups[0]}"', VAL), ("  ", XML),
               ("crs:CorrectionActive", ATTR), ("=", XML), (f'"{first_active}"', VAL)],
              [("                crs:CorrectionSyncID", ATTR), ("=", XML), (f'"{first_sync[:16]}…"', VAL),
               (f"  ({len(groups)} groups: {', '.join(groups[:3])}, …)", NOTE)],
              [("                <crs:CorrectionMasks> … brush/radial/linear/AI geometry + LumEq range curves", NOTE)],
              [("              </rdf:Description></rdf:li>", XML)]]
LINES += [gap(), off(at("</rdf:RDF>")[0]) + [("</rdf:RDF>", XML)], off(at("</x:xmpmeta>")[0]) + [("</x:xmpmeta>", XML)]]
if packet:
    LINES += [off(at("<?xpacket end")[0]) + [("<?xpacket end=", XML), ('"w"', VAL), ("?>", XML), ("   ", XML),
                                             ('"w" = in-place rewrite allowed; tail padding enables it', NOTE)]]
LINES += [gap(),
    [("rules:", HILITE), ("  flat slider → attribute   ·   list/curve → rdf:Seq   ·   bag/unordered → rdf:Bag", NOTE)],
    [(f"          mask = nested rdf:Description inside a Seq ({n_desc} nested, {n_seq} rdf:Seq here)   ·   "
      "settings\\ store = same bare XML", NOTE)],
]

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def make_svg(path):
    fs, lh, pad = 14, 20, 26
    width = 1480
    height = pad * 2 + lh * (len(LINES) + 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Consolas, \'Cascadia Mono\', \'Courier New\', monospace">',
             f'<rect width="{width}" height="{height}" fill="{BG}"/>']
    y = pad
    parts.append(f'<text x="{pad}" y="{y}" font-size="{fs+2}" font-weight="bold" fill="{TITLE}">'
                 'Develop XMP — internal structure</text>')
    y += lh + 8
    for line in LINES:
        if line and any(s.strip() for s, _ in line):
            tspans = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in line)
            parts.append(f'<text x="{pad}" y="{y}" font-size="{fs}" xml:space="preserve">{tspans}</text>')
        y += lh
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

def make_png(path):
    from PIL import Image, ImageDraw, ImageFont
    fs = 14
    font  = ImageFont.truetype("consola.ttf", fs)
    tfont = ImageFont.truetype("consolab.ttf", fs + 2)
    lh, pad = 21, 28
    width = int(max(sum(font.getlength(t) for t, _ in line) for line in LINES
                    if line and any(s.strip() for s, _ in line)) + pad * 2 + 16)
    height = pad * 2 + lh * (len(LINES) + 2)
    img = Image.new("RGB", (int(width), height), BG)
    d = ImageDraw.Draw(img)
    y = pad - 4
    d.text((pad, y), "Develop XMP — internal structure", font=tfont, fill=TITLE)
    y += lh + 8
    for line in LINES:
        if line and any(s.strip() for s, _ in line):
            x = pad
            for t, c in line:
                d.text((x, y), t, font=font, fill=c)
                x += font.getlength(t)
        y += lh
    img.save(path)

make_svg(os.path.join(OUT, "xmp-structure.svg"))
make_png(os.path.join(OUT, "xmp-structure.png"))
print("written:", OUT)
