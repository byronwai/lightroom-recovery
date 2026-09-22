# Recovering a Lightroom (cloud) Library After Access Revocation

**Case:** Lightroom desktop (cloud version, not Classic) — access revoked (subscription/license ended) with ~621 edited photos and 1,991 assets in the catalog.
**Outcome:** 100% of originals (1,692 files, 64 GB) recovered locally; 303 edited renders (2048 px JPEGs) recovered; **full develop settings (XMP) for 1,952 photos — every edited photo included — extracted from the local `settings\` cache**; 234 presets recovered with names; full library backed up. Everything done offline, without any Adobe app or account.
**Date:** 2026-09-21

---

## 1. Why the revocation didn't destroy anything — the core insight

Adobe's access gate lives **in the application, not in the data**:

- The revoked license stops *Lightroom the app* from launching. It does not encrypt, lock, or delete the local cache.
- The cloud Lightroom keeps a **complete local copy of everything it synced** under `%LOCALAPPDATA%\Adobe\Lightroom CC\Data\<guid>\` — unencrypted, standard SQLite databases plus plain files on disk.
- Reading those files requires nothing but file access to your own user profile. No account, no entitlement, no app.

So "bypassing" Adobe's logic here is trivial by design: the moment you stop thinking *app first* and start thinking *files first*, the whole library is sitting on disk in the open. The only real work was decoding the formats, because none of them are documented.

What the gate genuinely protects (and what could NOT be recovered offline): the cloud-side originals of edits — the full develop settings (every slider) for most photos are stored only on Adobe's servers, referenced by sha256. Local caches held only *renders* of the edits plus a handful of cached XMP payloads. For the rest you need one of:

1. **lightroom.adobe.com** — after access ends there is a grace period where you can still sign in, view, and download your photos (originals and edited JPEGs). Free, no desktop app needed.
2. **A free trial on the same Adobe account** — the cloud library reappears with all edits; export originals + XMP before it expires.

> Scope note: this is about rescuing **your own photos** from your own disk. It is not a way to keep using Adobe's software or services without a license — the app stays locked, and the cloud side stays gated until you resubscribe or use the grace/trial paths above.

---

## 2. The local storage map

```
C:\Users\<user>\AppData\Local\Adobe\Lightroom CC\Data\<guid>\
├── Managed Catalog.mcat          the catalog: Couchbase-Lite-style doc store
│                                  (tables: docs, revs, labels; content = CBOR-ish blobs)
├── Managed Catalog.wfindex        SQLite "workflow index" — THE GOLDMINE
│                                  (assets, versions, assetPathsAndInfo, localAuxTracker,
│                                   purgeCandidates, ratings, editedDate, albums...)
├── Managed Catalog.notifdb        notifications (irrelevant)
├── originals\<year>\<date>\*.ARW  full local originals (if "store locally" / cached)
├── previews\<aa>\ <50-char key><suffix>   rendered previews, EDITED pixels baked in
├── proxies\2560\<id[:3]>\<id[3:]>  2560 px DNG smart proxies (UNEDITED)
├── auxiliary\<id[:3]>\<id[3:]>     mixed binary store: renditions AND zlib XMP payloads
├── settings\<64-hex sha256>        ★ THE PER-PHOTO DEVELOP XMP STORE —
│                                  every edit Adobe downloaded is here,
│                                  content-addressed by sha256 (2,648 files)
├── cr_settings\<docId>.xmp        user presets (names in presetsAndProfiles)
├── cr_cameraprofiles\, cr_defaults\  camera profiles / raw defaults
├── xmp\                           develop XMP downloads — often EMPTY (cached on demand)
└── big_table_cache\               blob cache — often EMPTY
```

Also relevant on this machine: Lightroom *Classic* keeps separate catalogs under
`C:\Users\<user>\Pictures\Lightroom\*.lrcat` (plain SQLite; edits in `Adobe_images` /
develop tables; previews extractable from `*_Previews.lrdata`).

---

## 3. ID schemes and file naming (the Rosetta stone)

| Artifact | Key | How to resolve to a photo |
|---|---|---|
| asset (photo) | `assetId` = 32-char hex | `wfindex.assets.assetId` → `filename`, `captureDate` |
| original file | `originals\<year>\<date>\<file>` | `assetPathsAndInfo.originalRelativePath` (absolute path, no drive letter) — **its `docId` column actually holds the assetId** |
| proxy DNG | `proxies\2560\<assetId[:3]>\<assetId[3:]>` | direct by assetId |
| auxiliary file | `auxiliary\<digest[:3]>\<digest[3:]>` (digest uppercase hex) | `localAuxTracker.digest` → `docId` → `versions.docId → assetId`; **fallback: `purgeCandidates.docId → assetId`** (resolved 25/25 XMPs the versions join missed — see §6.8) |
| preview JPEG | `previews\<2-char shard>\<50-char key><3-char suffix>` | **no local mapping exists** — perceptual matching required (see §5) |

Preview rendition suffixes (all metadata-stripped, no EXIF):

- `afa` = 320 px thumbnail
- `ama` = 640 px thumbnail
- `baa` = 2048 px preview ← the ones worth recovering

Auxiliary container anatomy:

- `02 00 00 00 ...` then TIFF header → rendered rendition (TIFF/DNG-ish)
- `<uint32 LE length> 78 9c ...` → **zlib-compressed XMP develop settings** (a complete edit packet! wrap the inner `<x:xmpmeta…</x:xmpmeta>` in `<?xpacket?>` and it's a valid sidecar)

---

## 4. What is local vs cloud-only

| Data | Local? | Where |
|---|---|---|
| Original raw files | ✅ all 1,692 | `originals\` (64 GB) |
| Catalog metadata (names, dates, ratings, albums) | ✅ | `wfindex` |
| Edited pixels | ✅ renders only | `previews\…baa` (2048 px), aux renditions |
| Full develop settings (sliders, masks) | ✅ | `settings\<sha256>` — mapped to photos via `purgeCandidates` (`binaryType='xmp_develop'`, `contentIdOrSha256`, `assetId`); current revision = highest `dateLastUpdatedInSeconds`. First conclusion — "mostly cloud-only" — was **wrong**, caused by missing this folder (see §6.9) |
| Smart proxies | ✅ | `proxies\2560\` — **unedited**, useful only as small stand-ins |

The catalog itself will tell you the boundary: `purgeCandidates` lists every binary with `hasLocalFile` and `ozHasBinary` ("Oz" = Adobe's cloud object store). Anything with `ozHasBinary=1, hasLocalFile=0` is cloud-only.

---

## 5. How the edited JPEGs were named without any metadata

Previews carry no EXIF and their cache keys map to nothing in the local DBs. Solution: **perceptual matching against the originals' own embedded JPEGs** (every Sony ARW contains a full-size JPEG preview — find the largest `FFD8FF…FFD9` segment).

What worked, in order of reliability:

1. Mean/std-normalized grayscale correlation (24×24) of edited JPEG vs embedded JPEG — robust to exposure/white-balance shifts.
2. Tile-normalized variant (4×4 tiles each normalized separately) — handles vignettes and gradients.
3. Center-crop variant of the original (crop to middle 70%) — tolerates user crops.

Accept a match only with **absolute score AND margin over the runner-up** (e.g. corr > 0.45 and margin > 0.08). Lesson burned in: **a wrong name is worse than no name** — we auto-named only 52/303 and shipped `match-helper.html` (edited thumbnail + top-3 candidate originals, base64-embedded, one self-contained page) for a human to finish the rest. For a photo library, human-in-the-loop beats forced automation.

---

## 6. Reverse-engineering war stories (the time sinks)

These are the traps that cost the most time — recorded so they're one-minute fixes next time:

1. **SQLite TEXT columns holding binary.** `revs.content` is declared TEXT but contains bytes. Python's sqlite3 raises `Could not decode to UTF-8` on fetch. Fix: `con.text_factory = bytes` **plus** `SELECT CAST(col AS BLOB)`.
2. **Blob parameters never match TEXT columns.** `WHERE fullDocId=?` with a *bytes* param returns nothing against a TEXT column, silently. Pass `str`.
3. **`length()` lies on binary-in-TEXT.** It counts characters, not bytes — a 2,316-byte blob reported as "1,028". Always `length(CAST(col AS BLOB))`.
4. **Column names lie.** `assetPathsAndInfo.docId` holds the *assetId*, not the docs-table localDocId; meanwhile `assets.docId` is an INTEGER while other tables use hex strings. Normalize every join key through `str(decode-if-bytes)`.
5. **Adobe's CBOR dialect breaks stock decoders.** `cbor2` dies with "premature end of stream" on `mcat` documents — they're a nonstandard variant (top-level array, binary in text headers). A hand-rolled tolerant scanner (ASCII-run extraction of key names) was enough to *understand* structure without full decoding — and it turned out we never needed to fully decode it, because `wfindex` holds everything needed as proper SQL.
6. **Big lesson #1 of the whole job:** before reverse-engineering the exotic binary thing (`mcat`), inventory the boring thing (`wfindex`). The SQL index had 60+ ready-made tables; hours went into CBOR before that was fully appreciated.
7. **Empty `xmp\` and `big_table_cache\` folders are normal.** The develop XMPs actually hide inside `auxiliary\` as zlib payloads — discoverable only by magic-byte triage (`78 9c` after a 4-byte length). Triage *all* file kinds with header counters before concluding anything is "not stored locally".
8. **When one join fails, enumerate every table carrying the key.** 25 XMP payloads wouldn't resolve through `versions.docId` — but `purgeCandidates` (Adobe's cache-management table) carries the identical `docId → assetId` link and resolved all 25._wfindex has ~60 tables; several are redundant key-spaces for the same objects, and the "boring" table often saves the "interesting" one.
9. **The costliest miss of the job: judging a folder by its name.** The complete per-photo edit store was sitting in `Data\settings\` from the first minute — 2,648 sha256-named XMP files — while the investigation chased compressed payloads in `auxiliary\` and concluded "most edits are cloud-only". The index even said so (`purgeCandidates.hasLocalFile=1` for 2,123 xmp_develop rows — *the flag was right, the search was wrong*). Rule: **enumerate and triage every directory with a file count before assigning semantics to any of them.** A 4-line `os.walk` census answering "what names exist here?" would have saved an hour and prevented a false conclusion in the write-up.

---

## 7. The finalized workflow

```
lightroom-recovery/
├── run_all.py                 driver — runs 01→06, stops on first failure
├── 01_snapshot_catalog.py     copy mcat + wfindex + previews/ to a safe workdir
├── 02_build_recovery.py       build the recovery tree (<out>):
│                              originals/ (full-size copy), edited-jpg-unnamed/,
│                              dng-proxies-2560/ (renamed by photo),
│                              catalog-backup/ (everything), manifest.csv
├── 03_match_previews.py       round 1 strict matching → edited-jpg/ + edited-jpg-map.csv
├── 04_match_previews_round2.py  round 2 crop-tolerant matching
├── 05_make_helper.py          match-helper.html contact sheet
├── 06_extract_settings_xmp.py  full XMP extraction from Data\settings\ —
│                              places each XMP next to its RAW in
│                              originals\<year>\<date>\ under the EXACT base
│                              name (DSC02091.xmp for DSC02091.ARW); older
│                              revisions keep a sha suffix; photos whose
│                              original was never cached locally stay in
│                              xmp-sidecars\ with a date prefix
└── LESSONS_LEARNED.md         this document
```

**Sidecar naming rule (the one that silently bites):** Camera Raw / Bridge
only read an XMP whose base name is *byte-identical* to the photo's. Any
date prefix, suffix, or "(1)" copy marker and the edits are silently
ignored — no error, no warning. That is why the recovery names files with
date prefixes for uniqueness but step 06 strips them at placement time,
and why any manual copy must be renamed to match the RAW exactly.

Dependencies: `pip install numpy pillow` (`cbor2` optional). Total runtime is dominated by the 64 GB file copy; everything else is minutes.

---

## 8. Prevention — so this never matters again

- **Write edits into the files.** In Lightroom: "Save To" / auto-XMP settings (or Classic's "Automatically write changes into XMP"). Sidecars next to files survive every kind of lockout.
- **Keep originals on your own disk first**, cloud second. "Store a copy of all originals locally" was the single setting that made this recovery 100% instead of a salvage job.
- **Export milestones.** After a big shoot's edit session, export finished JPEGs/TIFFs somewhere boring.
- **Audit the cache.** `du` on `%LOCALAPPDATA%\Adobe\Lightroom CC\Data` tells you how much of your library actually lives on your machine; treat it as the real backup surface.
- If you stay with Adobe, know that **Classic's catalog is a single portable SQLite file** — much friendlier to offline recovery than the cloud library's split-brain caches.

---

## 9. Bottom line

Access revocation is an **application-level** control. Against a user's own files it's a door made of paper: the local library is unencrypted, standard SQLite plus files, and every edit Adobe ever rendered on that machine left a recoverable artifact — in the end including the full develop settings for essentially the whole library (`settings\` cache). Nothing of this user's editing work was actually hostage to the cloud.
