r"""Forensic flow: how the Catalog <-> XMP linkage was actually discovered.

Writes docs/assets/catalog-xmp-discovery.svg + .png (headless Edge).
Mirrors walkthrough.md steps 3-6, dead ends included.
Run:  python scripts/make_discovery_flow_image.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
EDGE = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1180, 1760
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, RED, GRAY = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#ff7b72", "#7A8899"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
     f'viewBox="0 0 {W} {H}" font-family="{SANS}">',
     f'<rect width="{W}" height="{H}" fill="{BG}"/>',
     '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" '
     'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
     f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{TXT}"/></marker></defs>']

def box(x, y, w, h, border, fill=PANEL, rx=14, dash="", sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
             f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
             f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

def arrow(x1, y1, x2, y2, label=None, lx=None, ly=None, color=TXT):
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
             f'stroke-width="2" marker-end="url(#arr)"/>')
    if label:
        text(lx, ly, label, 13.5, color, MONO, "bold", "middle")

CX = 590
def centered(y, s, size=15, fill=TXT, font=SANS, weight="normal"):
    text(CX, y, s, size, fill, font, weight, "middle")

# ---------- title ----------
text(40, 52, "How the Catalog ↔ XMP linkage was found — the forensic path", 28, TXT, SANS, "bold")
text(40, 82, "reconstruction of the actual investigation · dead ends included · numbers from the real recovery", 15, DIM)

# ---------- start ----------
box(190, 110, 800, 84, GRAY)
centered(144, "~630 photos edited (versions table)", 17, TXT, SANS, "bold")
centered(172, "but every develop setting is invisible — where do the edits physically live?", 14, DIM)
arrow(CX, 198, CX, 240, "the obvious candidates first", CX + 150, 226)

# ---------- dead ends ----------
box(90, 246, 460, 92, RED, dash="7 5", sw=1.6)
text(110, 276, "xmp\\", 17, RED, MONO, "bold")
text(110, 302, "the folder literally named for it —", 13.5, DIM)
text(110, 324, "0 files", 13.5, DIM)

box(630, 246, 460, 92, RED, dash="7 5", sw=1.6)
text(650, 276, "big_table_cache\\", 17, RED, MONO, "bold")
text(650, 302, "the general blob cache —", 13.5, DIM)
text(650, 324, "0 files", 13.5, DIM)

box(240, 372, 700, 74, RED, fill="#1a0f0d", sw=1.6)
centered(402, "early — wrong — conclusion:", 14.5, RED, SANS, "bold")
centered(428, "\u201cmost edit settings are cloud-only\u201d", 15, DIM, MONO)

arrow(CX, 450, CX, 492, "but Adobe's own bookkeeping disagreed …", CX + 170, 478, PURPLE)

# ---------- the census clue ----------
box(140, 498, 900, 122, PURPLE)
text(160, 528, "the census query — purgeCandidates", 15, PURPLE, SANS, "bold")
text(160, 556, "SELECT binaryType, COUNT(*), SUM(hasLocalFile) FROM purgeCandidates GROUP BY 1", 14, TXT, MONO)
text(160, 584, "xmp_develop:  3,457 rows  ·  2,123 flagged hasLocalFile=1", 15, GREEN, MONO, "bold")
text(160, 608, "Adobe's own index claims 2,123 develop XMPs exist ON THIS MACHINE", 14, DIM)

arrow(CX, 626, CX, 668, "index says local → the files exist → stop guessing folders", CX + 200, 654, BLUE)

# ---------- the filename census ----------
box(190, 674, 800, 104, BLUE)
text(210, 704, "the 4-line census that should have run first", 15, BLUE, SANS, "bold")
text(210, 730, "os.walk the whole tree · keep names matching ^[0-9a-f]{64}$", 14, TXT, MONO)
text(210, 758, "no assumptions about what any folder is \u201cfor\u201d", 13.5, DIM)

arrow(CX, 784, CX, 826, "2,592 hits — all in one folder", CX + 140, 812, ORANGE)

# ---------- discovery ----------
box(140, 832, 900, 118, ORANGE, fill="#1f1608", sw=3)
text(160, 864, "settings\\", 22, ORANGE, MONO, "bold")
text(160, 892, "2,648 extensionless files named by 64-hex sha256", 15, TXT)
text(160, 918, "the folder skipped for hours because its name sounded like app preferences", 13.5, DIM)
text(160, 938, "", 12, DIM)

arrow(CX, 958, CX, 1000, "so is the column in the index the same thing?", CX + 190, 986, GREEN)

# ---------- decisive test ----------
box(140, 1006, 900, 122, GREEN, fill="#0e1a10", sw=3)
text(160, 1038, "the decisive test", 17, GREEN, SANS, "bold")
text(160, 1066, "contentIdOrSha256 values  vs  actual filenames in settings\\", 15, TXT, MONO)
text(160, 1094, "2,123/2,123 rows resolve · 1,345/1,345 distinct shas — 100%, zero misses", 15.5, GREEN, MONO, "bold")
text(160, 1118, "no decoding, no hashing: one SQL row is the entire linkage", 13.5, DIM)

arrow(CX, 1136, CX, 1178, "and the payloads are what Adobe documents them to be", CX + 210, 1164, GREEN)

# ---------- content check ----------
box(190, 1184, 800, 88, GREEN)
text(210, 1214, "content verification (publicly documented)", 14.5, GREEN, SANS, "bold")
text(210, 1240, "http://ns.adobe.com/camera-raw-settings/1.0/  +  crs:Exposure2012 present", 13.5, TXT, MONO)
text(210, 1262, "→ these are Camera Raw develop settings", 13.5, DIM)

arrow(CX, 1280, CX, 1322, "join it all together", CX + 90, 1308, ORANGE)

# ---------- the join result ----------
box(140, 1328, 900, 118, ORANGE, fill="#1f1608", sw=3)
text(160, 1360, "the linkage, productized", 16, ORANGE, SANS, "bold")
text(160, 1388, "purgeCandidates.assetId + assets.filename + assetPathsAndInfo.path", 14, TXT, MONO)
text(160, 1414, "1,952 named sidecars · every edited photo covered · counts reconcile", 14.5, GREEN)
text(160, 1438, "current revision by dateLastUpdatedInSeconds · wrap() adds the xpacket envelope", 13, DIM)

# ---------- epilogue: the .acr sequel ----------
arrow(CX, 1446, CX, 1486)
box(90, 1492, 1000, 100, GREEN, fill="#0e1a10", sw=2)
text(110, 1522, "epilogue — after access was restored, a real export", 14.5, GREEN, SANS, "bold")
text(110, 1548, "\"original + settings\" emitted .acr companions — same type-02 records as auxiliary\:", 13.5, TXT, MONO)
text(110, 1572, "the \"TIFF renditions\" finally had their name — mask rasters (§6.8, step 08)", 13.5, DIM)

# ---------- lesson ----------
box(90, 1620, 1000, 96, RED, dash="8 5", sw=1.6)
text(110, 1650, "the lesson", 14.5, RED, SANS, "bold")
text(110, 1676, "the index was right both times — the search was wrong", 15, TXT, MONO, "bold")
text(110, 1702, "enumerate every folder before assigning semantics to its name · full story: walkthrough.md steps 3–6", 13, DIM)

S.append("</svg>")
with open(SVG_PATH := os.path.join(OUT, "catalog-xmp-discovery.svg"), "w", encoding="utf-8") as f:
    f.write("\n".join(S))
print("svg written:", SVG_PATH)

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, "shot.png")
    subprocess.run([EDGE, "--headless=new", "--user-data-dir=" + os.path.join(td, "prof"),
                    f"--screenshot={out}",
                    f"--window-size={W},{H}", "--force-device-scale-factor=1",
                    "--default-background-color=00000000",
                    "file:///" + SVG_PATH.replace("\\", "/")],
                   check=True, capture_output=True, timeout=90)
    import shutil; shutil.copy(out, os.path.join(OUT, "catalog-xmp-discovery.png"))
print("png written")
