r"""Render the internal structure of a Lightroom develop XMP file as PNG + SVG.

All offsets and values are real, taken from DSC08974.xmp (24,340 bytes —
packet envelope + 178 scalar attributes + 50 rdf:Seq arrays + 11 nested
Descriptions, incl. a mask group named "Water").

Output: docs/assets/xmp-structure.png / .svg
Re-run after editing LINES:  python scripts/make_xmp_structure_image.py
"""
import os

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

LINES = [
    [("Anatomy of a develop XMP sidecar — real file, real offsets (DSC08974.xmp, 24,340 B)", TITLE)],
    gap(),
    off(0)     + [("<?xpacket ", XML), ("begin", ATTR), ("=", XML), ('"<BOM>"', VAL), (" ", XML), ("id", ATTR), ("=", XML), ('"W5M0MpCehiHzreSzNTczkc9d"', VAL), ("?>", XML)],
    [("", NOTE), ("packet envelope — id is a fixed GUID; begin BOM allows UTF-8 detection", NOTE)],
    off(54)    + [("<x:xmpmeta ", XML), ("xmlns:x", ATTR), ("=", XML), ('"adobe:ns:meta/"', VAL), (" ", XML), ("x:xmptk", ATTR), ("=", XML), ('"Adobe XMP Core 7.0-c000 …"', VAL), (">", XML)],
    [("", NOTE), ("wrapper + writing toolkit identity", NOTE)],
    off(164)   + [("<rdf:RDF ", XML), ("xmlns:rdf", ATTR), ("=", XML), ('"…/22-rdf-syntax-ns#"', VAL), (">", XML)],
    off(232)   + [("<rdf:Description ", XML), ("rdf:about", ATTR), ("=", XML), ('""', VAL), (" ", XML), ("xmlns:crs", ATTR), ("=", XML), ('"…/camera-raw-settings/1.0/"', VAL), (">", XML)],
    [("", NOTE), ("one edit = one Description; crs = Camera Raw Settings namespace", NOTE)],
    gap(),
    [("        scalar attributes — the sliders (flat name=\"value\")", HILITE)],
    [("            crs:ProcessVersion", ATTR), ("=", XML), ('"15.4"', VAL), ("   ", XML), ("crs:Version", ATTR), ("=", XML), ('"18.5.1"', VAL)],
    [("            crs:WhiteBalance", ATTR), ("=", XML), ('"Custom"', VAL), ("  ", XML), ("crs:Temperature", ATTR), ("=", XML), ('"5200"', VAL), ("  ", XML), ("crs:Tint", ATTR), ("=", XML), ('"+13"', VAL)],
    [("            crs:Exposure2012", ATTR), ("=", XML), ('"0.00"', VAL), ("  ", XML), ("crs:Vibrance", ATTR), ("=", XML), ('"+15"', VAL), ("  ", XML), ("crs:Saturation", ATTR), ("=", XML), ('"+5"', VAL)],
    [("            … 178 scalar attributes in this file: tone, presence, HSL, detail, optics, crop", NOTE)],
    gap(),
    [("        arrays & structs — child elements, values in rdf containers", HILITE)],
    off(4098)  + [("  <crs:ToneCurvePV2012>", XML), ("      curves: rdf:Seq of \"x, y\" points", NOTE)],
    [("              <rdf:Seq><rdf:li>", XML), ("0, 0", VAL), ("</rdf:li><rdf:li>", XML), ("255, 255", VAL), ("</rdf:li></rdf:Seq>", XML)],
    off(5085)  + [("  <crs:MaskGroupBasedCorrections>   masks: Seq of nested Descriptions", HILITE)],
    [("              <rdf:li><rdf:Description ", XML), ("crs:What", ATTR), ("=", XML), ('"Correction"', VAL)],
    [("                crs:CorrectionName", ATTR), ("=", XML), ('"Water"', VAL), ("  ", XML), ("crs:CorrectionActive", ATTR), ("=", XML), ('"true"', VAL)],
    [("                crs:CorrectionSyncID", ATTR), ("=", XML), ('"178CE3C8FA3715C7…"', VAL), ("  (7 groups: Water, Sky, …)", NOTE)],
    [("                <crs:CorrectionMasks> … brush/radial/linear/AI geometry + LumEq range curves", NOTE)],
    [("              </rdf:Description></rdf:li>", XML)],
    [("          <crs:RangeMaskMapInfo> … </crs:RangeMaskMapInfo>     nested masks carry their own curves", NOTE)],
    gap(),
    off(24297) + [("</rdf:RDF></x:xmpmeta>", XML)],
    off(24321) + [("<?xpacket end=", XML), ('"w"', VAL), ("?>", XML), ("   ", XML), ('"w" = in-place rewrite allowed; tail padding enables it', NOTE)],
    gap(),
    [("rules:", HILITE), ("  flat slider → attribute   ·   list/curve → rdf:Seq   ·   bag/unordered → rdf:Bag", NOTE)],
    [("          mask = nested rdf:Description inside a Seq   ·   settings\\ store = same XML minus the envelope", NOTE)],
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
        if line and line[0][0]:
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
                    if line and line[0][0]) + pad * 2 + 16)
    height = pad * 2 + lh * (len(LINES) + 2)
    img = Image.new("RGB", (int(width), height), BG)
    d = ImageDraw.Draw(img)
    y = pad - 4
    d.text((pad, y), "Develop XMP — internal structure", font=tfont, fill=TITLE)
    y += lh + 8
    for line in LINES:
        if line and line[0][0]:
            x = pad
            for t, c in line:
                d.text((x, y), t, font=font, fill=c)
                x += font.getlength(t)
        y += lh
    img.save(path)

make_svg(os.path.join(OUT, "xmp-structure.svg"))
make_png(os.path.join(OUT, "xmp-structure.png"))
print("written:", OUT)
