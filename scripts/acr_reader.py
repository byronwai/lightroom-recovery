r"""Read an Adobe .acr export companion: dump structure, extract mask rasters.

Layout (reverse-engineered from 76 real exports, see docs/diagrams.md §6.8):
  0x00  "ACR\0"            magic
  0x04  u32 version        1 in every observed file
  0x08  "<fmt>\0"          source RAW format, e.g. "ARW\0"
  0x0C  u32 N              number of records
  0x10  u32 reserved       0 in every observed file
  0x14  N x 32-byte table entries:
          +0x00  16 B   md5 of the record (signature + TIFF, without padding)
          +0x10  u64    record size in bytes
          +0x18  u64    record offset from start of file
  records start at 20 + 32*N, each on a 4-byte boundary (zero padding):
          16-byte signature  02 00 00 00 01 00 00 00 <8 zero bytes>
          then a self-contained little-endian TIFF (JPEG-XL tiled, tag 52546)

The record md5 is the value the XMP stores as crs:MaskDigest (AI masks) or
crs:pm_patch / crs:pm_patch_variation (Remove-tool patches), and the name the
local cache gives the identical record under auxiliary\.

Usage:
  python scripts/acr_reader.py <file.acr> [--out DIR] [--png]
    --out   write each record's TIFF into DIR (default: alongside input)
    --png   also decode rasters to PNG (needs: pip install tifffile imagecodecs)
If a sibling <name>.xmp exists, each record is matched to the XMP attribute
that references it.
"""
import sys, os, re, struct, hashlib

SIG = b"\x02\x00\x00\x00\x01\x00\x00\x00" + b"\x00" * 8
TIFF_MAGICS = (b"II*\x00", b"MM\x00*")

def read_table(data):
    """Return (version, fmt, reserved, [(md5_hex, size, offset), ...])."""
    assert data[:4] == b"ACR\x00", "not an ACR file"
    ver, = struct.unpack("<I", data[4:8])
    fmt = data[8:12].rstrip(b"\0").decode("ascii", "replace")
    n, reserved = struct.unpack("<II", data[12:20])
    entries = []
    for i in range(n):
        e = data[20 + 32 * i: 52 + 32 * i]
        size, off = struct.unpack("<QQ", e[16:32])
        entries.append((e[:16].hex().upper(), size, off))
    return ver, fmt, reserved, entries

def scan(data):
    """Fallback when the table is unusable: split at each signature.
    Sizes found this way may include up to 3 bytes of alignment padding."""
    starts, i = [], data.find(SIG)
    while i != -1:
        if data[i + 16:i + 20] in TIFF_MAGICS:
            starts.append(i)
        i = data.find(SIG, i + 1)
    ends = starts[1:] + [len(data)]
    return [(None, e - s, s) for s, e in zip(starts, ends)]

def tiff_info(t):
    """First value and count of each IFD0 tag (enough for the fields printed)."""
    bo = "<" if t[:2] == b"II" else ">"
    ifd = struct.unpack(bo + "I", t[4:8])[0]
    n = struct.unpack(bo + "H", t[ifd:ifd + 2])[0]
    tags = {}
    for k in range(n):
        e = t[ifd + 2 + 12 * k: ifd + 14 + 12 * k]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        buf = e[8:10] if typ == 3 else e[8:12]
        tags[tag] = (cnt, struct.unpack(bo + "H" if typ == 3 else bo + "I", buf)[0])
    return tags

def xmp_refs(path):
    """Map raster md5 -> referencing XMP attribute, from a sibling .xmp."""
    x = os.path.splitext(path)[0] + ".xmp"
    if not os.path.exists(x):
        return None
    s = open(x, "rb").read().decode("utf-8", "replace")
    refs = {}
    for m in re.finditer(r'crs:(MaskDigest|pm_patch|pm_patch_variation)="([0-9A-Fa-f]{32})"', s):
        refs.setdefault(m.group(2).upper(), m.group(1))
    return refs

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_png = "--png" in sys.argv
    path = args[0]
    outdir = (sys.argv[sys.argv.index("--out") + 1]
              if "--out" in sys.argv else os.path.dirname(os.path.abspath(path)))
    data = open(path, "rb").read()

    ver, fmt, reserved, entries = read_table(data)
    print(f"{os.path.basename(path)}  ({len(data):,} bytes)")
    print(f"  version {ver}  source-format {fmt}  records {len(entries)}  "
          f"reserved {reserved}  first record @0x{20 + 32 * len(entries):X}")
    if not all(off + size <= len(data) and data[off:off + 16] == SIG for _, size, off in entries):
        print("  WARNING: record table inconsistent with the file; falling back to signature scan")
        entries = scan(data)
    refs = xmp_refs(path)

    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    for n, (md5, size, off) in enumerate(entries):
        rec = data[off:off + size]
        tif = rec[16:]
        actual = hashlib.md5(rec).hexdigest().upper()
        info = tiff_info(tif)
        w, h = info[0x0100][1], info[0x0101][1]
        comp, spp = info[0x0103][1], info[0x0115][1]
        tiles = info.get(0x0144, (0, 0))[0]
        tifp = os.path.join(outdir, f"{base}_r{n:02d}.tif")
        open(tifp, "wb").write(tif)
        check = "" if md5 is None or md5 == actual else " (MISMATCH with table)"
        line = (f"  record {n}: @0x{off:X}  {size:,} B  {w}x{h} {spp}ch "
                f"comp={comp} tiles={tiles}  md5 {actual}{check}")
        if refs is not None:
            line += f"  <- xmp {refs.get(actual, 'not referenced')}"
        if do_png:
            try:
                import numpy as np, tifffile
                from PIL import Image
                a = tifffile.imread(tifp)
                if a.ndim == 3 and spp == 1:
                    a = a[..., 0]
                if a.dtype != np.uint8:
                    mx = int(a.max())
                    a = (a.astype(np.float64) * (255.0 / mx)).astype(np.uint8) if mx else a.astype(np.uint8)
                png = tifp[:-4] + ".png"
                Image.fromarray(a).save(png)
                line += f"  -> {os.path.basename(png)}"
            except ImportError:
                line += "  (tifffile/imagecodecs missing — no PNG)"
        print(line)
    if refs is not None:
        missing = set(refs) - {hashlib.md5(data[o:o + s]).hexdigest().upper() for _, s, o in entries}
        if missing:
            print(f"  xmp references {len(missing)} raster(s) not in this file")

if __name__ == "__main__":
    main()
