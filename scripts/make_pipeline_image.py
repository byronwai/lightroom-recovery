r"""The recovery pipeline (01-08) as SVG + PNG.

Writes docs/assets/pipeline.svg + .png (Chrome/Edge headless).
Run:  python scripts/make_pipeline_image.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1200, 1560
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899"
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

def arrow(x1, y1, x2, y2, color=TXT, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
             f'stroke-width="2" marker-end="url(#arr)"{d}/>')

text(40, 52, "The recovery pipeline", 30, TXT, SANS, "bold")
text(40, 82, "eight idempotent steps — every one standalone (--data / --work / --out), resumable after any failure", 15, DIM)

steps = [
    ("01", "snapshot_catalog", PURPLE,
     ["copy mcat + wfindex + previews out of Adobe's", "purge-able cache — run this FIRST"]),
    ("02", "build_recovery", BLUE,
     ["originals copy · DNG proxies · edited JPEGs", "manifest.csv · catalog backup"]),
    ("03", "match_previews", GREEN,
     ["strict perceptual matching of edited JPEGs", "against RAW-embedded previews"]),
    ("04", "match_previews_round2", GREEN,
     ["crop-tolerant matching — a wrong name", "is worse than no name"]),
    ("05", "make_helper", GRAY,
     ["match-helper.html contact sheet —", "human confirms the top-3 candidates"]),
    ("06", "extract_settings_xmp", ORANGE,
     ["the big one: every per-photo develop XMP", "from settings\\, placed next to its RAW", "+ presets recovered with real names"]),
    ("07", "install_acr_presets", GREEN,
     ["optional (dry-run default): presets into", "%APPDATA%\\Adobe\\CameraRaw\\Settings"]),
    ("08", "assemble_mask_rasters", PURPLE,
     ["offline .acr equivalent: type-02 rasters", "attributed to photos, decoded to PNG", "(needs tifffile + imagecodecs)"]),
]

y = 110
X, Wb, Hb = 120, 720, 118
centers = {}
for num, name, col, desc in steps:
    box(X, y, Wb, Hb, col)
    text(X + 20, y + 32, num, 20, col, MONO, "bold")
    text(X + 78, y + 32, name, 17, col, MONO, "bold")
    for i, ln in enumerate(desc):
        text(X + 78, y + 58 + i * 22, ln, 13.5, DIM)
    centers[num] = y + Hb
    if y > 110:
        arrow(X + Wb // 2, y - 12, X + Wb // 2, y - 2)
    y += Hb + 22

# side rails
M = box if False else None
box(940, 470, 220, 210, BLUE, dash="6 4", sw=1.6)
text(960, 500, "manifest.csv", 15, BLUE, MONO, "bold")
text(960, 526, "per-photo inventory", 13, DIM)
text(960, 548, "written by 02", 13, DIM)
text(960, 576, "xmpSidecar column", 13, DIM)
text(960, 596, "patched by 06", 13, DIM)
arrow(936, 560, 846, 560, BLUE, dash="5 4")
arrow(X + Wb, 560, 936, 560, BLUE, dash="5 4")

box(940, 1070, 220, 160, PURPLE, dash="6 4", sw=1.6)       # level with step 08, which reads it
text(960, 1100, "auxiliary\\ store", 15, PURPLE, MONO, "bold")
text(960, 1126, "4,504 type-02", 13, DIM)
text(960, 1146, "mask rasters", 13, DIM)
text(960, 1174, "purge aux rows give", 13, DIM)
text(960, 1194, "digest + assetId", 13, DIM)
arrow(936, 1149, 846, 1149, PURPLE, dash="5 4")

text(40, 1520, "steps are safe to re-run: identical writes are skipped, never duplicated", 13.5, DIM, MONO)

S.append("</svg>")
SVG = os.path.join(OUT, "pipeline.svg")
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
    import shutil; shutil.copy(out, os.path.join(OUT, "pipeline.png"))
print("written:", SVG)
print("written:", os.path.join(OUT, "pipeline.png"))
