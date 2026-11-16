r"""Decompose a real .acr into its records and show where each one lands.

Top: every record, as stored (rasters in sensor orientation; zlib records
summarised), labelled from the sibling XMP by md5. Bottom (optional): the
photo, the ARW's embedded full-size JPEG, with each AI mask outlined at the
XMP's Origin on the FullMaskSize canvas and any Remove target marked. The
composite is built in sensor orientation, where the masks live, and rotated
for display at the end.

Needs: pip install tifffile imagecodecs numpy pillow
Run:   python scripts/make_acr_decomposed_image.py <file.acr> [--out PNG] [--no-photo]
       (expects <name>.xmp and, optionally, <name>.ARW beside the .acr)
Default output: docs/assets/acr-decomposed.png
"""
import os, re, sys, struct, io
import numpy as np, tifffile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acr_reader import read_table, classify, REF_ATTRS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG, PANEL, TXT, DIM = (13, 17, 23), (22, 27, 34), (230, 237, 243), (139, 148, 158)
COLORS = [(255, 166, 87), (88, 166, 255), (126, 231, 135), (210, 168, 255),
          (255, 123, 114), (121, 192, 255), (227, 179, 65), (247, 120, 186)]
SUBTYPE = {"1": "Subject", "3": "People"}
SUBCAT = {"22": "Background", "50001": "Architecture", "50005": "Vegetation",
          "50006": "Sky", "50007": "Water", "11": "Clothes"}

def font(size):
    for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()

def xmp_index(path):
    """md5 -> dict of attributes of the XMP element that references it."""
    if not os.path.exists(path):
        return {}
    s = open(path, "rb").read().decode("utf-8", "replace")
    idx = {}
    pat = r"<[^<>]*crs:(?:%s)=\"[0-9A-Fa-f]{32}\"[^<>]*>" % "|".join(REF_ATTRS)
    for el in re.finditer(pat, s):
        a = dict(re.findall(r'crs:(\w+)="([^"]*)"', el.group(0)))
        for k in REF_ATTRS:
            if k in a:
                idx.setdefault(a[k].upper(), dict(a, _ref=k))
    return idx

def label(a, kind, gen=False):
    ref = a.get("_ref", "")
    gen = gen or a.get("fill_method") == "firefly"
    if ref == "IngestInfo":
        return "Generative Remove receipt", "crs:IngestInfo · receipt XMP"
    if ref == "pm_patch":
        return ("Generative Remove: chosen" if gen else "Remove patch"), "crs:pm_patch · RGB pixels"
    if ref == "pm_patch_variation":
        return ("Generative Remove: variation" if gen else "Remove patch variation"), "crs:pm_patch_variation · RGB"
    if ref == "pm_patch_mask":
        return "Remove fill mask", "crs:pm_patch_mask"
    if ref == "MaskDigest":
        name = re.sub(r"\s*\d+$", "", a.get("MaskName", "")).strip()
        st = a.get("MaskSubType", "?")
        cat = SUBTYPE.get(st) or SUBCAT.get(a.get("MaskSubCategoryID", ""), "scene")
        return (name or "AI object selection"), f"Mask/Image · subtype {st} ({cat})"
    return "unreferenced", kind

def orientation(arw_bytes):
    ifd = struct.unpack("<I", arw_bytes[4:8])[0]
    n = struct.unpack("<H", arw_bytes[ifd:ifd + 2])[0]
    for k in range(n):
        tag, typ, cnt, val = struct.unpack("<HHIH", arw_bytes[ifd + 2 + 12 * k: ifd + 12 + 12 * k])
        if tag == 0x0112:
            return val
    return 1

def embedded_photo(arw):
    """Largest embedded JPEG, as stored (sensor orientation), and the IFD0 Orientation."""
    d = open(arw, "rb").read()
    best, pos = None, 0
    while (i := d.find(b"\xff\xd8\xff", pos)) != -1:
        pos = i + 3
        e = d.find(b"\xff\xd9", i)
        if e != -1 and (best is None or e + 2 - i > len(best)):
            best = d[i:e + 2]
    return Image.open(io.BytesIO(best)).convert("RGB"), orientation(d)

def to_display(img, orient):
    return {3: img.rotate(180, expand=True), 6: img.rotate(-90, expand=True),
            8: img.rotate(90, expand=True)}.get(orient, img)

def to_u8(a):
    a = np.asarray(a)
    if a.dtype != np.uint8:
        lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
        a = ((a.astype(np.float64) - lo) / max(1.0, hi - lo) * 255).clip(0, 255).astype(np.uint8)
    return a

