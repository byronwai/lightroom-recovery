r"""Shared CLI helpers. No hardcoded, machine-specific paths anywhere:
the Lightroom data root auto-discovers from %LOCALAPPDATA% (or --data),
the catalog GUID folder is found by looking for Managed Catalog.mcat,
and the working/output folders default to locations next to the scripts.
"""
import argparse, glob, os, sys

def _data_root_default():
    local = os.environ.get("LOCALAPPDATA")
    return os.path.join(local, "Adobe", "Lightroom CC", "Data") if local else None

def find_catalog_dir(data_root):
    r"""Return the Data\<guid> folder that holds the Managed Catalog.

    When several catalog folders exist (e.g. a second Adobe account or a
    freshly created library), the most recently used one (newest .mcat
    mtime) wins, and all candidates are printed so the user can override
    with --data <specific folder>.
    """
    if not data_root or not os.path.isdir(data_root):
        sys.exit(f"Lightroom cloud Data folder not found: {data_root!r}\n"
                 "Pass --data <path to .../Adobe/Lightroom CC/Data>")
    candidates = []
    for d in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(d):
            continue
        mcats = glob.glob(os.path.join(d, "*.mcat"))
        # a real library folder also carries the cache subfolders
        if mcats and (os.path.isdir(os.path.join(d, "previews"))
                      or os.path.isdir(os.path.join(d, "originals"))):
            candidates.append((max(os.path.getmtime(m) for m in mcats), d))
    if not candidates:
        sys.exit(f"no catalog (Managed Catalog.mcat) found under {data_root}")
    if len(candidates) > 1:
        print("multiple catalogs found (picking the most recently used; "
              "pass --data <folder> to choose another):")
        for mt, d in sorted(candidates, reverse=True):
            print(f"  {'-> ' if d == max(candidates)[1] else '   '}{d}")
    return max(candidates)[1]

def get_paths(desc, need_out=True):
    """Parse common CLI args and resolve (data, work, out) paths."""
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--data", default=_data_root_default(),
                   help="Lightroom cloud Data folder "
                        "(default: %%LOCALAPPDATA%%\\Adobe\\Lightroom CC\\Data)")
    p.add_argument("--work", default=os.path.join(here, "work"),
                   help="working folder for catalog snapshots (default: ./work)")
    if need_out:
        p.add_argument("--out", default=os.path.join(os.getcwd(), "LightroomRecovery"),
                       help="recovery output root (default: ./LightroomRecovery)")
    a = p.parse_args()
    return argparse.Namespace(data=find_catalog_dir(a.data),
                              work=a.work,
                              out=getattr(a, "out", None))
