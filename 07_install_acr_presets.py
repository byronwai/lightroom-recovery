r"""Install the recovered ACR-format presets into Adobe's settings folders.

The presets recovered from cr_settings\ (output: <out>\presets\*.xmp) are
genuine Camera Raw preset files (crs namespace, PresetType/Cluster schema).
Adobe apps load them from:

  ACR / Lightroom (cloud):  %APPDATA%\Adobe\CameraRaw\Settings
  Lightroom Classic:        %APPDATA%\Adobe\Lightroom\Settings

Dry-run by default — pass --apply to actually copy. Existing files are
never overwritten; a counter suffix is added instead.

Usage:
  python 07_install_acr_presets.py --out D:\MyRecovery          (dry run)
  python 07_install_acr_presets.py --out D:\MyRecovery --apply
"""
import argparse, os, shutil, glob

def safe_dst(directory, name):
    dst = os.path.join(directory, name); n = 1
    stem, ext = os.path.splitext(name)
    while os.path.exists(dst):
        dst = os.path.join(directory, f"{stem}_{n}{ext}"); n += 1
    return dst

def main():
    roaming = os.environ.get("APPDATA")
    p = argparse.ArgumentParser(description="Install recovered presets into Adobe settings folders")
    p.add_argument("--out", default=os.path.join(os.getcwd(), "LightroomRecovery"),
                   help="recovery output root (default: ./LightroomRecovery)")
    p.add_argument("--apply", action="store_true",
                   help="actually copy (default: dry run)")
    p.add_argument("--acr-dir",
                   default=os.path.join(roaming, "Adobe", "CameraRaw", "Settings") if roaming else None,
                   help="ACR / Lightroom settings folder")
    p.add_argument("--lr-dir",
                   default=os.path.join(roaming, "Adobe", "Lightroom", "Settings") if roaming else None,
                   help="Lightroom Classic settings folder")
    a = p.parse_args()

    src = os.path.join(a.out, "presets")
    files = sorted(glob.glob(os.path.join(src, "*.xmp")))
    if not files:
        raise SystemExit(f"no presets found under {src!r} — run the pipeline first")

    targets = {name: d for name, d in
               (("ACR / Lightroom (cloud)", a.acr_dir),
                ("Lightroom Classic", a.lr_dir)) if d}
    print(f"{len(files)} presets from {src}")
    mode = "APPLY" if a.apply else "DRY RUN (pass --apply to copy)"
    print(f"mode: {mode}\n")

    for label, d in targets.items():
        os.makedirs(d, exist_ok=True)
        print(f"[{label}] -> {d}")
        for f in files:
            dst = safe_dst(d, os.path.basename(f))
            if a.apply:
                shutil.copy2(f, dst)
                print(f"  copied {os.path.basename(f)}")
            else:
                print(f"  would copy {os.path.basename(f)}"
                      + (" (name taken -> suffix)" if dst != os.path.join(d, os.path.basename(f)) else ""))
    if a.apply:
        print("\nDone. Restart the Adobe app and look in the Presets panel.")

if __name__ == "__main__":
    main()
