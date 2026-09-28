# Walkthrough: how the RAWs and the XMPs were actually found

A step-by-step forensic reconstruction of the recovery — every snippet is
the real code that was run (condensed), with an explanation of what it
revealed and why the next step followed. Paths are written as `DATA` for
the catalog folder (`%LOCALAPPDATA%\Adobe\Lightroom CC\Data\<guid>`).

Worked-example numbers are from the real recovery: 1,991 photos,
1,692 originals (64 GB), ~630 edited, 2,648 develop-settings blobs.

---

## Step 0 — Accept the premise: the data outranks the app

Access revocation stops *Lightroom the app* from launching. It does not
touch the app's local cache. So before any reverse engineering, the
question is simply: *what files exist?* — not *what does the app let me do?*

```python
import os
DATA = os.path.join(os.environ["LOCALAPPDATA"],
                    "Adobe", "Lightroom CC", "Data", "<guid>")
for name in sorted(os.listdir(DATA)):
    p = os.path.join(DATA, name)
    if os.path.isdir(p):
        n = sum(len(fs) for _, _, fs in os.walk(p))
        print(f"{name:20s} {n:6d} files")
    else:
        print(f"{name:20s} {os.path.getsize(p)//1024:6d} KB")
```

```
originals            1692 files      ← full-resolution RAWs (64 GB!)
previews             5530 files      ← rendered JPEGs (edits baked in)
auxiliary            4734 files      ← mixed binary store
proxies               318 files      ← 2560 px DNG stand-ins
settings            2648 files      ← ★ the per-photo edit store (Step 6)
xmp                    0 files       ← empty
big_table_cache        0 files       ← empty
Managed Catalog.mcat             161 MB
Managed Catalog.wfindex           30 MB
Managed Catalog.notifdb             …
```

Everything a recovery could want is visible in this one census — the RAWs
immediately (`originals\2025\2024-11-16\DSC00001.ARW`), the catalog as
SQLite files, and (once decoded) the rest.

> **The mistake to avoid:** judging folders by their names. `settings\`
> sounded like application preferences and was skipped for hours while the
> hunt detoured through compressed blobs in `auxiliary\`. Enumerate
> everything; assume nothing.

---

## Step 1 — Snapshot the databases before anything else

Two of the three SQLite files are in WAL mode (`.mcat-wal` holds pages not
yet merged into the main file). Copy the database **with** its WAL/SHM
siblings, and never work on the live copies — Adobe's cache manager can
purge them at any time.

```python
import shutil, glob, os
WORK = r".\work"
os.makedirs(WORK, exist_ok=True)
for pat in ("Managed Catalog.mcat*", "Managed Catalog.wfindex*"):
    for f in glob.glob(os.path.join(DATA, pat)):
        shutil.copy2(f, WORK)
shutil.copytree(os.path.join(DATA, "previews"), os.path.join(WORK, "previews"),
                dirs_exist_ok=True)
```

Opening them needs one non-negotiable setting, because Adobe stores binary
blobs inside columns *declared as TEXT*:

```python
import sqlite3
wfx = sqlite3.connect(os.path.join(WORK, "Managed Catalog.wfindex"))
wfx.text_factory = bytes          # ← without this: "Could not decode to UTF-8"

