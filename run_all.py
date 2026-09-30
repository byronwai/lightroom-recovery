r"""Lightroom (cloud) local-data recovery — pipeline driver.

Runs the numbered steps in order, forwarding the shared path arguments:

  python run_all.py [--data <Lightroom CC Data folder>]
                    [--work <working folder>]
                    [--out <recovery output root>]

Defaults: --data from %LOCALAPPDATA%\Adobe\Lightroom CC\Data (auto-discovers
the catalog GUID), --work ./work, --out ./LightroomRecovery under the
current directory.

Steps:
  01_snapshot_catalog.py    copy catalog DBs + previews out of Adobe's cache area
  02_build_recovery.py      build the recovery tree
                            (originals copy, DNG proxies, unnamed edited JPEGs,
                             manifest.csv, catalog backup)
  03_match_previews.py      round 1: name edited JPEGs by strict image matching
  04_match_previews_round2.py  round 2: looser matching (crop-tolerant)
  05_make_helper.py         match-helper.html contact sheet for the rest
  06_extract_settings_xmp.py  full XMP extraction from Data\settings\
                            (sha256-named develop store) — places each XMP
                            NEXT TO ITS RAW in originals\<year>\<date>\
                            with the exact base name Camera Raw needs
                            (older revisions get a sha suffix; photos with
                            no recovered original stay in xmp-sidecars\;
                            also recovers presets)
  07_install_acr_presets.py  optional: install recovered presets into
                            Adobe's settings folders (dry-run by default)
  08_assemble_mask_rasters.py  offline .acr equivalent: attribute the
                            auxiliary type-02 mask rasters to photos and
                            decode them to viewable PNGs

Dependencies:  python -m pip install numpy pillow
"""
import argparse, os, subprocess, sys

here = os.path.dirname(os.path.abspath(__file__))

def main():
    local = os.environ.get("LOCALAPPDATA")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=os.path.join(local, "Adobe", "Lightroom CC", "Data")
                   if local else None,
                   help="Lightroom cloud Data folder")
    p.add_argument("--work", default=os.path.join(here, "work"))
    p.add_argument("--out", default=os.path.join(os.getcwd(), "LightroomRecovery"))
    a = p.parse_args()

    fwd = ["--work", a.work, "--out", a.out]
    if a.data:
        fwd += ["--data", a.data]

    steps = ["01_snapshot_catalog.py", "02_build_recovery.py",
             "03_match_previews.py", "04_match_previews_round2.py",
             "05_make_helper.py", "06_extract_settings_xmp.py",
             "07_install_acr_presets.py", "08_assemble_mask_rasters.py"]
    for s in steps:
        print(f"\n===== {s} =====")
        cmd = [sys.executable, os.path.join(here, s)]
        if s == "01_snapshot_catalog.py":          # step 01 has no --out
            cmd += ["--data", a.data] if a.data else ["--work", a.work]
            if a.data:
                cmd += ["--work", a.work]
        else:
            cmd += fwd
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"!! {s} failed with exit code {r.returncode} — fix and re-run from here")
            sys.exit(r.returncode)
    print(f"\nAll steps done. See {a.out} for the recovered files "
          "(README.txt there describes the layout if it was generated).")

if __name__ == "__main__":
    main()
