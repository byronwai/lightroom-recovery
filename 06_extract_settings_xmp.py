r"""Extract ALL per-photo develop XMPs from Data\settings\ and place each one
NEXT TO ITS ORIGINAL photo in the recovery tree.

Layout produced:
  originals\<year>\<date>\<DSCbase>.xmp          current edit (name = RAW name)
  originals\<year>\<date>\<DSCbase>_<sha6>.xmp    older edit revisions
  xmp-sidecars\<date>_<DSCbase>.xmp              photos with no recovered original
  xmp-sidecars\_unlinked\<sha256>.xmp            orphaned revisions (no asset link)

Sidecar naming rule: an XMP must share the EXACT base name of its photo
(DSC02108.xmp for DSC02108.ARW) or Camera Raw ignores it silently — that is
why placed files carry no date prefix, and why leftovers keep one (their
RAW is not on disk, the prefix is the only disambiguator).

Dependencies: none beyond Python stdlib.
"""
import sqlite3, os, glob, shutil, csv, re, collections
from common import get_paths

_p = get_paths("Extract per-photo develop XMPs and place them next to their RAWs")
DATA, WORK, OUT = _p.data, _p.work, _p.out
ORIG = os.path.join(OUT, "originals")
XDIR = os.path.join(OUT, "xmp-sidecars")

def S(x): return x.decode('utf-8','replace') if isinstance(x, bytes) else x

wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex")); wfx.text_factory = bytes

assets = {S(a): (S(f), S(c)) for a, f, c in
          wfx.execute("SELECT assetId, filename, captureDate FROM assets")}

# asset -> folder of its recovered original (assetPathsAndInfo.docId = assetId)
asset_dir = {}
for r in wfx.execute("SELECT docId, originalRelativePath FROM assetPathsAndInfo"):
    aid, rel = S(r[0]), S(r[1]) or ""
    if "originals" not in rel: continue
    tail = rel.replace("\\", "/").split("originals/")[-1]
    d = os.path.dirname(os.path.join(ORIG, tail))
    if os.path.isdir(d):
        asset_dir[aid] = d

# asset -> [(sha, updated)] for xmp_develop rows
asset_shas = collections.defaultdict(list)
for aid, sha, upd in wfx.execute(
    """SELECT assetId, contentIdOrSha256, dateLastUpdatedInSeconds
       FROM purgeCandidates WHERE binaryType='xmp_develop'"""):
    asset_shas[S(aid)].append((S(sha), upd or 0))

# docId -> assetId, sha -> assetId (all id spaces, for leftovers)
doc2asset = {}
for doc, aid in wfx.execute("SELECT docId, assetId FROM versions"): doc2asset[S(doc)] = S(aid)
for doc, aid in wfx.execute("SELECT DISTINCT docId, assetId FROM purgeCandidates"):
    doc2asset.setdefault(S(doc), S(aid))
sha2asset = {}
for doc, sha in wfx.execute("SELECT docId, sha256 FROM externalDevelopSettings"):
    a = doc2asset.get(S(doc))
    if a: sha2asset[S(sha)] = a

on_disk = {os.path.basename(p): p for p in glob.glob(os.path.join(DATA, "settings", "*"))}
print("settings files:", len(on_disk))

def wrap(raw):
    if raw.lstrip()[:9] == b'<?xpacket' or b'<?xpacket' in raw[:200]:
        return raw
    i = raw.find(b'<x:xmpmeta'); j = raw.rfind(b'</x:xmpmeta>')
    if i == -1 or j == -1: return None
    return (b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
            + raw[i:j + 12] + b'\n<?xpacket end="w"?>')

def safe_dst(directory, name):
    dst = os.path.join(directory, name); n = 1
    stem, ext = os.path.splitext(name)
    while os.path.exists(dst):
        dst = os.path.join(directory, f"{stem}_{n}{ext}"); n += 1
    return dst

# --- preserve pre-existing _aux (generative-remove metadata) by placing them too
aux_moves = []
for f in glob.glob(os.path.join(XDIR, "*_aux.xmp")):
    m = re.match(r'(\d{4}-\d\d-\d\d)_(.+)_aux\.xmp$', os.path.basename(f))
    if m:
        d = os.path.join(ORIG, m.group(1)[:4], m.group(1))
        if os.path.isdir(d): aux_moves.append((f, d, f"{m.group(2)}_aux.xmp"))

