r"""Structure diagrams of Managed Catalog.wfindex — two variants:

  wfindex-structure.png/.svg        detailed, with row counts (worked example)
  wfindex-structure-plain.png/.svg  simplified overview, no counts

PNGs via headless Edge. Run:  python scripts/make_wfindex_diagram.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
EDGE = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1560, 1030
BG, PANEL, EDGE_ = "#0d1117", "#161b22", "#30363d"
TXT, DIM = "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, GRAY = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#7A8899"
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', sans-serif"

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build(with_counts=True):
    S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="{SANS}">',
         f'<rect width="{W}" height="{H}" fill="{BG}"/>']

    def box(x, y, w, h, border, fill=PANEL, rx=14, dash="", sw=2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

    def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
        S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
                 f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

    text(40, 52, "Managed Catalog.wfindex — internal structure", 30, TXT, SANS, "bold")
    sub = "62 SQLite tables · " + ("31 populated · " if with_counts else "") + \
          "derived from the sync stream (mcat is the source of truth)"
    text(40, 82, sub, 15, DIM, MONO)

    # ---------------- critical panel ----------------
    box(40, 110, 930, 500, ORANGE)
    text(60, 144, "RECOVERY-CRITICAL TABLES", 15, ORANGE, SANS, "bold")
    text(60, 168, "the seven that carry every join the toolkit needs", 14, DIM)

    crit = [
        ("assets", "assetId · filename · captureDate · rating · flag", "1,991", "the photo's identity — pivot of every join"),
        ("assetPathsAndInfo", "docId (= assetId!) · fileName · originalRelativePath", "1,998", "where the RAW lives on disk"),
        ("versions", "docId · assetId — one row per edit", "1,459", "which photos are edited"),
        ("externalDevelopSettings", "docId · sha256", "3,457", "edit-blob references (same shas as settings\\)"),
        ("purgeCandidates", "assetId · binaryType · contentIdOrSha256 · hasLocalFile · dateLastUpdated", "12,856", "THE master index: photo ↔ blob — XMPs and mask rasters"),
        ("localAuxTracker", "docId · digest", "10,461", "digest chain → auxiliary\\ payloads"),
        ("presetsAndProfiles", "docId · name", "235", "preset names for cr_settings\\"),
    ]
    y = 190
    for name, cols, n, why in crit:
        box(56, y, 898, 56, "#30363d", fill="#0e1420", rx=10)
        text(72, y + 24, name, 16, ORANGE, MONO, "bold")
        text(72, y + 44, cols, 13, DIM, MONO)
        if with_counts:
            text(938, y + 24, n, 15, TXT, MONO, "bold", "end")
        text(938, y + 44, why, 12.5, DIM, SANS, "normal", "end")
        y += 62

    # ---------------- key-space panel ----------------
    box(1000, 110, 520, 500, PURPLE)
    text(1020, 144, "TWO KEY SPACES  (+ one trap)", 15, PURPLE, SANS, "bold")

    box(1020, 164, 480, 120, "#30363d", fill="#0e1420", rx=10)
    text(1036, 192, "assetId", 16, BLUE, MONO, "bold")
    text(1036, 216, "32-hex · one per photo", 13.5, DIM, MONO)
    text(1036, 240, "assets.assetId — and ⚠ assetPathsAndInfo.docId holds these", 12.5, DIM)
    text(1036, 266, "proxies\\2560\\ folders are sharded by it", 12.5, DIM)

    box(1020, 296, 480, 120, "#30363d", fill="#0e1420", rx=10)
    text(1036, 324, "docId", 16, GREEN, MONO, "bold")
    text(1036, 348, "32-hex · one per document", 13.5, DIM, MONO)
    text(1036, 372, "versions · purgeCandidates · localAuxTracker", 12.5, DIM)
    text(1036, 396, "externalDevelopSettings — no single table covers all", 12.5, DIM)

    box(1020, 428, 480, 78, "#7A8899", fill="#0e1420", rx=10)
    text(1036, 454, "assets.docId — INTEGER row id", 15, "#ff7b72", MONO, "bold")
    text(1036, 476, "a different space entirely — the classic silent-join trap", 12.5, DIM)
    text(1036, 498, "(length() also lies on binary TEXT columns)", 12.5, DIM)

    box(1020, 520, 480, 72, PURPLE, fill="#0e1420", rx=10)
    text(1036, 546, "self-describing schema", 14, PURPLE, MONO, "bold")
    text(1036, 568, "PRAGMA table_info reveals every column —", 12.5, DIM)
    text(1036, 586, "how this whole map was established", 12.5, DIM)

    # ---------------- satellite panels ----------------
    def sat(x, w, title, color, rows):
        box(x, 640, w, 200, color)
        text(x + 20, 670, title, 14, color, SANS, "bold")
        yy = 696
        for item in rows:
            name, n = item
            text(x + 20, yy, name, 13.5, TXT, MONO)
            if with_counts:
                text(x + w - 20, yy, n, 13, DIM, MONO, "normal", "end")
            yy += 24

    sat(40, 480, "IDENTITY & FILES", BLUE, [
        ("mediaTypes", "3,982"), ("importSource", "1,991"),
        ("cameras · cameraModelsInUse", "1,991"),
        ("extensions", "1,991"), ("locations", "516"),
        ("asset_sync_local_file_type_ui", "1,998"),
    ])
    sat(550, 480, "DATES — precomputed calendar buckets", GREEN, [
        ("captureDate", "1,991"), ("importTime", "1,991"),
        ("modifiedTime", "1,991"), ("editedDate (isEdited)", "1,230"),
    ])
    sat(1060, 460, "SYNC & CACHE STATE", PURPLE, [
        ("asset_sync_status_ui", "7,992"), ("auxReferenceTracker", "10,461"),
        ("localStatusAndOzStatus", "3,457"), ("assetReferredCameraProfile", "975"),
        ("trashAssets · indexStatus · localState", "7/58/3"),
        ("schemaVersion", "1"),
    ])

    # ---------------- empty tables strip ----------------
    box(40, 870, 1480, 110, GRAY, dash="7 5", sw=1.6)
    text(60, 898, ("31 " if with_counts else "") + "EMPTY TABLES — schema scaffolding for features never used", 14, GRAY, SANS, "bold")
    text(60, 922, "albums · album_asset_v2 · smart_albums · project_albums · space · space_album · space_user · spaceRelatives ·", 13, DIM, MONO)
    text(60, 944, "spacefavorite · keywords · faces · person · comment · stacks · stack_assets · conflicts · errors · watermark · quota_exceeded …", 13, DIM, MONO)
    text(60, 964, "their presence still teaches the schema's shape — empty tables name the features Adobe plans or syncs lazily", 12, DIM)

    S.append("</svg>")
    return "\n".join(S)

def build_simple():
    """Simplified overview: the 7 tables that matter + key spaces, nothing else."""
    WS, HS = 1160, 660
    S = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WS}" height="{HS}" '
         f'viewBox="0 0 {WS} {HS}" font-family="{SANS}">',
         f'<rect width="{WS}" height="{HS}" fill="{BG}"/>']

    def box(x, y, w, h, border, fill=PANEL, rx=14, dash="", sw=2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
                 f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

    def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
        S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
                 f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

    text(40, 52, "Managed Catalog.wfindex — the 7 tables that matter", 30, TXT, SANS, "bold")
    text(40, 82, "62 tables total · all of it derived, rebuildable data — the mcat document store is the source of truth", 15, DIM)

    # ---- left: the seven ----
    box(40, 110, 660, 440, ORANGE)
    text(60, 144, "RECOVERY-CRITICAL", 14, ORANGE, SANS, "bold")
    seven = [
        ("assets", "the photo's identity"),
        ("assetPathsAndInfo", "where the RAW lives on disk"),
        ("versions", "which photos are edited"),
        ("purgeCandidates", "photo ↔ sha ↔ on-disk flag — the master index"),
        ("externalDevelopSettings", "edit-blob references"),
        ("localAuxTracker", "mask-raster & aux digests"),
        ("presetsAndProfiles", "preset names"),
    ]
    y = 166
    for name, role in seven:
        box(56, y, 628, 48, "#30363d", fill="#0e1420", rx=10)
        hl = name == "purgeCandidates"
        text(72, y + 30, name, 17, ORANGE if hl else TXT, MONO, "bold")
        text(672, y + 30, role, 13.5, DIM, SANS, "normal", "end")
        y += 54

    # ---- right: key spaces ----
    box(730, 110, 390, 440, PURPLE)
    text(750, 144, "KEY SPACES", 14, PURPLE, SANS, "bold")

    box(750, 162, 350, 92, "#30363d", fill="#0e1420", rx=10)
    text(766, 190, "assetId", 17, BLUE, MONO, "bold")
    text(766, 214, "one per photo — pivot of every join", 13.5, DIM)
    text(766, 236, "⚠ assetPathsAndInfo.docId holds these", 12.5, DIM)

    box(750, 266, 350, 92, "#30363d", fill="#0e1420", rx=10)
    text(766, 294, "docId", 17, GREEN, MONO, "bold")
    text(766, 318, "one per document (edit, preset, aux ref)", 13.5, DIM)
    text(766, 340, "versions · purgeCandidates · localAuxTracker", 12.5, DIM)

    box(750, 370, 350, 66, "#7A8899", fill="#0e1420", rx=10)
    text(766, 394, "assets.docId — INTEGER row id", 14.5, "#ff7b72", MONO, "bold")
    text(766, 418, "a third, unrelated space — the silent-join trap", 12.5, DIM)

    box(750, 448, 350, 82, PURPLE, fill="#0e1420", rx=10)
    text(766, 476, "self-describing schema", 14, PURPLE, MONO, "bold")
    text(766, 500, "PRAGMA table_info reveals every", 12.5, DIM)
    text(766, 520, "column — how this map was made", 12.5, DIM)

    # ---- bottom: everything else ----
    box(40, 574, 1080, 62, GRAY, dash="6 4", sw=1.6)
    text(60, 600, "the other 55 tables — derived search indexes (dates, ratings, cameras) · sync state · 31 empty scaffolding tables", 14.5, DIM)
    text(60, 624, "(albums · faces · keywords · stacks … present but unused — their names still teach the schema's shape)", 12.5, DIM)

    S.append("</svg>")
    return "\n".join(S)

def render(svg_text, png_path):
    svg_path = png_path[:-4] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_text)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "shot.png")
        w = svg_text.split('width="', 1)[1].split('"', 1)[0]
        h = svg_text.split('height="', 1)[1].split('"', 1)[0]
        subprocess.run([EDGE, "--headless=new", "--user-data-dir=" + os.path.join(td, "prof"),
                    f"--screenshot={out}",
                        f"--window-size={w},{h}", "--force-device-scale-factor=1",
                        "--default-background-color=00000000",
                        "file:///" + svg_path.replace("\\", "/")],
                       check=True, capture_output=True, timeout=90)
        import shutil; shutil.copy(out, png_path)
    print("written:", svg_path)
    print("written:", png_path)

render(build(with_counts=True), os.path.join(OUT, "wfindex-structure.png"))
render(build_simple(),        os.path.join(OUT, "wfindex-structure-plain.png"))
