r"""Render the Lightroom (cloud) local-data-layout tree as PNG + SVG.

Two variants:
  lightroom-cc-data-tree.png/.svg        detailed, with sizes/counts
  lightroom-cc-data-tree-plain.png/.svg  simplified, no sizes/counts

Re-run after editing:  python scripts/make_tree_image.py
"""
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "assets")
os.makedirs(OUT, exist_ok=True)

# ---- palette (GitHub-dark) ----
BG      = "#0d1117"
GLYPH   = "#4d5761"   # tree-structure characters
DIR     = "#79c0ff"   # folder names
FILE    = "#e6edf3"   # file names
NOTE    = "#8b949e"   # annotations / counts
HILITE  = "#ffa657"   # starred (recovery-critical)
BAD     = "#ff7b72"   # the red herrings / traps
TITLE   = "#e6edf3"

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# ---------------- detailed variant (with sizes/counts) ----------------

LINES = [
    [("%LOCALAPPDATA%\\Adobe\\Lightroom CC\\", DIR)],
    [("├── ", GLYPH), ("Caches\\", DIR), ("                    8 files — per-user cache blobs (guid-named, ~12 KB)", NOTE)],
    [("├── ", GLYPH), ("Connections\\", DIR), ("              2 files — sync connection state", NOTE)],
    [("├── ", GLYPH), ("Preferences\\", DIR), ("              1 file", NOTE)],
    [("├── ", GLYPH), ("avatar\\", DIR), ("                   26 files — Adobe profile avatars", NOTE)],
    [("└── ", GLYPH), ("Data\\", DIR)],
    [("    ├── ", GLYPH), ("<catalog-guid>\\", DIR), ("     ← one folder per cloud catalog", NOTE)],
    [("    │   ├── ", GLYPH), ("Managed Catalog.mcat", FILE), ("        160 MB — document store,", NOTE)],
    [("    │   │", GLYPH), ("                                     sync source of truth (CBOR blobs)", NOTE)],
    [("    │   │   + -shm / -wal", NOTE), ("                         WAL siblings — copy together!", BAD)],
    [("    │   ├── ", GLYPH), ("Managed Catalog.mru", FILE)],
    [("    │   ├── ", GLYPH), ("Managed Catalog.notifdb", FILE), (" (+ -wal)", NOTE), ("   notifications (ignorable)", NOTE)],
    [("    │   ├── ", GLYPH), ("Managed Catalog.wfindex", FILE), ("      36 MB — • SQL index: the goldmine", HILITE)],
    [("    │   │   + -shm / -wal", NOTE)],
    [("    │   ├── ", GLYPH), ("cullingScores.db", FILE), ("          2.9 MB — AI culling scores", NOTE)],
    [("    │   ├── ", GLYPH), ("originals\\", DIR), ("                 1,692 RAWs — 64 GB — 2nd copy of your own files", NOTE)],
    [("    │   │   ├── ", GLYPH), ("2025\\2024-11-16\\DSCxxxxx.ARW", DIR), ("   grouped by year\\capture-date", NOTE)],
    [("    │   │   ├── ", GLYPH), ("2026\\2025-02-08\\ … 2025-06-08\\", DIR), ("  9 date folders", NOTE)],
    [("    │   │   └── ", GLYPH), ("0000\\0000-00-00\\", DIR), ("              ← photos with unknown capture date", BAD)],
    [("    │   ├── ", GLYPH), ("settings\\", DIR), ("                 2,648 files — •• per-photo develop XMPs", HILITE)],
    [("    │   │   └── ", GLYPH), ("<64-hex sha256>", FILE), ("             no extension — named by content hash", NOTE)],
    [("    │   ├── ", GLYPH), ("auxiliary\\", DIR), ("               4,734 files in 2,801 shards", NOTE)],
    [("    │   │   └── ", GLYPH), ("<digest[:3]>\\<digest[3:]>", FILE), ("       mask rasters (TIFF) + zlib XMP payloads", NOTE)],
    [("    │   ├── ", GLYPH), ("previews\\", DIR), ("                5,530 renders in 256 shards", NOTE)],
    [("    │   │   └── ", GLYPH), ("<2-hex>\\<key><suffix>", FILE), ("            afa=320px ama=640px baa=2048px (edited)", NOTE)],
    [("    │   ├── ", GLYPH), ("proxies\\", DIR), ("                 318 files — 2560px DNG stand-ins (unedited)", NOTE)],
    [("    │   │   └── ", GLYPH), ("2560\\<assetId[:3]>\\<assetId[3:]>", FILE)],
    [("    │   ├── ", GLYPH), ("cr_settings\\", DIR), ("             234 user presets (real ACR .xmp format)", HILITE)],
    [("    │   │   └── ", GLYPH), ("<preset-docId>.xmp", FILE)],
    [("    │   ├── ", GLYPH), ("cr_defaults\\", DIR), ("             FavoriteStyles.xmp · RawDefaults.xmp", NOTE)],
    [("    │   ├── ", GLYPH), ("cr_cameraprofiles\\", DIR), ("        (empty — profiles ship with the app)", NOTE)],
    [("    │   ├── ", GLYPH), ("watermarks\\ · people\\", DIR), ("       (empty here)", NOTE)],
    [("    │   ├── ", GLYPH), ("xmp\\", DIR), ("                     2,570 shards — transient downloads,", BAD)],
    [("    │   │   └── ", GLYPH), ("<2-hex>\\ + Index_*.dat", FILE), ("         empty between syncs (the red herring)", BAD)],
    [("    │   └── ", GLYPH), ("big_table_cache\\", DIR), ("          (empty)", NOTE)],
    [("    ├── ", GLYPH), ("<other catalog guids>\\", DIR), ("         one per account/library that synced", NOTE)],
    [("    ├── ", GLYPH), ("FolderSourcePreviews\\ · TemporaryEdits\\", DIR), ("   app working areas", NOTE)],
    [("    └── ", GLYPH), ("big_table_cache\\ · profiles\\ · user\\", DIR), ("   app-level defaults", NOTE)],
    [("", NOTE)],
    [("• = recovery-critical      ", HILITE), ("│ tree verified against a live library · counts = real file counts", NOTE)],
]

