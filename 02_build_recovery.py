r"""Build the recovery tree (<out>) from local Adobe Lightroom (cloud) data."""
import os, re, csv, glob, shutil, sqlite3, zlib, struct, sys
from common import get_paths

_paths = get_paths("Build the recovery tree from local Lightroom cloud data")
DATA, WORK, OUT = _paths.data, _paths.work, _paths.out

def S(x): return x.decode('utf-8','replace') if isinstance(x, bytes) else x

wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex"))
wfx.text_factory = bytes

# ---------- 1. asset metadata ----------
assets = {}  # assetId -> dict
for r in wfx.execute("""SELECT a.assetId, a.filename, a.captureDate, a.rating, a.flag,
                               a.width, a.height, a.subtype FROM assets a"""):
    assets[S(r[0])] = dict(filename=S(r[1]), capture=S(r[2]), rating=r[3], flag=r[4],
                           w=r[5], h=r[6], subtype=S(r[7]), albums=[], edited=False,
                           local_original=None, camera=None, dng=False, xmp=False, jpg=False)

for doc, cam in wfx.execute("SELECT docId, camera FROM cameras"):
    pass  # docId-space differs; cameras joined below via cameraModelsInUse docId==assets docId

# docId -> assetId for assets, then camera (try both id-spaces)
doc2asset = {}
for doc, aid in wfx.execute("SELECT docId, assetId FROM assets"):
    doc2asset[S(doc)] = S(aid)
for doc, cam in wfx.execute("SELECT docId, cameraModel FROM cameraModelsInUse"):
    for key in (S(doc), doc2asset.get(S(doc))):
        if key and key in assets and not assets[key]["camera"]:
            assets[key]["camera"] = S(cam)

# ---------- 2. albums (empty in this catalog, skipped) ----------

# ---------- 3. edited (versions) ----------
n_ed = 0
for (aid,) in wfx.execute("SELECT DISTINCT assetId FROM versions"):
    aid = S(aid)
    if aid in assets:
        assets[aid]["edited"] = True; n_ed += 1
print("edited assets:", n_ed)

# ---------- 4. local originals (assetPathsAndInfo.docId holds the assetId) ----------
n_orig = 0
for r in wfx.execute("SELECT docId, fileName, originalRelativePath FROM assetPathsAndInfo"):
    aid = S(r[0]); rel = S(r[2])
    if not rel: continue
    m = re.search(r"originals[/\\](.*)$", rel.replace("\\", "/"))
    if not m: continue
    cand = os.path.join(DATA, "originals", m.group(1))
    if os.path.exists(cand) and aid in assets:
        assets[aid]["local_original"] = "originals/" + m.group(1)
        n_orig += 1
print("local originals matched:", n_orig)

# ---------- 5. proxies -> 2560px DNG stand-ins (unedited smart proxies, keyed by assetId) ----------
os.makedirs(os.path.join(OUT, "dng-proxies-2560"), exist_ok=True)
n_dng = 0
for aid, a in assets.items():
    p = os.path.join(DATA, "proxies", "2560", aid[:3], aid[3:])
    if os.path.exists(p):
        date = (a["capture"] or "")[:10]
        fn = os.path.splitext(a["filename"] or aid)[0]
        shutil.copy2(p, os.path.join(OUT, "dng-proxies-2560", f"{date}_{fn}.dng"))
        a["dng"] = True; n_dng += 1
print("2560px DNG proxies:", n_dng)

# ---------- 6. XMP sidecars from zlib aux payloads ----------
# digest -> file, docId -> digest
digest_file = {}
for p in glob.glob(os.path.join(DATA, "auxiliary", "*", "*")):
    dg = os.path.basename(os.path.dirname(p)) + os.path.basename(p)
    digest_file[dg.upper()] = p
doc_digest = {}
for doc, dg in wfx.execute("SELECT docId, digest FROM localAuxTracker"):
    doc_digest.setdefault(S(doc), []).append(S(dg).upper())
