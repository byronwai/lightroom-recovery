r"""Assemble per-photo mask rasters from the auxiliary store (offline .acr).

Background: Lightroom's "original + settings" export emits a third
companion, <name>.acr — a container of the photo's mask rasters (the
type-02 records that also live in auxiliary\\). That file is manufactured
at export time and never exists in the cache, so a locked-out user can't
recover the .acr itself — but the PAYLOAD can be re-assembled offline:
purgeCandidates' aux rows carry digest AND assetId directly, and every
type-02 record is a 16-byte header followed by a self-contained TIFF.

Output:
  mask-rasters\\<capture-date>_<RAW stem>_<n>.tif   one TIFF per mask raster
  mask-rasters\\..._<n>.png                          decoded viewable copy
                                                     (needs: pip install tifffile imagecodecs —
                                                      the rasters are JPEG-XL tiled TIFFs,
                                                      compression tag 52546 = JPEGXL_DNG)
  mask-rasters\\_unlinked\\<digest>.tif              rasters no table can link

The TIFFs/PNGs are grayscale single-channel selections — forensic/archival
artifacts, not importable settings; the parametric masks live in the XMPs.

Run:  python 08_assemble_mask_rasters.py [--data ...] [--work ...] [--out ...]
"""
import os, glob, sqlite3, collections
from common import get_paths

_p = get_paths("Assemble per-photo mask rasters from the auxiliary store")
DATA, WORK, OUT = _p.data, _p.work, _p.out
MDIR = os.path.join(OUT, "mask-rasters")

def S(x): return x.decode('utf-8', 'replace') if isinstance(x, bytes) else x

wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex"))
wfx.text_factory = bytes

assets = {S(a): (S(f), S(c)) for a, f, c in
          wfx.execute("SELECT assetId, filename, captureDate FROM assets")}

# primary: purge aux rows carry the digest (contentId) AND assetId directly
dig2asset = {}
for cid, aid in wfx.execute(
        """SELECT contentIdOrSha256, assetId FROM purgeCandidates
           WHERE binaryType='aux' AND contentIdOrSha256 IS NOT NULL
             AND assetId IS NOT NULL"""):
    dig2asset.setdefault(S(cid).upper(), S(aid))

# fallback: localAuxTracker digest -> docId -> assetId (any binaryType / versions)
doc2asset = {}
for doc, aid in wfx.execute("SELECT docId, assetId FROM versions"): doc2asset[S(doc)] = S(aid)
for doc, aid in wfx.execute("SELECT DISTINCT docId, assetId FROM purgeCandidates"):
    doc2asset.setdefault(S(doc), S(aid))
dig2docs = collections.defaultdict(list)
for doc, dg in wfx.execute("SELECT docId, digest FROM localAuxTracker"):
    dig2docs[S(dg).upper()].append(S(doc))

def write_if_changed(path, data):
    if os.path.exists(path) and open(path, 'rb').read() == data:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return path

try:
    import numpy as np
    import tifffile
    from PIL import Image
    def to_png(tif_path):
        png = tif_path[:-4] + ".png"
        if os.path.exists(png):
            return True
        a = tifffile.imread(tif_path)
        if a.ndim == 3:                       # some rasters are 3-channel
            a = a[..., 0]
        if a.dtype != np.uint8:
            mx = int(a.max())
            a = (a * (255 // max(1, mx))).astype(np.uint8) if mx else a.astype(np.uint8)
        Image.fromarray(a).save(png)
        return True
except ImportError:
    to_png = None

os.makedirs(MDIR, exist_ok=True)
per_photo = collections.Counter()
linked = unlinked = notype = pngs = 0
for p in glob.glob(os.path.join(DATA, "auxiliary", "*", "*")):
    with open(p, 'rb') as f:
        head = f.read(16)
    if len(head) < 16 or head[:4] != b'\x02\x00\x00\x00':
        continue                                        # not a type-02 raster
    notype += 1
    raw = open(p, 'rb').read()
    tiff = raw[16:]
    if tiff[:4] not in (b'II*\x00', b'MM\x00*'):
        continue
    dg = (os.path.basename(os.path.dirname(p)) + os.path.basename(p)).upper()
    aid = dig2asset.get(dg)
    if not aid:
        for doc in dig2docs.get(dg, []):
            cand = doc2asset.get(doc)
            if cand:
                aid = cand; break
    if aid and aid in assets:
        fn, cap = assets[aid]
        base = os.path.splitext(fn)[0]
        n = per_photo[aid]
        per_photo[aid] += 1
        out = write_if_changed(os.path.join(MDIR, f"{cap[:10]}_{base}_{n:02d}.tif"), tiff)
        try:
            if to_png and to_png(out): pngs += 1
        except Exception:
            pass                                     # keep the .tif regardless
        linked += 1
    else:
        write_if_changed(os.path.join(MDIR, "_unlinked", dg + ".tif"), tiff)
        unlinked += 1

print(f"type-02 mask rasters found : {notype}")
print(f"  attributed to a photo     : {linked} across {len(per_photo)} photos")
print(f"  decoded to PNG            : {pngs}" + ("" if to_png else "  (tifffile/imagecodecs not installed)"))
print(f"  unlinked (orphan digests) : {unlinked}")