def fit(img, w, h):
    s = min(w / img.width, h / img.height)
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    acr = args[0]
    out = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
           else os.path.join(ROOT, "docs", "assets", "acr-decomposed.png"))
    base = os.path.splitext(acr)[0]
    idx = xmp_index(base + ".xmp")
    firefly = any(a.get("fill_method") == "firefly" for a in idx.values())
    data = open(acr, "rb").read()
    _, _, _, entries = read_table(data)
    recs = []
    for md5, size, off in entries:
        kind, body, _ = classify(data[off:off + size])
        arr = tifffile.imread(io.BytesIO(body)) if kind == "raster" else None
        recs.append((kind, size, len(body), arr, idx.get(md5, {})))

    W, TILE_W, TILE_H = 1600, 360, 240
    cols = min(4, len(recs))
    rows = -(-len(recs) // cols)
    top = 120
    tiles_h = rows * (TILE_H + 92)
    photo = None
    arw = next((base + e for e in (".ARW", ".arw") if os.path.exists(base + e)), None)
    if arw and "--no-photo" not in sys.argv:
        photo, orient = embedded_photo(arw)
    comp_h = 980 if photo is not None else 0
    H = top + tiles_h + (comp_h + 80 if comp_h else 20)
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f_title, f_sub, f_lab, f_small = font(34), font(18), font(19), font(15)
    dr.text((40, 30), f"{os.path.basename(acr)}, decomposed: what the container actually holds", fill=TXT, font=f_title)
    dr.text((40, 78), f"{len(recs)} records, labelled from the sibling XMP by md5 · rasters shown as stored (sensor orientation)",
            fill=DIM, font=f_sub)

    gx = (W - cols * TILE_W) // (cols + 1)
    for i, (kind, size, blen, arr, a) in enumerate(recs):
        r, c = divmod(i, cols)
        x, y = gx + c * (TILE_W + gx), top + r * (TILE_H + 92)
        color = COLORS[i % len(COLORS)]
        dr.rounded_rectangle([x - 8, y - 8, x + TILE_W + 8, y + TILE_H + 84], 10, fill=PANEL, outline=color, width=2)
        l1, l2 = label(a, kind, firefly)
        if arr is not None:
            a8 = to_u8(arr)
            t = fit(Image.fromarray(a8 if a8.ndim == 2 else a8[..., :3]).convert("RGB"), TILE_W, TILE_H)
            img.paste(t, (x + (TILE_W - t.width) // 2, y + (TILE_H - t.height) // 2))
            h, w = arr.shape[:2]
            ch = 1 if arr.ndim == 2 else arr.shape[2]
            info = f"{w}x{h} · {ch}ch {arr.dtype}" + (f" · Origin {a['Origin']}" if "Origin" in a else "")
        else:
            dr.text((x + 20, y + 80), f"{kind} record", fill=color, font=f_lab)
            dr.text((x + 20, y + 110), f"{size:,} B → {blen:,} B inflated", fill=TXT, font=f_small)
            dr.text((x + 20, y + 134), "12-byte frame + <x:xmpmeta>", fill=DIM, font=f_small)
            info = f"{size:,} B · not an image"
        dr.text((x, y + TILE_H + 8), f"record {i} · {l1}", fill=color, font=f_lab)
        dr.text((x, y + TILE_H + 34), info, fill=DIM, font=f_small)
        dr.text((x, y + TILE_H + 56), l2, fill=DIM, font=f_small)

    if photo is not None:
        cy = top + tiles_h + 30
        dr.text((40, cy), "placed on the photo: AI masks outlined at XMP Origin on the FullMaskSize canvas; Remove target boxed",
                fill=TXT, font=f_lab)
        fms = next((a["FullMaskSize"] for *_, a in recs if "FullMaskSize" in a), None)
        cw, chh = map(int, fms.split(",")) if fms else photo.size
        canvas = photo.resize((cw, chh), Image.LANCZOS)
        canvas = Image.blend(canvas, Image.new("RGB", canvas.size, (0, 0, 0)), 0.25)
        cd = ImageDraw.Draw(canvas)
        for i, (kind, size, blen, arr, a) in enumerate(recs):
            col = COLORS[i % len(COLORS)]
            if arr is not None and arr.ndim == 2 and "Origin" in a:
                ox, oy = map(int, a["Origin"].split(","))
                m = Image.fromarray(((to_u8(arr) > 127) * 255).astype(np.uint8))
                edge = np.asarray(m.filter(ImageFilter.MaxFilter(9)), dtype=bool) & \
                       ~np.asarray(m.filter(ImageFilter.MinFilter(3)), dtype=bool)
                region = np.asarray(canvas.crop((ox, oy, ox + arr.shape[1], oy + arr.shape[0]))).copy()
                region[edge] = col
                canvas.paste(Image.fromarray(region), (ox, oy))
                cd = ImageDraw.Draw(canvas)
            if a.get("_ref") == "pm_patch" and "pm_target_left" in a:
                sx = cw / (float(a["pm_full_image_right"]) - float(a["pm_full_image_left"]))
                sy = chh / (float(a["pm_full_image_bottom"]) - float(a["pm_full_image_top"]))
                box = [float(a["pm_target_left"]) * sx, float(a["pm_target_top"]) * sy,
                       float(a["pm_target_right"]) * sx, float(a["pm_target_bottom"]) * sy]
                cd.rectangle(box, outline=col, width=8)
        canvas = to_display(canvas, orient)
        s = min((W - 80) / canvas.width, (comp_h - 60) / canvas.height)
        disp = canvas.resize((int(canvas.width * s), int(canvas.height * s)), Image.LANCZOS)
        img.paste(disp, ((W - disp.width) // 2, cy + 44))
    img.save(out)
    print("written:", out)

if __name__ == "__main__":
    main()
