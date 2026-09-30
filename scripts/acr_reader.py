r"""Read an Adobe .acr export companion: dump structure, extract mask rasters.

Layout (reverse-engineered, see docs/diagrams.md §6.8):
  0x00  "ACR\\0"  u32 ver  "<fmt>\\0"  u32 4  u32 0
  0x14  20-byte id (not sha1 of RAW/XMP — provenance unknown)
  0x2C  u32 0     0x30  u32 offset-to-first-record (148 in samples)
  ...   directory region
  records: 16-byte header  02 00 00 00 01 00 00 00 <8 zero bytes>
           followed by a self-contained TIFF (JPEG-XL tiled, tag 52546)
  TIFFs are not length-prefixed, so records are delimited by the NEXT
  record's signature (or EOF) — the walker below uses exactly that.

Usage:
  python scripts/acr_reader.py <file.acr> [--out DIR] [--png]
    --out   write each record's TIFF into DIR (default: alongside input)
    --png   also decode rasters to PNG (needs: pip install tifffile imagecodecs)
"""
import sys, os, struct, glob

SIG = b"\x02\x00\x00\x00\x01\x00\x00\x00" + b"\x00" * 8
TIFF_MAGICS = (b"II*\x00", b"MM\x00*")

def records(data):
    """Yield (offset, tiff_bytes) for every type-02 record in the blob."""
    starts = []
    i = data.find(SIG)
    while i != -1:
        if data[i + 16:i + 20] in TIFF_MAGICS:
            starts.append(i)
        i = data.find(SIG, i + 1)
    for k, off in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(data)
        yield off, data[off + 16:end]

def tiff_info(t):
    bo = "<" if t[:2] == b"II" else ">"
    n = struct.unpack(bo + "H", t[8:10])[0]
    tags = {}
    for k in range(n):
        e = t[10 + k * 12:22 + k * 12]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        buf = e[8:10] if typ == 3 else e[8:12]
        tags[tag] = struct.unpack(bo + "H" if typ == 3 else bo + "I", buf)[0]
    return tags

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_png = "--png" in sys.argv
    outdir = (sys.argv[sys.argv.index("--out") + 1]
              if "--out" in sys.argv else os.path.dirname(os.path.abspath(args[0])))
    path = args[0]
    data = open(path, "rb").read()

    assert data[:4] == b"ACR\x00", "not an ACR file"
    ver, fmt = struct.unpack("<I", data[4:8]), data[8:12].rstrip(b"\0").decode()
    first = struct.unpack("<I", data[44:48])[0]
    print(f"{os.path.basename(path)}  ({len(data):,} bytes)")
    print(f"  version {ver}  source-format {fmt}  id {data[20:40].hex()}")
    print(f"  first record @ 0x{first:X}")

    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    for n, (off, tif) in enumerate(records(data)):
        info = tiff_info(tif)
        w, h = info.get(0x0100), info.get(0x0101)
        comp, spp = info.get(0x0103), info.get(0x0115)
        tifp = os.path.join(outdir, f"{base}_r{n:02d}.tif")
        open(tifp, "wb").write(tif)
        line = (f"  record {n}: @0x{off:X}  {len(tif):,} B  "
                f"{w}x{h} {spp}ch comp={comp}")
        if do_png:
            try:
                import numpy as np, tifffile
                from PIL import Image
                a = tifffile.imread(tifp)
                if a.ndim == 3: a = a[..., 0]
                if a.dtype != np.uint8:
                    mx = int(a.max())
                    a = (a * (255 // max(1, mx))).astype(np.uint8) if mx else a.astype(np.uint8)
                png = tifp[:-4] + ".png"
                Image.fromarray(a).save(png)
                line += f"  -> {os.path.basename(png)}"
            except ImportError:
                line += "  (tifffile/imagecodecs missing — no PNG)"
        print(line)

if __name__ == "__main__":
    main()