# ---------------- simplified variant (no sizes/counts) ----------------

def build_simple():
    NC = 52   # column where annotations start
    def row(g, name, note, nc=NOTE, namec=FILE):
        pad = " " * max(1, NC - len(g) - len(name))
        return [(g, GLYPH), (name, namec), (pad + note, nc)]
    return [
        [("%LOCALAPPDATA%\\Adobe\\Lightroom CC\\", DIR)],
        [("├── ", GLYPH), ("Caches\\ · Connections\\ · Preferences\\ · avatar\\", DIR),
         ("            app state — ignorable", NOTE)],
        [("└── ", GLYPH), ("Data\\<catalog-guid>\\", DIR),
         ("                      one folder per cloud catalog", NOTE)],
        [("    ├── ", GLYPH), ("Managed Catalog.mcat", FILE),
         ("            document store — sync source of truth", NOTE)],
        [("    ├── ", GLYPH), ("Managed Catalog.wfindex", FILE),
         ("           SQL index — the recovery goldmine", HILITE)],
        [("    ├── ", GLYPH), ("originals\\<year>\\<date>\\", DIR),
         ("             your RAW files", NOTE)],
        [("    ├── ", GLYPH), ("settings\\<64-hex sha256>", FILE),
         ("              per-photo develop XMPs", HILITE)],
        [("    ├── ", GLYPH), ("previews\\<shard>\\<key>", FILE),
         ("              rendered JPEGs — edits baked in", NOTE)],
        [("    ├── ", GLYPH), ("auxiliary\\<digest[:3]>\\<digest[3:]>", FILE),
         ("       mask rasters + zlib XMP payloads", NOTE)],
        [("    ├── ", GLYPH), ("proxies\\2560\\<assetId>", FILE),
         ("              DNG stand-ins — unedited", NOTE)],
        [("    ├── ", GLYPH), ("cr_settings\\<preset-docId>.xmp", FILE),
         ("       ACR presets · cr_defaults\\ raw defaults", NOTE)],
        [("    └── ", GLYPH), ("xmp\\<shard>\\", DIR),
         ("                        empty — the red herring", BAD)],
        [("", NOTE)],
        [("• = recovery-critical", HILITE)],
    ]

# ---------------- renderers ----------------

def make_svg(path, lines, title):
    fs, lh, pad = 15, 21, 28
    width = 1080
    height = pad * 2 + lh * (len(lines) + 2)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="Consolas, \'Cascadia Mono\', \'Courier New\', monospace">',
             f'<rect width="{width}" height="{height}" fill="{BG}"/>']
    y = pad
    parts.append(f'<text x="{pad}" y="{y}" font-size="{fs+2}" font-weight="bold" fill="{TITLE}">{esc(title)}</text>')
    y += lh + 6
    for line in lines:
        if line and line[0][0]:
            tspans = "".join(f'<tspan fill="{c}">{esc(t)}</tspan>' for t, c in line)
            parts.append(f'<text x="{pad}" y="{y}" font-size="{fs}" xml:space="preserve">{tspans}</text>')
        y += lh
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

def make_png(path, lines, title):
    from PIL import Image, ImageDraw, ImageFont
    fs = 15
    font  = ImageFont.truetype("consola.ttf", fs)
    tfont = ImageFont.truetype("consolab.ttf", fs + 2)
    lh, pad = 22, 30
    width = int(max(sum(font.getlength(t) for t, _ in line) for line in lines
                    if line and line[0][0]) + pad * 2 + 20)
    height = pad * 2 + lh * (len(lines) + 2)
    img = Image.new("RGB", (int(width), height), BG)
    d = ImageDraw.Draw(img)
    y = pad - 4
    d.text((pad, y), title, font=tfont, fill=TITLE)
    y += lh + 8
    for line in lines:
        if line and line[0][0]:
            x = pad
            for t, c in line:
                d.text((x, y), t, font=font, fill=c)
                x += font.getlength(t)
        y += lh
    img.save(path)

make_svg(os.path.join(OUT, "lightroom-cc-data-tree.svg"), LINES,
         "Adobe Lightroom (cloud) — local data layout")
make_png(os.path.join(OUT, "lightroom-cc-data-tree.png"), LINES,
         "Adobe Lightroom (cloud) — local data layout")

simple = build_simple()
make_svg(os.path.join(OUT, "lightroom-cc-data-tree-plain.svg"), simple,
         "Adobe Lightroom (cloud) — local data tree (simplified)")
make_png(os.path.join(OUT, "lightroom-cc-data-tree-plain.png"), simple,
         "Adobe Lightroom (cloud) — local data tree (simplified)")
print("written:", OUT)