def S(x):  return x.decode('utf-8', 'replace') if isinstance(x, bytes) else x
def K(x):  return str(S(x))       # canonical join key: always a str
```

**Why `text_factory = bytes`:** Python's sqlite3 tries to UTF-8-decode TEXT
columns on fetch. Adobe's are binary. `bytes` hands them through raw, and
the `S()`/`K()` helpers decode defensively. Two related traps:

- `WHERE fullDocId = ?` with a **bytes** parameter silently matches nothing
  against a TEXT column — always pass `str`.
- `length(col)` counts *characters* on binary-in-TEXT and understates the
  size; use `length(CAST(col AS BLOB))`.

### What's inside

`Managed Catalog.mcat` is a Couchbase-Lite-style document store
(`docs` + `revs`, content in an Adobe-flavored CBOR). Stock `cbor2` chokes
on it. **Ignore it at first** — because:

```python
tabs = [S(r[0]) for r in wfx.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(len(tabs))
```

`wfindex` — the "workflow index" Adobe builds for search — has ~60 plain
tables that already answer every question the CBOR would:

| table | what it holds |
|---|---|
| `assets` | one row per photo: `assetId`, `filename`, `captureDate`, `rating`, `flag` |
| `versions` | one row per edit: `docId`, `assetId`, timestamps |
| `assetPathsAndInfo` | where each photo's local original lives |
| `localAuxTracker` | `docId → digest` for `auxiliary\` files |
| `purgeCandidates` | every cacheable binary: `docId, assetId, binaryType, contentIdOrSha256, hasLocalFile` |
| `externalDevelopSettings` | `docId → sha256` of edit settings |
| `presetsAndProfiles` | preset `docId → name` |

> **Lesson:** inventory the boring SQL before fighting the exotic binary.

---

## Step 2 — Find the RAWs

The photo→file mapping lives in `assetPathsAndInfo.originalRelativePath`
(absolute-ish path with no drive letter). One subtlety: the column is
called `docId`, but it actually holds the **assetId** — verified by
checking that its values are the same 32-hex ids as `assets.assetId`:

```python
info = {}
for r in wfx.execute(
        "SELECT docId, fileName, originalRelativePath FROM assetPathsAndInfo"):
    aid, fn, rel = K(r[0]), S(r[1]), S(r[2]) or ""
    if "originals" not in rel:
        continue
    tail = rel.replace("\\", "/").split("originals/")[-1]
    p = os.path.join(DATA, "originals", tail)
    if os.path.exists(p):
        info[aid] = (fn, p)

print(len(info), "originals on disk")   # → 1646 mapped paths
```

```python
assets = {K(a): (S(f), S(c)) for a, f, c in
          wfx.execute("SELECT assetId, filename, captureDate FROM assets")}
edited = {K(a) for (a,) in wfx.execute("SELECT DISTINCT assetId FROM versions")}
print(len(assets), "photos,", len(edited), "edited")
```

At this point the RAWs are safe — one `copytree` away. Keep the framing
honest, though: these are byte-identical copies of files the user already
owned, so this step is redistribution, not recovery — a lifeline only when
the original import source (cards, drives) is gone. The genuinely
irreplaceable data — the edits, which exist nowhere else — is what the
rest of this document recovers.

---

## Step 3 — Where are the edits? (the dead ends)

Cloud Lightroom stores full develop settings as *externalized binaries*.
The index says so — and says whether each one is local:

```python
for r in wfx.execute("""SELECT binaryType, COUNT(*), SUM(hasLocalFile)
                        FROM purgeCandidates GROUP BY 1"""):
    print(r)
```

```
b'aux'          5403 total, 4676 local
b'xmp_develop'  3457 total, 2123 local   ← 2,123 rows point at local blobs
b'original'     1998 total, 1646 local
b'proxy'        1998 total,  310 local
```

`purgeCandidates` is Adobe's cache-management bookkeeping (`hasLocalFile`,
`ozHasBinary` — "Oz" is their cloud object store). That census is the map
for the whole hunt: it promises 2,123 local XMP payloads. The obvious
candidates betrayed us first:

- `Data\xmp\` — 0 files.
- `Data\big_table_cache\` — 0 files.

**Moral:** the *index* was right both times; the *search* looked in the
wrong folders.

---

## Step 4 — First XMPs: the `auxiliary\` containers

Since no folder volunteered XMPs, triage every file by its magic bytes:

```python
import glob, os, collections
kinds = collections.Counter()
for p in glob.glob(os.path.join(DATA, "auxiliary", "*", "*")):
    with open(p, "rb") as f:
        kinds[f.read(2).hex()] += 1
print(kinds)
```

```
{'0200': 4504, '0500': 198, '9006': 6, '8d06': 5, ...}
```

Most files start `02 00 00 00 …` (length-prefixed TIFF renditions). But a
tail of odd headers turns out to be **`<uint32 LE uncompressed-length>` +
zlib** — the second `78 9c` gives it away:

```python
import zlib, struct
p  = glob.glob(os.path.join(DATA, "auxiliary", "*", "*"))[1]
d  = open(p, "rb").read()
ln = struct.unpack("<I", d[:4])[0]
raw = zlib.decompress(d[4:])
print(ln, len(raw), raw[:20])
# → 1680 1680 b'...<x:xmpmeta xmlns:x="adobe:ns:meta/"...'
```

**31 complete XMP develop packets**, hidden as zlib payloads inside
content-addressed containers. To name them, chain three tables:

```
auxiliary\<digest[:3]>\<digest[3:]>          (the file, sharded by digest)
        ↑ localAuxTracker.digest
        localAuxTracker.docId
        ↑ purgeCandidates.docId  →  purgeCandidates.assetId
        assets.assetId          →  filename
```

```python
digest2docs = {}
for doc, dg in wfx.execute("SELECT docId, digest FROM localAuxTracker"):
    digest2docs.setdefault(S(dg).upper(), []).append(K(doc))

doc2asset = {}
for doc, aid in wfx.execute("SELECT DISTINCT docId, assetId FROM purgeCandidates"):
    doc2asset.setdefault(K(doc), K(aid))

for f in glob.glob(os.path.join(DATA, "auxiliary", "*", "*")):
    digest = os.path.basename(os.path.dirname(f)) + os.path.basename(f)
    for doc in digest2docs.get(digest.upper(), []):
        aid = doc2asset.get(doc)          # → photo's assetId
        ...
```

> The `versions.docId` join only resolved 21 of them; `purgeCandidates`
> — a *redundant* key-space for the same objects — resolved all 25
> remaining. When one join fails, enumerate every table carrying the key.

## Step 5 — The wrong conclusion (and the census that fixed it)

With 46 sidecars written and `xmp\`/`big_table_cache\` empty, the working
conclusion became "most edit settings are cloud-only." The index disagreed
(`hasLocalFile=1` × 2,123). The tie-breaker is a whole-tree filename
census — four lines that should have run in Step 0:

```python
import re
hex64 = re.compile(r'[0-9a-f]{64}').fullmatch
for dirpath, dirs, files in os.walk(os.path.dirname(DATA)):
    for f in files:
        if hex64(os.path.splitext(f)[0]):
            print(os.path.join(dirpath, f))
```

```
...\Data\<guid>\settings\0000ee9ecbd3ab7546a9a9b009440a344a5d07...
...\Data\<guid>\settings\0010efb96b7a1624b7080c0ed59ed2d9ed2554...
... (2,592 files)
```

**`Data\settings\`** — 2,648 extensionless files named by 64-hex sha256.
Cross-check against the index:

```python
ids = {S(r[0]) for r in wfx.execute(
    """SELECT DISTINCT contentIdOrSha256 FROM purgeCandidates
       WHERE binaryType='xmp_develop' AND hasLocalFile=1""")}
on_disk = {os.path.basename(p)
           for p in glob.glob(os.path.join(DATA, "settings", "*"))}
print(len(ids & on_disk), "of the promised XMPs are right here")
# → 1,345 of 1,345 distinct shas found (100%) · 1,303 orphan files on disk
#   (row view: 2,123/2,123 rows with a sha resolve to a file)
```

Verify the payload is what it claims:

```python
d = open(glob.glob(os.path.join(DATA, "settings", "*"))[0], "rb").read()
print(b'camera-raw-settings' in d, b'Exposure2012' in d)   # True True
```

## Step 6 — Turn sha256 names into photo names

The join that unlocks everything:

```
purgeCandidates: assetId ─── contentIdOrSha256 ─── settings\<sha256> file
assets:          assetId ─── filename + captureDate
```

```python
import collections
asset_shas = collections.defaultdict(list)
for aid, sha, upd in wfx.execute(
        """SELECT assetId, contentIdOrSha256, dateLastUpdatedInSeconds
           FROM purgeCandidates WHERE binaryType='xmp_develop'"""):
    asset_shas[K(aid)].append((S(sha), upd or 0))

on_disk = {os.path.basename(p)
           for p in glob.glob(os.path.join(DATA, "settings", "*"))}
covered = {a for a, lst in asset_shas.items()
           if any(s in on_disk for s, _ in lst)}
print(len(covered), "photos get their edits back")   # → 1,952
```

`dateLastUpdatedInSeconds` also decides **which revision is current** when
a photo has several (sort ascending; the last one wins — the others are
kept with a `_abcdef` suffix from the sha).

## Step 7 — Make them into real sidecars

Two rules produce files that Camera Raw actually reads:

1. **Byte-identical base name.** `DSC02091.xmp` for `DSC02091.ARW`.
   Any prefix/suffix and ACR silently ignores the file.
2. **A wrapped XMP packet.** The stored blobs start at `<x:xmpmeta`;
   sidecars want the `<?xpacket?>` envelope:

```python
def wrap(raw: bytes):
    if raw.lstrip()[:9] == b'<?xpacket' or b'<?xpacket' in raw[:200]:
        return raw                       # already a packet
    i = raw.find(b'<x:xmpmeta')
    j = raw.rfind(b'</x:xmpmeta>')
    if i == -1 or j == -1:
        return None
    return (b'<?xpacket begin="\xef\xbb\xbf" '
            b'id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
            + raw[i:j + 12] + b'\n<?xpacket end="w"?>')
```

Placement uses the photo's *own* folder from Step 2 — which is why each
XMP lands in its correct `originals\<year>\<date>\` even when hundreds of
shoot-days exist:

```python
for aid, lst in asset_shas.items():
    hits = sorted([(s, u) for s, u in lst if s in on_disk],
                  key=lambda t: t[1])            # oldest → newest
    fn, cap = assets[aid]
    base = os.path.splitext(fn)[0]
    d = asset_dir[aid]                            # from assetPathsAndInfo
    for k, (s, u) in enumerate(hits):
        current = (k == len(hits) - 1)
        name = f"{base}.xmp" if current else f"{base}_{s[:6]}.xmp"
        with open(os.path.join(d, name), "wb") as f:
            f.write(wrap(open(os.path.join(DATA, "settings", s), "rb").read()))
```

Sanity-check the result before trusting it — open one sidecar and confirm
the sliders:

```python
import re
t = open("DSC02091.xmp", encoding="utf-8", errors="replace").read()
print(re.search(r'crs:Exposure2012="([^"]+)"', t).group(1),
      re.search(r'crs:WhiteBalance="([^"]+)"', t).group(1))
```

---

## Bonus track — the edited JPEGs (when no XMP exists)

`previews\` holds *rendered* edits — JPEGs with the look baked in — keyed
by opaque cache ids that map to nothing in any table. Rendition suffixes:
`afa` = 320 px, `ama` = 640 px, `baa` = 2048 px (the ones worth keeping).
No EXIF survives, so naming them is a *perceptual* problem:

```python
# every Sony ARW embeds a full-size JPEG — harvest it:
def embedded_jpeg(path):
    data, pos, best = open(path, "rb").read(), 0, None
    while (i := data.find(b"\xff\xd8\xff", pos)) != -1:
        pos = i + 3
        if (e := data.find(b"\xff\xd9", i)) != -1:
            seg = data[i:e + 2]
            if len(seg) > 30000 and (best is None or len(seg) > len(best)):
                best = seg
    return best

# compare 24×24 grayscale, normalized per image so exposure/WB shifts cancel:
def thumb(img_bytes, size=24):
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(img_bytes))).convert("L")
    a = np.asarray(im.resize((size, size)), dtype=np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)
```

Accept a match only on **absolute score AND margin over the runner-up**
(`corr > 0.45`, `margin > 0.08`); heavy crops need the tile-normalized /
center-crop variants (steps 03/04). Deliberate result: only ~50–56 auto-named
of 303 — *a wrong name is worse than no name* — with a self-contained
`match-helper.html` contact sheet (edited thumbnail + top-3 candidate
originals, base64-embedded) for a human to finish the job.

---

## The habits that made it work

1. **File census first.** `os.walk` + counters over *every* folder, before
   any format assumptions. (The Step-5 census should have been Step 0.)
2. **Trust the index over intuition.** `purgeCandidates.hasLocalFile`
   described reality exactly; the failure was searching the wrong folders.
3. **Enumerate redundant key-spaces.** `versions.docId`,
   `purgeCandidates.docId`, `assetPathsAndInfo.docId` (=assetId!) —
   one of them always joins.
4. **Count everything, print everything.** Every step above ends in a
   printed number; discrepancies (2,123 promised vs 31 found) are the
   pointer to the next step.
5. **Verify final artifacts by content**, not by count — one opened XMP
   with real `crs:` sliders is worth more than a directory listing.
