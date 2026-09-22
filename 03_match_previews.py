r"""Name the 303 edited 2048px JPEGs by matching them to original ARW embedded previews."""
import os, glob, io, sqlite3
import numpy as np
from PIL import Image

from common import get_paths
_p = get_paths("Name edited JPEGs by strict image matching")
WORK, DATA, OUT = _p.work, _p.data, _p.out

def S(x): return x.decode('utf-8','replace') if isinstance(x, bytes) else x
def K(x): return str(S(x))

wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex"))
wfx.text_factory = bytes

# assetId -> (filename, capture, relative original path)
# NOTE: assetPathsAndInfo.docId actually holds the assetId (32-hex)
info = {}
for r in wfx.execute("SELECT docId, fileName, originalRelativePath FROM assetPathsAndInfo"):
    aid = K(r[0])
    rel = S(r[2]) or ""
    if "originals" not in rel: continue
    tail = rel.replace("\\", "/").split("originals/")[-1]
    p = os.path.join(DATA, "originals", tail)
    if os.path.exists(p):
        info[aid] = (S(r[1]) or aid, "", p)
# capture dates from assets table
for aid, cap in wfx.execute("SELECT assetId, captureDate FROM assets"):
    if K(aid) in info:
        f, _, p = info[K(aid)]
        info[K(aid)] = (f, S(cap) or "", p)
print("assets with local originals:", len(info))

def extract_embedded_jpeg(path):
    """Sony ARW: find the largest embedded JPEG."""
    best = None
    with open(path, "rb") as f:
        data = f.read()
    pos = 0
    starts = []
    while True:
        i = data.find(b"\xff\xd8\xff", pos)
        if i == -1: break
        starts.append(i); pos = i + 3
    for i in starts:
        e = data.find(b"\xff\xd9", i)
        if e == -1: continue
        seg = data[i:e+2]
        if len(seg) > 30000 and (best is None or len(seg) > len(best)):
            best = seg
    return best

def thumb(img_bytes, size=24):
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("L")
        # handle EXIF rotation
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception: pass
        im = im.resize((size, size))
        a = np.asarray(im, dtype=np.float32)
        a = (a - a.mean()) / (a.std() + 1e-6)
        return a
    except Exception:
        return None

# build original thumbs (cache)
orig_thumbs = {}
for aid, (fn, cap, p) in info.items():
    jb = extract_embedded_jpeg(p)
    if not jb: continue
    t = thumb(jb)
    if t is not None: orig_thumbs[aid] = t
print("original thumbs built:", len(orig_thumbs))
ids = list(orig_thumbs)
M = np.stack([orig_thumbs[i] for i in ids])

baa = [p for p in glob.glob(os.path.join(WORK, "previews", "*", "*")) if p.endswith("baa")]
print("baa jpegs:", len(baa))

os.makedirs(os.path.join(OUT, "edited-jpg"), exist_ok=True)
named = 0
map_rows = []
for p in baa:
    t = thumb(open(p, "rb").read())
    if t is None: continue
    v = t.flatten()
    scores = (M.reshape(len(ids), -1) @ v) / (M.shape[1]*M.shape[2])
    order = np.argsort(scores)[::-1]
    best, second = ids[order[0]], ids[order[1]]
    margin = scores[order[0]] - scores[order[1]]
    if scores[order[0]] > 0.45 and margin > 0.08:
        fn, cap, _ = info[best]
        date = cap[:10]
        base = os.path.splitext(fn)[0]
        dst_name = f"{date}_{base}.jpg"
        dst = os.path.join(OUT, "edited-jpg", dst_name)
        if os.path.exists(dst):
            dst_name = f"{date}_{base}_{os.path.basename(p)[:6]}.jpg"
            dst = os.path.join(OUT, "edited-jpg", dst_name)
        import shutil; shutil.copy2(p, dst)
        map_rows.append((dst_name, best, round(float(scores[order[0]]), 3)))
        named += 1
print("named:", named, "of", len(baa))
with open(os.path.join(OUT, "edited-jpg-map.csv"), "w", newline="", encoding="utf-8-sig") as f:
    import csv
    w = csv.writer(f); w.writerow(["file", "assetId", "score"]); w.writerows(map_rows)
