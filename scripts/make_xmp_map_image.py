r"""Render the XMP directory map (Adobe cache sources -> recovery layout)
as PNG + SVG.

Output: docs/assets/xmp-directory-map.png / .svg
Re-run after editing LINES below:  python scripts/make_xmp_map_image.py
"""
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "assets")
os.makedirs(OUT, exist_ok=True)

BG      = "#0d1117"
GLYPH   = "#4d5761"
DIR     = "#79c0ff"
FILE    = "#e6edf3"
NOTE    = "#8b949e"
HILITE  = "#ffa657"
BAD     = "#ff7b72"
TITLE   = "#e6edf3"
HEAD    = "#d2a8ff"

NOTE_COL = 46   # fixed column where annotations start

def row(glyph, name, note, note_color=NOTE, name_color=FILE):
    pad = " " * max(1, NOTE_COL - len(glyph) - len(name))
    return [(glyph, GLYPH), (name, name_color), (pad + note, note_color)]

def cont(text, indent_len):
    return [(" " * indent_len, GLYPH), (text, NOTE)]

LINES = [
    [("SOURCE — Adobe cache: where XMP lives", HEAD)],
    [("", NOTE)],
    [("Data\\<catalog-guid>\\", DIR)],
    row("├── ", "settings\\<64-hex sha256>", "2,648 per-photo develop blobs", HILITE),
    cont("current + superseded revisions, no envelope", 46),
    row("├── ", "auxiliary\\<digest[:3]>\\<digest[3:]>", "31 zlib XMPs among 4,734 files"),
    cont("23 Generative Remove · 8 develop (redundant)", 46),
    row("├── ", "cr_settings\\<preset-docId>.xmp", "234 user presets (ACR schema)", HILITE),
    row("├── ", "cr_defaults\\", "RawDefaults.xmp · FavoriteStyles.xmp"),
    row("└── ", "xmp\\<2-hex>\\", "transient shards — empty (red herring)", BAD),
    [("", NOTE)],
    [("DESTINATION — recovery output: 3,665 .xmp files", HEAD)],
    [("", NOTE)],
    [("<out>\\", DIR)],
    row("├── ", "originals\\<year>\\<date>\\", "1,785 XMPs beside their RAWs", HILITE, DIR),
    row("│   ├── ", "DSC03049.ARW", "", NOTE),
    row("│   ├── ", "DSC03049.xmp", "current edit — byte-identical base name", HILITE),
    row("│   ├── ", "DSC03049_<sha6>.xmp", "older revision (sha6 suffix)"),
    row("│   └── ", "DSC03049_aux.xmp", "Generative Remove record"),
    row("├── ", "xmp-sidecars\\", "336 (photo's RAW not cached locally)", NOTE, DIR),
    row("│   ├── ", "<date>_<RAW stem>.xmp", "current edit, date = disambiguator"),
    row("│   └── ", "_unlinked\\", "1,308 orphans no table can link", NOTE, DIR),
    row("├── ", "presets\\<name>.xmp", "234 ACR presets (real names)", HILITE),
    row("└── ", "raw-defaults\\", "2 (RawDefaults, FavoriteStyles)", NOTE, DIR),
    [("", NOTE)],
    [("rule: Camera Raw reads only a byte-identical base name —", HILITE),
     ("  every suffix exists to protect it", NOTE)],
]

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def make_svg(path):
    fs, lh, pad = 15, 21, 28
    width = 1080
    height = pad * 2 + lh * (len(LINES) + 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Consolas, \'Cascadia Mono\', \'Courier New\', monospace">',
             f'<rect width="{width}" height="{height}" fill="{BG}"/>']
    y = pad
    parts.append(f'<text x="{pad}" y="{y}" font-size="{fs+2}" font-weight="bold" fill="{TITLE}">'
                 f'XMP data map — Adobe cache sources to recovery layout</text>')
    y += lh + 6
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
    fs = 15
    font  = ImageFont.truetype("consola.ttf", fs)
    tfont = ImageFont.truetype("consolab.ttf", fs + 2)
    lh = 22
    pad = 30
    width = int(max(sum(font.getlength(t) for t, _ in line) for line in LINES
                    if line and line[0][0]) + pad * 2 + 20)
    height = pad * 2 + lh * (len(LINES) + 2)
    img = Image.new("RGB", (int(width), height), BG)
    d = ImageDraw.Draw(img)
    y = pad - 4
    d.text((pad, y), "XMP data map — Adobe cache sources to recovery layout",
           font=tfont, fill=TITLE)
    y += lh + 8
    for line in LINES:
        if line and line[0][0]:
            x = pad
            for t, c in line:
                d.text((x, y), t, font=font, fill=c)
                x += font.getlength(t)
        y += lh
    img.save(path)

make_svg(os.path.join(OUT, "xmp-directory-map.svg"))
make_png(os.path.join(OUT, "xmp-directory-map.png"))
print("written:", OUT)
