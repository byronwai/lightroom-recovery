r"""Round 2: tile-normalized correlation + crop tolerance for unnamed edited JPEGs."""
import os, glob, io, csv, shutil
import numpy as np
from PIL import Image, ImageOps

from common import get_paths
_p = get_paths("Round-2 crop-tolerant matching for edited JPEGs")
WORK, DATA, OUT = _p.work, _p.data, _p.out
SZ = 32

def S(x): return x.decode('utf-8','replace') if isinstance(x, bytes) else x
def K(x): return str(S(x))

import sqlite3
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

def tile_norm(a, tiles=4):
    h, w = a.shape
    out = np.empty_like(a)
    for ti in range(tiles):
        for tj in range(tiles):
            ys, ye = ti*h//tiles, (ti+1)*h//tiles
            xs, xe = tj*w//tiles, (tj+1)*w//tiles
            t = a[ys:ye, xs:xe]
            out[ys:ye, xs:xe] = (t - t.mean()) / (t.std() + 1e-6)
    return out

def thumb(img_bytes, crop=None):
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("L")
        im = ImageOps.exif_transpose(im)
        if crop:  # (l,t,r,b) fractions
            W, H = im.size
            im = im.crop((int(W*crop[0]), int(H*crop[1]), int(W*crop[2]), int(H*crop[3])))
        im = im.resize((SZ, SZ))
        return tile_norm(np.asarray(im, dtype=np.float32))
    except Exception:
        return None

# originals: full + center-crop variants
orig_full, orig_c70 = {}, {}
for aid, (fn, cap, p) in info.items():
    jb = extract_embedded_jpeg(p)
    if not jb: continue
    t = thumb(jb)
    if t is not None: orig_full[aid] = t
    t2 = thumb(jb, crop=(0.15, 0.15, 0.85, 0.85))
    if t2 is not None: orig_c70[aid] = t2
print("original thumbs:", len(orig_full))

idsF = list(orig_full)
MF = np.stack([orig_full[i] for i in idsF]).reshape(len(idsF), -1)
idsC = list(orig_c70)
MC = np.stack([orig_c70[i] for i in idsC]).reshape(len(idsC), -1)

already = set()
mapfile = os.path.join(OUT, "edited-jpg-map.csv")
if os.path.exists(mapfile):
    with open(mapfile, newline="", encoding="utf-8-sig") as f:
        already = {r[0] for r in csv.reader(f) if r and r[0] != "file"}
baa_all = [p for p in glob.glob(os.path.join(WORK, "previews", "*", "*")) if p.endswith("baa")]
# which ones did round1 name? match by size/hash via mapfile->edited-jpg folder
named_stems = set()
for fn in already:
    # find baa whose copy equals the named file
    pass

# simpler: redo all, but skip those whose bytes already exist in edited-jpg
named_bytes = set()
for fn in already:
    p = os.path.join(OUT, "edited-jpg", fn)
    if os.path.exists(p): named_bytes.add(open(p, "rb").read()[:65536])

new_rows = []
n2 = 0
for p in baa_all:
    head = open(p, "rb").read()[:65536]
    if head in named_bytes: continue
    t = thumb(open(p, "rb").read())
    if t is None: continue
    v = t.flatten()
    sF = MF @ v / (SZ*SZ)
    sC = MC @ v / (SZ*SZ)
    # combine: best of full/center per asset
    comb = {}
    for i, aid in enumerate(idsF): comb[aid] = sF[i]
    for i, aid in enumerate(idsC): comb[aid] = max(comb.get(aid, -9), sC[i])
    ranked = sorted(comb.items(), key=lambda kv: -kv[1])
    (b_id, b_s), (s_id, s_s) = ranked[0], ranked[1]
    if b_s > 0.30 and b_s - s_s > 0.06:
        fn, cap, _ = info[b_id]
        dst_name = f"{cap[:10]}_{os.path.splitext(fn)[0]}.jpg"
        dst = os.path.join(OUT, "edited-jpg", dst_name)
        k = 1
        while os.path.exists(dst):
            dst_name = f"{cap[:10]}_{os.path.splitext(fn)[0]}_{k}.jpg"
            dst = os.path.join(OUT, "edited-jpg", dst_name); k += 1
        shutil.copy2(p, dst)
        new_rows.append((dst_name, b_id, round(float(b_s), 3)))
        n2 += 1
print("round2 named:", n2)
with open(mapfile, "a", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows(new_rows)
