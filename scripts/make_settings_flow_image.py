r"""Flow diagram: how Managed Catalog.wfindex maps to the settings\\ store —
two variants:

  wfindex-settings-join.png/.svg        with counts (worked example)
  wfindex-settings-join-plain.png/.svg  no counts (library-agnostic)

PNGs via headless Edge. Run:  python scripts/make_settings_flow_image.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

W, H = 1180, 1320
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, RED = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#ff7b72"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build(with_counts=True):
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
            text(lx, ly, label, 14, color, MONO, "bold", "middle")

    text(40, 52, "How wfindex maps to settings\\ — the develop-XMP join", 28, TXT, SANS, "bold")
    text(40, 82, "one SQL index table turns anonymous sha256 files into named sidecars"
         + ("" if with_counts else "  ·  counts omitted — they vary per library"), 15, DIM)

    # ---- row 1: wfindex panel + settings store ----
    box(40, 120, 640, 320, PURPLE)
    text(60, 154, "Managed Catalog.wfindex  (SQLite, ~60 tables)", 18, PURPLE, MONO, "bold")

    box(60, 176, 600, 74, EDGE_, fill="#0e1420")
    text(76, 202, "purgeCandidates", 16, PURPLE, MONO, "bold")
    text(76, 226, ("WHERE binaryType='xmp_develop'  →  3,457 rows · 2,123 hasLocalFile=1"
                   if with_counts else
                   "WHERE binaryType='xmp_develop'  →  one row per edit blob"), 13.5, DIM, MONO)

    box(60, 262, 600, 74, EDGE_, fill="#0e1420")
    text(76, 288, "assets", 16, BLUE, MONO, "bold")
    text(76, 312, "assetId  →  filename · captureDate   (the photo's identity)", 13.5, DIM, MONO)

    box(60, 348, 600, 74, EDGE_, fill="#0e1420")
    text(76, 374, "assetPathsAndInfo", 16, GREEN, MONO, "bold")
    text(76, 398, "docId column = assetId  →  originalRelativePath   (the folder)", 13.5, DIM, MONO)

    box(760, 176, 380, 200, ORANGE)
    text(778, 208, "settings\\", 19, ORANGE, MONO, "bold")
    text(778, 236, "2,648 files" if with_counts else "one file per edit blob", 15, TXT)
    text(778, 264, "<64-hex sha256>", 14, DIM, MONO)
    text(778, 292, "bare <x:xmpmeta> develop", 13.5, DIM)
    text(778, 314, "settings — no extension,", 13.5, DIM)
    text(778, 336, "no envelope", 13.5, DIM)

    arrow(662, 213, 756, 213, "contentIdOrSha256  IS  the file name", 709, 160, ORANGE)

    # ---- row 2: revision selection ----
    box(40, 500, 1100, 120, BLUE)
    text(60, 532, "revisions", 16, BLUE, MONO, "bold")
    text(60, 558, "one assetId can own several shas  →  sort by dateLastUpdatedInSeconds", 15, TXT)
    text(60, 586, "newest → DSC02091.xmp          older → DSC02091_1045a0.xmp (_sha6 suffix)", 15, DIM, MONO)
    arrow(778, 380, 778, 496)
    arrow(370, 446, 370, 496)

    # ---- row 3: naming inputs ----
    box(40, 690, 520, 110, BLUE)
    text(60, 722, "from assets", 15, BLUE, MONO, "bold")
    text(60, 748, "filename → sidecar stem (DSC02091)", 15, TXT)
    text(60, 774, "byte-identical base name required", 13.5, DIM)

    box(620, 690, 520, 110, GREEN)
    text(640, 722, "from assetPathsAndInfo", 15, GREEN, MONO, "bold")
    text(640, 748, "originals\\<year>\\<capture-date>\\", 15, TXT, MONO)
    text(640, 774, "the XMP goes where the RAW already is", 13.5, DIM)
    arrow(370, 624, 300, 686)
    arrow(778, 624, 880, 686)

    # ---- row 4: wrap + output ----
    box(280, 870, 620, 90, PURPLE)
    text(300, 900, "wrap()", 16, PURPLE, MONO, "bold")
    text(300, 928, "add <?xpacket?> envelope around <x:xmpmeta>", 15, TXT, MONO)
    arrow(300, 804, 430, 866)
    arrow(880, 804, 750, 866)

    box(160, 1030, 860, 150, ORANGE, fill="#1f1608", sw=3)
    text(180, 1064, "originals\\2025\\2024-11-16\\", 17, ORANGE, MONO, "bold")
    text(180, 1096, "DSC02091.ARW   +   DSC02091.xmp", 21, TXT, MONO, "bold")
    text(180, 1128, "1,952 photos recovered this way — every edited photo included"
          if with_counts else "every edited photo is recovered this way", 14, DIM)
    arrow(590, 964, 590, 1026, "place beside the RAW", 700, 1002, ORANGE)

    # ---- footer: fallbacks ----
    box(40, 1210, 1100, 84, RED, dash="7 5", sw=1.6)
    text(60, 1238, "fallback joins (same sha space / different chains)", 14, RED, MONO, "bold")
    text(60, 1266, "externalDevelopSettings.docId→sha256 · versions.docId→assetId · localAuxTracker.digest → auxiliary\\ zlib", 14, DIM, MONO)

    S.append("</svg>")
    return "\n".join(S)

def render(svg_text, png_path):
    svg_path = png_path[:-4] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_text)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "shot.png")
        subprocess.run([EDGE, "--headless=new", f"--screenshot={out}",
                        f"--window-size={W},{H}", "--force-device-scale-factor=1",
                        "--default-background-color=00000000",
                        "file:///" + svg_path.replace("\\", "/")],
                       check=True, capture_output=True, timeout=90)
        import shutil; shutil.copy(out, png_path)
    print("written:", svg_path)
    print("written:", png_path)

render(build(with_counts=True),  os.path.join(OUT, "wfindex-settings-join.png"))
render(build(with_counts=False), os.path.join(OUT, "wfindex-settings-join-plain.png"))