# --- clean the sidecar folder root (regenerating everything)
os.makedirs(XDIR, exist_ok=True)
for f in glob.glob(os.path.join(XDIR, "*.xmp")):
    os.remove(f)
for f, d, n in aux_moves:
    shutil.copy2(f, safe_dst(d, n)); print("aux placed:", n)

placed = sidecar = revs = 0
covered = set()
for aid, lst in asset_shas.items():
    if aid not in assets: continue
    hits = sorted([(s, u) for s, u in lst if s in on_disk], key=lambda t: t[1])
    if not hits: continue
    fn, cap = assets[aid]
    base = os.path.splitext(fn)[0]
    d = asset_dir.get(aid)
    for k, (s, u) in enumerate(hits):
        pkt = wrap(open(on_disk[s], 'rb').read())
        if pkt is None: continue
        current = (k == len(hits) - 1)
        if d:
            name = f"{base}.xmp" if current else f"{base}_{s[:6]}.xmp"
            with open(safe_dst(d, name), 'wb') as f: f.write(pkt)
            if current: placed += 1
            else: revs += 1
        else:
            name = f"{cap[:10]}_{base}.xmp" if current else f"{cap[:10]}_{base}_{s[:6]}.xmp"
            with open(safe_dst(XDIR, name), 'wb') as f: f.write(pkt)
            if current: sidecar += 1
            else: revs += 1
        covered.add(aid)

# leftovers: disk files not claimed by any purge row
claimed = {s for lst in asset_shas.values() for s, u in lst}
n_unlinked = 0
extra = set()
for s, p in on_disk.items():
    if s in claimed: continue
    aid = sha2asset.get(s)
    pkt = wrap(open(p, 'rb').read())
    if pkt is None: continue
    if aid and aid in assets:
        fn, cap = assets[aid]
        base = os.path.splitext(fn)[0]; d = asset_dir.get(aid)
        if d:
            with open(safe_dst(d, f"{base}_{s[:6]}.xmp"), 'wb') as f: f.write(pkt)
        else:
            with open(safe_dst(XDIR, f"{cap[:10]}_{base}_{s[:6]}.xmp"), 'wb') as f: f.write(pkt)
        extra.add(aid)
    else:
        os.makedirs(os.path.join(XDIR, "_unlinked"), exist_ok=True)
        shutil.copy2(p, os.path.join(XDIR, "_unlinked", s + '.xmp'))
        n_unlinked += 1
print(f"placed next to RAW: {placed} (+{revs} old revisions) | no-original sidecars: {sidecar} "
      f"| extra linked: {len(extra)} | unlinked: {n_unlinked}")

# --- presets (rebuild folder cleanly so re-runs don't duplicate)
presets = {S(doc): S(nm) for doc, nm in wfx.execute("SELECT docId, name FROM presetsAndProfiles")}
pdir = os.path.join(OUT, "presets")
shutil.rmtree(pdir, ignore_errors=True)
os.makedirs(pdir, exist_ok=True)
n_pre = 0
for p in glob.glob(os.path.join(DATA, "cr_settings", "*.xmp")):
    stem = os.path.splitext(os.path.basename(p))[0]
    nm = (presets.get(stem) or stem).strip().replace(' ', '_') or stem
    shutil.copy2(p, safe_dst(pdir, nm + '.xmp')); n_pre += 1
print("presets copied:", n_pre)

# --- manifest patch
mpath = os.path.join(OUT, "manifest.csv")
rows = list(csv.reader(open(mpath, newline="", encoding="utf-8-sig")))
hdr = rows[0]; i_aid, i_xmp = hdr.index("assetId"), hdr.index("xmpSidecar")
n = 0
for r in rows[1:]:
    if r[i_aid] in covered and r[i_xmp] != "yes":
        r[i_xmp] = "yes"; n += 1
with open(mpath, "w", newline="", encoding="utf-8-sig") as f:
    csv.writer(f).writerows(rows)
print("manifest updated:", n, "| total xmp=yes:", sum(1 for r in rows[1:] if r[i_xmp] == "yes"))
