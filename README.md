# Lightroom Cloud Local Recovery

Recover your photos, edits, and presets from the **local cache of Adobe
Lightroom (cloud version)** — without the Lightroom app, without an Adobe
account, without any entitlement. Works after your subscription ended,
your license was revoked, or you simply can't sign in anymore.

Built and battle-tested on a real recovery: 1,692 originals (64 GB),
full develop settings (XMP) for every edited photo, edited JPEG renders,
and 234 presets — all pulled from the local cache after access was revoked.

**New: [docs/walkthrough.md](docs/walkthrough.md)** — a detailed
step-by-step forensic reconstruction of how the RAW and XMP files were
actually found, every code snippet explained: the database snapshots,
the dead ends, the sha256 content store, and the perceptual matcher.

> **Scope:** this project rescues **your own photos from your own disk**.
> It is not a way to keep using Adobe's software or services without a
> license — the app stays locked, and anything Adobe kept server-side
> stays gated until you resubscribe (or use their post-cancellation
> grace period / free trial to export).

## How is this possible?

Adobe's access gate lives in the application, not in the data. The cloud
Lightroom keeps a complete local copy of everything it synced under
`%LOCALAPPDATA%\Adobe\Lightroom CC\Data\<guid>\` — unencrypted, standard
SQLite databases plus plain files. The only real work is decoding the
undocumented formats, which is exactly what this toolkit does.
The full reverse-engineering story is in
[docs/lessons-learned.md](docs/lessons-learned.md).

## Quick start (Windows, tested)

```bat
pip install numpy pillow
cd lightroom-recovery
python run_all.py --out D:\MyRecovery
```

Everything auto-discovers: the data root from `%LOCALAPPDATA%`, the
catalog GUID by looking for `Managed Catalog.mcat`. Override with
`--data` if your library lives elsewhere.

Run the steps individually if you prefer (each takes the same
`--data / --work / --out` arguments):

| Step | What it does |
|---|---|
| `01_snapshot_catalog.py` | Copies catalog DBs + preview cache out of Adobe's purge-able cache area — **run this first** |
| `02_build_recovery.py` | Builds the recovery tree: originals, DNG proxies, edited JPEGs, manifest, catalog backup |
| `03/04_match_previews*.py` | Names edited JPEGs by perceptual matching against the RAWs (strict, then crop-tolerant) |
| `05_make_helper.py` | Generates `match-helper.html` — a contact sheet to name the rest by eye |
| `06_extract_settings_xmp.py` | The big one: extracts every per-photo develop XMP from `Data\settings\` and places it **next to its RAW** |

## What you get

```
<out>\
├── originals\<year>\<date>\   your RAWs, each with its current edit XMP
│                              beside it (DSC02091.ARW + DSC02091.xmp;
│                              older edit revisions keep a sha suffix)
├── edited-jpg\                edited JPEGs (2048 px) matched to names
├── edited-jpg-unnamed\        edited JPEGs automation couldn't safely name
│                              → identify them visually via match-helper.html
├── xmp-sidecars\              XMPs for photos with no local original,
│                              plus _unlinked\ orphaned revisions
├── presets\                   your Lightroom presets, real names restored
├── raw-defaults\              RawDefaults / FavoriteStyles
├── dng-proxies-2560\          small DNG stand-ins (unedited)
├── catalog-backup\            complete copy of the local library
└── manifest.csv               per-photo inventory (dates, ratings, coverage)
```

## Key facts worth knowing

- **The sidecar naming rule:** Camera Raw / Bridge only read an XMP whose
  base name is *byte-identical* to the photo's. Any prefix or "(1)" and
  it's silently ignored. Step 06 handles this; manual copies must too.
- **What is local vs cloud:** originals, catalog, edit XMPs
  (`Data\settings\`, sha256-addressed), rendered previews, and presets are
  local. Older edit revisions and anything never downloaded stay in
  Adobe's cloud.
- **Generative Remove metadata** (`*_aux.xmp`) records the AI operations,
  not the look — kept for completeness, not for rendering.

## Limitations

- Windows tested; the macOS data layout (`~/Library/Application Support/...`)
  is likely similar but untested — PRs welcome.
- Preview→photo matching is perceptual and deliberately conservative:
  a wrong name is worse than no name.
- Lightroom *Classic* catalogs are out of scope (they're plain SQLite and
  far better documented elsewhere).

## License

[MIT](LICENSE)
