r"""Decompose a real .acr into its rasters and show where each one lands.

Top row: every record decoded (grayscale AI masks, RGB Remove-tool patches),
labelled from the sibling XMP. Bottom: the photo (the ARW's embedded
full-size JPEG) with each mask placed by the XMP's Origin on the
FullMaskSize canvas.

Needs: pip install tifffile imagecodecs numpy pillow
Run:   python scripts/make_acr_decomposed_image.py <file.acr> [--out PNG] [--no-photo]
       (expects <name>.xmp and, optionally, <name>.ARW beside the .acr;
        --no-photo skips the composite, e.g. when the photo shows people)
Default output: docs/assets/acr-decomposed.png
"""
import os, re, sys, struct, hashlib, io
import numpy as np, tifffile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BG, PANEL, EDGE, TXT, DIM = (13, 17, 23), (22, 27, 34), (48, 54, 61), (230, 237, 243), (139, 148, 158)
COLORS = [(255, 166, 87), (88, 166, 255), (126, 231, 135), (210, 168, 255),
          (255, 123, 114), (121, 192, 255), (227, 179, 65), (247, 120, 186)]
SUBTYPE = {"1": "Subject", "3": "People"}
SUBCAT = {"22": "Background", "50006": "Sky", "50007": "Water", "11": "Clothes"}

def font(size):
    for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()

def records(data):
    n, = struct.unpack("<I", data[12:16])
    for i in range(n):
        e = data[20 + 32 * i: 52 + 32 * i]
        size, off = struct.unpack("<QQ", e[16:32])
        rec = data[off:off + size]
        yield hashlib.md5(rec).hexdigest().upper(), rec[16:]

def xmp_index(path):
    """md5 -> dict of attributes of the XMP element that references it."""
    if not os.path.exists(path):
        return {}
    s = open(path, "rb").read().decode("utf-8", "replace")
    idx = {}
    for el in re.finditer(r"<[^<>]*crs:(?:MaskDigest|pm_patch|pm_patch_variation)=\"[0-9A-Fa-f]{32}\"[^<>]*>", s):
        a = dict(re.findall(r'crs:(\w+)="([^"]*)"', el.group(0)))
        for k in ("MaskDigest", "pm_patch", "pm_patch_variation"):
            if k in a:
                idx.setdefault(a[k].upper(), dict(a, _ref=k))
    return idx

def label(a):
    if a.get("_ref", "").startswith("pm_"):
        return "Remove-tool patch", a["_ref"]
    name = re.sub(r"\s*\d+$", "", a.get("MaskName", "")).strip() or "AI mask"
    st = a.get("MaskSubType", "?")
    kind = SUBTYPE.get(st) or SUBCAT.get(a.get("MaskSubCategoryID", ""), "scene")
    return name, f"Mask/Image · subtype {st} ({kind})"

def embedded_photo(arw):
    """Largest embedded JPEG, rotated per the ARW's IFD0 Orientation."""
    d = open(arw, "rb").read()
    best, pos = None, 0
    while (i := d.find(b"\xff\xd8\xff", pos)) != -1:
        pos = i + 3
        e = d.find(b"\xff\xd9", i)
        if e != -1 and (best is None or e + 2 - i > len(best)):
            best = d[i:e + 2]
    img = Image.open(io.BytesIO(best)).convert("RGB")
    ifd = struct.unpack("<I", d[4:8])[0]
    n = struct.unpack("<H", d[ifd:ifd + 2])[0]
    for k in range(n):
        tag, typ, cnt, val = struct.unpack("<HHIH", d[ifd + 2 + 12 * k: ifd + 12 + 12 * k])
        if tag == 0x0112:
            img = {3: img.rotate(180, expand=True), 6: img.rotate(-90, expand=True),
                   8: img.rotate(90, expand=True)}.get(val, img)
    return img

