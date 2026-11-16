r"""The .acr companion: anatomy + export/offline paths, as SVG + PNG.

The anatomy panel is read from the .acr you pass.
Writes docs/assets/acr-flow.svg + .png (Chrome/Edge headless).
Run:  python scripts/make_acr_flow_image.py <file.acr>
"""
import os, sys, subprocess, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acr_reader import read_table, classify  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("usage: make_acr_flow_image.py <file.acr>")
ACR = sys.argv[1]
DATA = open(ACR, "rb").read()
_, FMT, RESERVED, ENTRIES = read_table(DATA)
N = len(ENTRIES)
KINDS = [classify(DATA[o:o + s])[0] for _, s, o in ENTRIES]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "docs", "assets")
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

W, H = 1240, 1500
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
     'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
     f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{TXT}"/></marker></defs>']

def box(x, y, w, h, border, fill=PANEL, rx=14, dash="", sw=2):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    S.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
             f'fill="{fill}" stroke="{border}" stroke-width="{sw}"{d}/>')

def text(x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start"):
    S.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
             f'font-family="{font}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')

def arrow(x1, y1, x2, y2, color=TXT, label=None, lx=None, ly=None):
    S.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
             f'stroke-width="2" marker-end="url(#arr)"/>')
    if label:
        text(lx, ly, label, 13.5, color, MONO, "bold", "middle")

text(40, 52, "The .acr companion — anatomy and both paths", 28, TXT, SANS, "bold")
text(40, 82, "reverse-engineered (§6.8) · reader: scripts/acr_reader.py · counts from the real export", 14.5, DIM)

# ---------- panel A: anatomy ----------
box(40, 110, 1160, 560, ORANGE)
name = os.path.basename(ACR)
text(60, 142, f"ANATOMY — byte map ({name}, {len(DATA):,} bytes, {N} records; same layout in 77 files)", 15, ORANGE, SANS, "bold")
hx = lambda a, b: " ".join(f"{x:02x}" for x in DATA[a:b])
n_raster, n_zlib = KINDS.count("raster"), KINDS.count("zlib")
rows = [
    ("0x00", hx(0, 4), 'magic "ACR\\0"', DIM),
    ("0x04", hx(4, 8), "version = 1", DIM),
    ("0x08", hx(8, 12), f'source-format tag "{FMT}\\0"', DIM),
    ("0x0C", hx(12, 16), f"N = {N} records · then u32 {RESERVED} (reserved)", ORANGE),
    ("0x14", f"{N} × 32 B", "record table, sorted by md5: md5[16] | u64 size | u64 offset", BLUE),
    ("", "           ", "md5 = crs:MaskDigest / crs:pm_patch* / crs:IngestInfo in the XMP", BLUE),
    (f"0x{20 + 32 * N:X}", "record 0", "at 20 + 32×N; records 4-byte aligned, located via the table", TXT),
    ("", f"{n_raster} raster", "16-byte signature 02 00 00 00 01 00 00 00 + 8×00, then a JPEG-XL TIFF", GREEN),
    ("", f"{n_zlib} zlib", "u32 inflated length + zlib: a 12-byte frame + XMP packet (the receipt)", ORANGE),
]
y = 170
for off, what, desc, col in rows:
    text(80, y, off, 14.5, PURPLE, MONO, "bold")
    text(150, y, what, 14.5, col, MONO, "bold")
    text(330, y, desc, 13.5, DIM)
    y += 30
text(80, y + 6, "TIFFs: single-channel grayscale (some 3-channel 16-bit) · compression tag 52546 = JPEGXL_DNG", 13.5, DIM, MONO)
text(80, y + 30, "→ PIL refuses them; decode with tifffile + imagecodecs · each raster cropped to its mask, placed by XMP Origin", 13.5, DIM)

# ---------- panel B: two paths ----------
box(40, 700, 1160, 700, EDGE_)
text(60, 732, "TWO WAYS TO GET THE MASK RASTERS", 15, DIM, SANS, "bold")

# export path (left)
box(70, 760, 540, 150, GREEN)
text(90, 792, "cloud export path", 16, GREEN, SANS, "bold")
text(90, 820, "Lightroom \u201coriginal + settings\u201d export", 14, TXT)
text(90, 846, "manufactures the container on the fly —", 13.5, DIM)
text(90, 870, "full fidelity, straight from the cloud", 13.5, DIM)

box(70, 960, 540, 170, GREEN, fill="#0e1a10", sw=3)
text(90, 992, "the export trio", 15, GREEN, SANS, "bold")
text(90, 1020, "DSCxxxxx.ARW   the pixels", 15, TXT, MONO)
text(90, 1048, "DSCxxxxx.xmp   the recipe (bare, no envelope)", 15, TXT, MONO)
text(90, 1076, "DSCxxxxx.acr   the mask molds — real container", 15, GREEN, MONO, "bold")
text(90, 1106, "written iff the edit has AI masks (84/84 sidecars checked)", 13.5, DIM)
arrow(340, 914, 340, 954, GREEN)

# offline path (right)
box(640, 760, 540, 150, PURPLE)
text(660, 792, "offline path (lockout)", 16, PURPLE, SANS, "bold")
text(660, 820, "auxiliary\\ store — 4,504 type-02 rasters", 14, TXT, MONO)
text(660, 846, "already on disk; never packaged as .acr", 13.5, DIM)

box(640, 960, 540, 120, PURPLE)
text(660, 992, "purgeCandidates aux rows", 15, PURPLE, MONO, "bold")
text(660, 1020, "digest + assetId — the join needs no other table", 13.5, DIM)
text(660, 1048, "08_assemble_mask_rasters.py", 14.5, TXT, MONO, "bold")
arrow(910, 914, 910, 954, PURPLE)

box(640, 1130, 540, 190, PURPLE, fill="#171021", sw=3)
text(660, 1162, "functional equivalent", 15, PURPLE, SANS, "bold")
text(660, 1190, "mask-rasters\\<date>_<RAW>_<n>.tif  (4,448 attributed", 14, TXT, MONO)
text(660, 1216, "across 1,219 photos)", 13.5, DIM)
text(660, 1246, "                     + decoded .png   (100%)", 14, TXT, MONO)
text(660, 1276, "same records, different boxing —", 13.5, DIM)
text(660, 1298, "only the .acr box is made at export time", 13.5, DIM)
arrow(910, 1084, 910, 1124, PURPLE)

# footer
box(70, 1430, 1100, 46, GRAY, dash="6 4", sw=1.5)
text(90, 1459, "read any .acr yourself:  python scripts/acr_reader.py <file.acr> --png   → dumps records, extracts viewable rasters", 14, DIM, MONO)

S.append("</svg>")
SVG = os.path.join(OUT, "acr-flow.svg")
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
    import shutil; shutil.copy(out, os.path.join(OUT, "acr-flow.png"))
print("written:", SVG)
print("written:", os.path.join(OUT, "acr-flow.png"))
