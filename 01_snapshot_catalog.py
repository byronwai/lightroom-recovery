r"""Snapshot the Lightroom cloud local library to a safe working copy.

This is step 01 of the recovery pipeline. It copies the catalog databases
and the preview cache BEFORE anything else — those files live inside Adobe's
cache area and can be purged by the app at any time.

Usage:  python 01_snapshot_catalog.py [--data <Lightroom CC Data folder>]
                                       [--work <working folder>]
"""
import os, shutil, glob
from common import get_paths

def main():
    paths = get_paths("Snapshot the Lightroom cloud catalog to a working copy",
                      need_out=False)
    WORK, src = paths.work, paths.data
    os.makedirs(WORK, exist_ok=True)
    print("source:", src)

    # 1) catalog databases (mcat = document store, wfindex = SQL index, notifdb)
    for pat in ("Managed Catalog.mcat*", "Managed Catalog.wfindex*", "Managed Catalog.notifdb*"):
        for f in glob.glob(os.path.join(src, pat)):
            shutil.copy2(f, WORK); print("copied", os.path.basename(f))

    # 2) preview cache (edited JPEG renders, metadata-stripped, keyed by cache ids)
    shutil.copytree(os.path.join(src, "previews"), os.path.join(WORK, "previews"),
                    dirs_exist_ok=True)
    print("previews copied")

    # originals are NOT copied here (they are 64 GB) — the main builder copies
    # them straight to the recovery drive instead.

if __name__ == "__main__":
    main()