def to_u8(a):
    a = np.asarray(a)
    if a.dtype != np.uint8:
        mx = float(a.max()) or 1.0
        a = (a.astype(np.float64) * (255.0 / mx)).astype(np.uint8)
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
    data = open(acr, "rb").read()
    recs = []
    for md5, tif in records(data):
        arr = tifffile.imread(io.BytesIO(tif))
        recs.append((md5, arr, idx.get(md5, {})))

    W, TILE_W, TILE_H, PAD = 1600, 360, 240, 28
    cols = min(4, len(recs))
    rows = -(-len(recs) // cols)
    top = 120
    tiles_h = rows * (TILE_H + 92)
    photo = None
    for ext in (".ARW", ".arw"):
        if os.path.exists(base + ext) and "--no-photo" not in sys.argv:
            photo = embedded_photo(base + ext)
    comp_h = 760 if photo is not None else 0
    H = top + tiles_h + (comp_h + 80 if comp_h else 20)
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    f_title, f_sub, f_lab, f_small = font(34), font(18), font(19), font(15)
    name = os.path.basename(acr)
    dr.text((40, 30), f"{name}, decomposed: what the container actually holds", fill=TXT, font=f_title)
    dr.text((40, 78), f"{len(recs)} records · each decoded from JPEG-XL tiles (tag 52546) · labels from the sibling XMP, matched by md5",
            fill=DIM, font=f_sub)

    # ---- tiles ----
    gx = (W - cols * TILE_W) // (cols + 1)
    for i, (md5, arr, a) in enumerate(recs):
        r, c = divmod(i, cols)
        x = gx + c * (TILE_W + gx)
        y = top + r * (TILE_H + 92)
        color = COLORS[i % len(COLORS)]
        dr.rounded_rectangle([x - 8, y - 8, x + TILE_W + 8, y + TILE_H + 84], 10, fill=PANEL, outline=color, width=2)
        a8 = to_u8(arr)
        t = Image.fromarray(a8 if a8.ndim == 2 else a8[..., :3]).convert("RGB")
        t = fit(t, TILE_W, TILE_H)
        img.paste(t, (x + (TILE_W - t.width) // 2, y + (TILE_H - t.height) // 2))
        l1, l2 = label(a) if a else ("unreferenced", "")
        h, w = arr.shape[:2]
        ch = 1 if arr.ndim == 2 else arr.shape[2]
        dr.text((x, y + TILE_H + 8), f"record {i} · {l1}", fill=color, font=f_lab)
        dr.text((x, y + TILE_H + 34), f"{w}x{h} · {ch}ch {arr.dtype}" + (f" · Origin {a['Origin']}" if "Origin" in a else ""),
                fill=DIM, font=f_small)
        dr.text((x, y + TILE_H + 56), l2, fill=DIM, font=f_small)

    # ---- composite ----
    if photo is not None:
        cy = top + tiles_h + 30
        dr.text((40, cy), "placed on the photo: mask outline at XMP Origin on the FullMaskSize canvas (dashed box = raster extent)",
                fill=TXT, font=f_lab)
        fms = next((a["FullMaskSize"] for _, _, a in recs if "FullMaskSize" in a), None)
        cw, chh = (map(int, fms.split(","))) if fms else (photo.width, photo.height)
        canvas = photo.resize((cw, chh), Image.LANCZOS)
        canvas = Image.blend(canvas, Image.new("RGB", canvas.size, (0, 0, 0)), 0.25)
        boxes = []
        for i, (md5, arr, a) in enumerate(recs):
            if "Origin" not in a or arr.ndim != 2:
                continue
            ox, oy = map(int, a["Origin"].split(","))
            m = Image.fromarray(((to_u8(arr) > 127) * 255).astype(np.uint8))
            edge = np.asarray(m.filter(ImageFilter.MaxFilter(9)), dtype=bool) & \
                   ~np.asarray(m.filter(ImageFilter.MinFilter(3)), dtype=bool)
            region = np.asarray(canvas.crop((ox, oy, ox + arr.shape[1], oy + arr.shape[0]))).copy()
            region[edge] = COLORS[i % len(COLORS)]
            canvas.paste(Image.fromarray(region), (ox, oy))
            boxes.append((i, ox, oy, arr.shape[1], arr.shape[0]))
        s = min((W - 80) / cw, (comp_h - 60) / chh)
        disp = canvas.resize((int(cw * s), int(chh * s)), Image.LANCZOS)
        px, py = (W - disp.width) // 2, cy + 44
        img.paste(disp, (px, py))
        for i, ox, oy, w, h in boxes:
            col = COLORS[i % len(COLORS)]
            x0, y0, x1, y1 = px + ox * s, py + oy * s, px + (ox + w) * s, py + (oy + h) * s
            for k in range(int(x0), int(x1), 14):
                dr.line([k, y0, min(k + 7, x1), y0], fill=col, width=2)
                dr.line([k, y1, min(k + 7, x1), y1], fill=col, width=2)
            for k in range(int(y0), int(y1), 14):
                dr.line([x0, k, x0, min(k + 7, y1)], fill=col, width=2)
                dr.line([x1, k, x1, min(k + 7, y1)], fill=col, width=2)
            dr.text((x0 + 6, y0 + 4), f"r{i}", fill=col, font=f_lab)
    img.save(out)
    print("written:", out)

if __name__ == "__main__":
    main()