# version docId -> assetId
ver_doc2asset = {}
for doc, aid in wfx.execute("SELECT docId, assetId FROM versions"):
    ver_doc2asset[S(doc)] = S(aid)

os.makedirs(os.path.join(OUT, "xmp-sidecars", "_unmatched"), exist_ok=True)
n_xmp = 0
for doc, digs in doc_digest.items():
    aid = ver_doc2asset.get(doc)
    matched = False
    for dg in digs:
        p = digest_file.get(dg)
        if not p: continue
        raw = open(p, "rb").read()
        if raw[4:6] != b"\x78\x9c": continue
        try: xml = zlib.decompress(raw[4:])
        except Exception: continue
        i = xml.find(b"<x:xmpmeta"); j = xml.rfind(b"</x:xmpmeta>")
        if i == -1 or j == -1: continue
        packet = (b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
                  + xml[i:j+len(b"</x:xmpmeta>")] + b'\n<?xpacket end="w"?>')
        if aid and aid in assets:
            a = assets[aid]
            date = (a["capture"] or "")[:10]
            fn = os.path.splitext(a["filename"] or aid)[0]
            outp = os.path.join(OUT, "xmp-sidecars", f"{date}_{fn}.xmp")
            a["xmp"] = True; matched = True
        else:
            outp = os.path.join(OUT, "xmp-sidecars", "_unmatched", os.path.basename(p) + ".xmp")
        with open(outp, "wb") as f:
            f.write(packet)
        n_xmp += 1
    if matched is False and aid is None:
        pass
print("XMP sidecars written:", n_xmp)

# ---------- 7. 2048px edited JPEGs (previews, cache-key names) ----------
os.makedirs(os.path.join(OUT, "edited-jpg-unnamed"), exist_ok=True)
n_jpg = 0
for p in glob.glob(os.path.join(WORK, "previews", "*", "*")):
    if not p.endswith("baa"): continue
    shutil.copy2(p, os.path.join(OUT, "edited-jpg-unnamed", os.path.basename(p) + ".jpg"))
    n_jpg += 1
print("2048px edited JPEGs (unnamed):", n_jpg)

# ---------- 8. catalog backup ----------
os.makedirs(os.path.join(OUT, "catalog-backup"), exist_ok=True)
n_b = 0
for f in glob.glob(os.path.join(WORK, "Managed Catalog.*")):
    shutil.copy2(f, os.path.join(OUT, "catalog-backup", os.path.basename(f))); n_b += 1
for sub in ("previews", "proxies", "auxiliary", "xmp"):
    src = os.path.join(DATA, sub)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(OUT, "catalog-backup", sub), dirs_exist_ok=True)
print("catalog-backup files:", n_b, "+ cache folders")

# ---------- 8b. edited-jpg map from matcher ----------
jpgmap = os.path.join(OUT, "edited-jpg-map.csv")
if os.path.exists(jpgmap):
    import csv as _csv
    with open(jpgmap, newline="", encoding="utf-8-sig") as f:
        for row in _csv.reader(f):
            if row and row[1] in assets:
                assets[row[1]]["jpg"] = True

# ---------- 9. manifest ----------
with open(os.path.join(OUT, "manifest.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["filename", "captureDate", "camera", "rating", "flag", "albums",
                "edited", "localOriginalRecovered", "editedJpg2048", "xmpSidecar", "assetId"])
    for aid, a in sorted(assets.items(), key=lambda kv: (kv[1]["capture"] or "", kv[1]["filename"] or "")):
        w.writerow([a["filename"], a["capture"], a["camera"], a["rating"], a["flag"],
                    " | ".join(a["albums"]), "yes" if a["edited"] else "",
                    a["local_original"] or "", "yes" if a["jpg"] else "",
                    "yes" if a["xmp"] else "", aid])
print("manifest.csv rows:", len(assets))
print("\nDONE")
