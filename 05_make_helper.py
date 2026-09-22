r"""Contact-sheet helper to identify the unnamed edited JPEGs visually."""
import os, glob, io, csv, base64, sqlite3, shutil
import numpy as np
from PIL import Image, ImageOps

from common import get_paths
_p = get_paths("Generate the match-helper.html contact sheet")
WORK, DATA, OUT = _p.work, _p.data, _p.out
SZ = 24

def S(x): return x.decode('utf-8','replace') if isinstance(x, bytes) else x
def K(x): return str(S(x))

wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex")); wfx.text_factory = bytes
info = {}
for r in wfx.execute("SELECT docId, fileName, originalRelativePath FROM assetPathsAndInfo"):
    aid = K(r[0]); rel = S(r[2]) or ""
    if "originals" not in rel: continue
    tail = rel.replace("\\", "/").split("originals/")[-1]
    p = os.path.join(DATA, "originals", tail)
    if os.path.exists(p): info[aid] = (S(r[1]) or aid, "", p)
for aid, cap in wfx.execute("SELECT assetId, captureDate FROM assets"):
    if K(aid) in info:
        f, _, p = info[K(aid)]
        info[K(aid)] = (f, S(cap) or "", p)

def extract_embedded_jpeg(path):
    data = open(path, "rb").read()
    pos = 0; best = None
    while True:
        i = data.find(b"\xff\xd8\xff", pos)
        if i == -1: break
        pos = i + 3
        e = data.find(b"\xff\xd9", i)
        if e == -1: continue
        seg = data[i:e+2]
        if len(seg) > 30000 and (best is None or len(seg) > len(best)): best = seg
    return best

def norm(a):
    return (a - a.mean()) / (a.std() + 1e-6)

def thumb_arr(img_bytes, size=SZ):
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes)).convert("L")).resize((size, size))
        return norm(np.asarray(im, dtype=np.float32))
    except Exception:
        return None

def b64_thumb(img_bytes, w=180):
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes)))
        im.thumbnail((w, w))
        buf = io.BytesIO(); im.convert("RGB").save(buf, "JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

ids = list(info)
arrs = {}
for aid in ids:
    jb = extract_embedded_jpeg(info[aid][2])
    if jb:
        t = thumb_arr(jb)
        if t is not None: arrs[aid] = (t, jb)
ids = list(arrs)
M = np.stack([arrs[i][0] for i in ids]).reshape(len(ids), -1)

# which baa are still unnamed?
named = {}
with open(os.path.join(OUT, "edited-jpg-map.csv"), newline="", encoding="utf-8-sig") as f:
    for r in csv.reader(f):
        if r and r[0] != "file": named[r[0]] = True
named_bytes = set()
for fn in named:
    p = os.path.join(OUT, "edited-jpg", fn)
    if os.path.exists(p): named_bytes.add(open(p, "rb").read()[:65536])

baa = [p for p in glob.glob(os.path.join(WORK, "previews", "*", "*")) if p.endswith("baa")]
rows_html = []
for p in baa:
    if open(p, "rb").read()[:65536] in named_bytes: continue
    data = open(p, "rb").read()
    t = thumb_arr(data)
    if t is None: continue
    v = t.flatten()
    scores = M @ v / (SZ*SZ)
    top = np.argsort(scores)[::-1][:3]
    cands = [(ids[i], float(scores[i])) for i in top]
    cells = [f'<div class="cell"><img src="data:image/jpeg;base64,{b64_thumb(data)}"><div class="lbl">EDITED (unnamed)</div></div>']
    for aid, s in cands:
        fn, cap, _ = info[aid]
        jb = arrs[aid][1]
        cells.append(f'<div class="cell"><img src="data:image/jpeg;base64,{b64_thumb(jb)}">'
                     f'<div class="lbl">{cap[:10]}_{os.path.splitext(fn)[0]} ({s:.2f})</div></div>')
    rows_html.append("<div class='row'>" + "".join(cells) + "</div>")

html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Match edited JPEGs</title>
<style>body{{background:#222;color:#ddd;font-family:sans-serif}}
.row{{display:flex;gap:8px;margin:10px 0;align-items:flex-start}}
.cell{{text-align:center}} .cell img{{height:160px;display:block;border:2px solid #555}}
.cell:first-child img{{border-color:#e05}} .lbl{{font-size:12px;margin-top:2px}}</style></head>
<body><h2>Left (red border) = edited JPEG &mdash; right = top-3 matching originals</h2>
<p>Rename the file in edited-jpg-unnamed to the correct name on the right (first suggestion is usually right; scores &gt; 0.5 are very likely correct).</p>
{''.join(rows_html)}</body></html>"""
with open(os.path.join(OUT, "match-helper.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("match-helper.html written with", len(rows_html), "rows")
