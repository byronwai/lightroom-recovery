r"""Graphical block diagram of the Lightroom (cloud) local data layout.

Emits TWO variants from one source:
  docs/assets/lightroom-cc-layout.png/.svg        with sizes & counts (worked example)
  docs/assets/lightroom-cc-layout-plain.png/.svg  library-agnostic, no sizes/counts

PNGs are rendered via headless Edge (SVG is the single source of truth).
Run:  python scripts/make_layout_diagram.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
EDGE = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1560, 1060
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, RED, PURPLE = "#58a6ff", "#ffa657", "#7ee787", "#ff7b72", "#d2a8ff"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build(with_counts=True):
    S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{SANS}">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>']

    def box(x, y, w, h, border, fill=PANEL, rx=14, dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill}" stroke="{border}" stroke-width="2"{d}/>')

    def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
        S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
                 f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

    def arrow(x1, y1, x2, y2, color=DIM, label=None, lx=None, ly=None, dash="4 4"):
        S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
                 f'stroke-width="1.6" stroke-dasharray="{dash}" marker-end="url(#arr)"/>')
        if label:
            text(lx, ly, label, 13, color, MONO, "normal", "middle")

    S.append(f'''<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
     markerWidth="7" markerHeight="7" orient="auto-start-reverse">
     <path d="M 0 0 L 10 5 L 0 10 z" fill="{DIM}"/></marker></defs>''')

    # ---------- title ----------
    text(40, 52, "Adobe Lightroom (cloud) — local data layout", 30, TXT, SANS, "bold")
    sub = ("%LOCALAPPDATA%\\Adobe\\Lightroom CC\\Data\\<catalog-guid>\\  ·  "
           + ("sizes/counts from the recovered library" if with_counts
              else "library-agnostic — sizes and counts vary per library"))
    text(40, 80, sub, 15, DIM, MONO)

    # ---------- panel A: databases ----------
    box(40, 110, 1480, 190, EDGE_)
    text(60, 142, "CATALOG DATABASES  (SQLite — unencrypted, plain files)", 14, DIM, SANS, "bold")

    box(70, 160, 430, 120, "#7A8899")
    text(90, 194, "Managed Catalog.mcat", 19, TXT, MONO, "bold")
    text(90, 222, "document store (docs + revs)" + ("  ·  160 MB" if with_counts else ""), 14, DIM)
    text(90, 246, "Adobe-flavored CBOR · sync source of truth", 14, DIM)

    box(530, 160, 360, 120, ORANGE)
    text(550, 194, "Managed Catalog.wfindex", 19, ORANGE, MONO, "bold")
    text(550, 222, "~60 plain SQL tables" + ("  ·  36 MB" if with_counts else ""), 14, TXT)
    text(550, 246, "assets · versions · purgeCandidates …", 14, DIM, MONO)

    box(920, 160, 300, 120, "#7A8899", dash="6 4")
    text(940, 194, "notifdb · mru", 17, DIM, MONO, "bold")
    text(940, 222, "notifications, recent-use", 14, DIM)
    text(940, 246, "ignorable", 14, DIM)

    box(1250, 160, 250, 120, "#7A8899")
    text(1270, 194, "cullingScores.db", 17, DIM, MONO, "bold")
    text(1270, 222, "AI culling scores", 14, DIM)
    text(1270, 246, "auto-maintained" if not with_counts else "2.9 MB", 14, DIM)

    WFX, WFY = 810, 280

    # ---------- panel B: content stores ----------
    box(40, 440, 1480, 470, EDGE_)
    text(60, 472, "CONTENT STORES  (plain files, content-addressed)", 14, DIM, SANS, "bold")

    def store(x, y, w, h, title, count, scheme, desc, color, key=None):
        box(x, y, w, h, color)
        text(x + 18, y + 34, title, 21, color, MONO, "bold")
        text(x + 18, y + 64, count, 16, TXT)
        text(x + 18, y + 92, scheme, 14, DIM, MONO)
        for i, ln in enumerate(desc):
            text(x + 18, y + 120 + i * 22, ln, 14, DIM)
        if key:
            box(x + 14, y + h - 40, w - 28, 28, color, fill="#21262d", rx=8)
            text(x + 26, y + h - 21, key, 13.5, color, MONO)

    cw, ch, gx, gy = 470, 190, 24, 30
    x0, y0 = 64, 490
    cells = [
        ("originals\\",
         "1,692 RAWs · 64 GB" if with_counts else "your original RAW files",
         "<year>\\<capture-date>\\DSCxxxxx.ARW",
         ["second copy of your own files", "grouped by shoot date",
          "0000\\0000-00-00 = unknown date"], BLUE, None),
        ("settings\\",
         "2,648 develop XMPs" if with_counts else "per-photo develop XMPs",
         "<64-hex sha256> · no extension",
         ["THE edit store — every edit Adobe", "downloaded, bare <x:xmpmeta>,",
          "current + superseded revisions"], ORANGE, None),
        ("previews\\",
         "5,530 rendered JPEGs" if with_counts else "rendered JPEG previews",
         "<2-hex shard>\\<key><suffix>",
         ["edits baked into the pixels", "afa 320px · ama 640px",
          "baa 2048px = the keepers"], GREEN, None),
        ("auxiliary\\",
         "4,734 files · 2,801 shards" if with_counts else "mask rasters + zlib XMP payloads",
         "<digest[:3]>\\<digest[3:]>",
         (["mask rasters (TIFF) + 31 zlib XMPs", "(23 Generative Remove",
           "· 8 redundant develop)"] if with_counts else
          ["mask rasters (TIFF) + zlib XMPs", "(incl. Generative Remove records,",
           "redundant develop copies)"]), PURPLE, "key: digest · localAuxTracker"),
        ("proxies\\",
         "318 DNG stand-ins" if with_counts else "2560 px DNG stand-ins",
         "2560\\<assetId[:3]>\\<assetId[3:]>",
         ["2560 px · UNEDITED", "no matching needed"], BLUE, "key: assetId (direct)"),
        ("cr_settings\\",
         "234 ACR presets" if with_counts else "user preset files",
         "<preset-docId>.xmp",
         ["real names via presetsAndProfiles", "genuine Camera Raw format,",
          "import as-is"], GREEN, "key: preset docId"),
    ]
    for i, (t, c, sc, d, col, key) in enumerate(cells):
        x = x0 + (i % 3) * (cw + gx)
        y = y0 + (i // 3) * (ch + gy)
        store(x, y, cw, ch, t, c, sc, d, col, key=key)

    # ---------- join-key arrows (row 1 only; row 2 uses key chips) ----------
    for x2, y2, label, lx, ly, col in [
        (300, 490, "originalRelativePath", 240, 430, BLUE),
        (810, 490, "contentIdOrSha256  (binaryType='xmp_develop')", 810, 430, ORANGE),
        (1320, 490, "no mapping — perceptual matching", 1290, 430, GREEN),
    ]:
        arrow(WFX, WFY, x2, y2, col, label, lx, ly)

    # ---------- panel C: traps ----------
    box(40, 940, 1480, 90, RED, dash="8 5")
    text(60, 968, "RED HERRINGS", 14, RED, SANS, "bold")
    text(60, 996, "xmp\\  " + ("2,570 shard folders — " if with_counts else "")
         + "transient download bay, empty between syncs", 15, DIM, MONO)
    text(860, 996, "big_table_cache\\  empty  ·  cr_cameraprofiles\\  profiles ship with the app", 15, DIM, MONO)

    S.append("</svg>")
    return "\n".join(S)

def render(svg_text, png_path):
    svg_path = png_path[:-4] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_text)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "shot.png")
        subprocess.run([EDGE, "--headless=new", "--user-data-dir=" + os.path.join(td, "prof"),
                    f"--screenshot={out}",
                        f"--window-size={W},{H}", "--force-device-scale-factor=1",
                        "--default-background-color=00000000",
                        "file:///" + svg_path.replace("\\", "/")],
                       check=True, capture_output=True, timeout=90)
        import shutil; shutil.copy(out, png_path)
    print("written:", svg_path)
    print("written:", png_path)

render(build(with_counts=True),  os.path.join(OUT, "lightroom-cc-layout.png"))
render(build(with_counts=False), os.path.join(OUT, "lightroom-cc-layout-plain.png"))
