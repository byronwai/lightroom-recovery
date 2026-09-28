r"""Catalog tables <-> file stores: the join graph, as SVG + PNG.

Writes docs/assets/join-graph.svg + .png (headless Edge).
Complements the Mermaid version in diagrams.md section 2.
Run:  python scripts/make_join_graph_image.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

W, H = 1560, 1130
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY, RED = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899", "#ff7b72"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="{SANS}">',
     f'<rect width="{W}" height="{H}" fill="{BG}"/>',
     '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
     'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
     f'<path d="M 0 0 L 10 5 L 0 10 z" fill="#8b949e"/></marker></defs>']

def box(x, y, w, h, border, fill=PANEL, rx=14, dash="", sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
             f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
             f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

def line(x1, y1, x2, y2, color=DIM, w=1.8):
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
             f'stroke-width="{w}" marker-end="url(#arr)"/>')

# ---------- title ----------
text(40, 52, "Catalog tables ↔ file stores — the join graph", 30, TXT, SANS, "bold")
text(40, 82, "wfindex (SQL) left · content-addressed stores right · every arrow is the exact join key", 15, DIM)

# ---------- left panel: wfindex tables ----------
box(40, 110, 560, 860, PURPLE)
text(60, 142, "Managed Catalog.wfindex — TABLES", 15, PURPLE, SANS, "bold")

tables = [
    ("assets", "assetId · filename · captureDate · rating", BLUE, True),
    ("versions", "docId · assetId — one row per edit", GREEN, False),
    ("externalDevelopSettings", "docId · sha256 (settings\\ space)", GREEN, False),
    ("purgeCandidates", "assetId · binaryType · contentIdOrSha256 · hasLocalFile", ORANGE, True),
    ("assetPathsAndInfo", "docId (= assetId!) · originalRelativePath", BLUE, True),
    ("localAuxTracker", "docId · digest", PURPLE, False),
    ("presetsAndProfiles", "docId · name", GREEN, False),
]
ty = 162
centers = {}
for name, cols, col, crit in tables:
    box(56, ty, 528, 84, col if crit else "#30363d", fill="#0e1420", rx=10)
    text(72, ty + 34, name, 16.5, col if crit else TXT, MONO, "bold")
    text(72, ty + 62, cols, 12.5, DIM, MONO)
    centers[name] = ty + 42
    ty += 106

# ---------- right panel: file stores ----------
box(960, 110, 560, 860, EDGE_)
text(980, 142, "FILE STORES — plain files, content-addressed", 15, DIM, SANS, "bold")

stores = [
    ("settings\\", "<64-hex sha256> · no extension", "per-photo develop XMPs", ORANGE),
    ("auxiliary\\", "<digest[:3]>\\<digest[3:]>", "renditions + zlib XMP payloads", PURPLE),
    ("originals\\", "<year>\\<capture-date>\\*.ARW", "the RAW files", BLUE),
    ("proxies\\", "2560\\<assetId[:3]>\\<assetId[3:]>", "2560 px DNG stand-ins (unedited)", BLUE),
    ("cr_settings\\", "<preset-docId>.xmp", "ACR presets", GREEN),
]
sy = 168
scenters = {}
for name, scheme, desc, col in stores:
    box(976, sy, 528, 118, col)
    text(994, sy + 34, name, 19, col, MONO, "bold")
    text(994, sy + 62, scheme, 13.5, DIM, MONO)
    text(994, sy + 90, desc, 13.5, DIM)
    scenters[name] = sy + 59
    sy += 140

# ---------- join arrows (exact keys) ----------
joins = [
    ("purgeCandidates", "settings\\",
     "binaryType='xmp_develop'", "contentIdOrSha256 = filename", ORANGE, 300),
    ("localAuxTracker", "auxiliary\\",
     "digest = folder + name", "", PURPLE, 445),
    ("assetPathsAndInfo", "originals\\",
     "originalRelativePath", "", BLUE, 590),
    ("assets", "proxies\\",
     "assetId = folder + name", "", BLUE, 735),
    ("presetsAndProfiles", "cr_settings\\",
     "docId = filename", "", GREEN, 880),
]
for src, dst, k1, k2, col, ly in joins:
    y1, y2 = centers[src], scenters[dst]
    line(588, y1, 972, y2, col)
    text(780, ly, k1, 13.5, col, MONO, "bold", "middle")
    if k2:
        text(780, ly + 20, k2, 12.5, col, MONO, "normal", "middle")

# ---------- footer: key-space gotchas ----------
box(40, 996, 1480, 100, RED, dash="8 5", sw=1.6)
text(60, 1026, "KEY-SPACE GOTCHAS — where silent join failures live", 14, RED, SANS, "bold")
text(60, 1052, "assets.docId = INTEGER row id (a third, unrelated space)  ·  assetPathsAndInfo.docId actually holds assetIds", 13.5, DIM, MONO)
text(60, 1076, "docId joins across versions · purgeCandidates · localAuxTracker · externalDevelopSettings — no single table covers all documents", 13.5, DIM, MONO)

S.append("</svg>")
SVG_PATH = os.path.join(OUT, "join-graph.svg")
with open(SVG_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(S))
print("svg written:", SVG_PATH)

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, "shot.png")
    subprocess.run([EDGE, "--headless=new", f"--screenshot={out}",
                    f"--window-size={W},{H}", "--force-device-scale-factor=1",
                    "--default-background-color=00000000",
                    "file:///" + SVG_PATH.replace("\\", "/")],
                   check=True, capture_output=True, timeout=90)
    import shutil; shutil.copy(out, os.path.join(OUT, "join-graph.png"))
print("png written")
