r"""Every figure of the "three files and a photo" post, in one house style.

All values are read from the DSC03049 family (ARW, XMP, ACR, JPGs); the cache
statistics come from the measurements in docs/diagrams.md and are marked as such.

Needs: pip install tifffile imagecodecs numpy pillow  (and Chrome or Edge)
Run:   python scripts/make_blog_figures.py <dir>/<NAME> [--out DIR] [--only a,b]
Writes <DIR>/blog-*.svg + .png (default DIR: docs/assets/blog)
"""
import os, re, sys, io, struct, hashlib, zlib
import numpy as np
from PIL import Image, ImageOps, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blog_theme import *                      # noqa: F401,F403
from blog_theme import Fig, esc, rgba         # noqa: E402
from acr_reader import read_table, classify, tiff_info   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hx = lambda v: f"0x{v:X}"
kb = lambda v: f"{v / 1000:,.0f} KB" if v < 1e6 else f"{v / 1e6:.1f} MB"


# ================================================================== inputs
class Family:
    """The DSC03049 export family, parsed once."""

    def __init__(self, stem):
        self.stem, self.name = stem, os.path.basename(stem)
        self.arw = open(stem + ".ARW", "rb").read()
        self.xmp = open(stem + ".xmp", "rb").read().decode("utf-8", "replace")
        self.acr = open(stem + ".acr", "rb").read()
        self._arw_map()
        self._acr_map()

    # ---- ARW
    def ifd(self, off):
        d = self.arw
        n = struct.unpack("<H", d[off:off + 2])[0]
        t = {}
        for k in range(n):
            p = off + 2 + 12 * k
            tag, typ, cnt, val = struct.unpack("<HHII", d[p:p + 12])
            if typ == 3 and cnt == 1:
                val &= 0xFFFF
            t[tag] = dict(typ=typ, cnt=cnt, val=val, raw=d[p:p + 12], pos=p)
        nxt = struct.unpack("<I", d[off + 2 + 12 * n: off + 6 + 12 * n])[0]
        return n, t, nxt

    def jpeg(self, off, size):
        return Image.open(io.BytesIO(self.arw[off:off + size])).convert("RGB")

    def _arw_map(self):
        n0, t0, i1 = self.ifd(8)
        ne, te, _ = self.ifd(t0[0x8769]["val"])
        n1, t1, i2 = self.ifd(i1)
        n2, t2, _ = self.ifd(i2)
        ns, ts, _ = self.ifd(t0[0x014A]["val"])
        self.a = dict(size=len(self.arw), ifd0_n=n0, exif=t0[0x8769]["val"], exif_n=ne,
                      maker=te[0x927C]["val"], maker_len=te[0x927C]["cnt"],
                      ifd1=i1, ifd1_n=n1, thumb=t1[0x0201]["val"], thumb_len=t1[0x0202]["val"],
                      ifd2=i2, ifd2_n=n2, full=t2[0x0201]["val"], full_len=t2[0x0202]["val"],
                      sub=t0[0x014A]["val"], sub_n=ns, strip=ts[0x0111]["val"], strip_len=ts[0x0117]["val"],
                      strip_w=ts[0x0100]["val"], strip_h=ts[0x0101]["val"],
                      prev=t0[0x0201]["val"], prev_len=t0[0x0202]["val"],
                      orient=t0.get(0x0112, {}).get("val", 1))
        self.sub_tags = ts

    # ---- ACR
    def _acr_map(self):
        ver, fmt, res, entries = read_table(self.acr)
        self.acr_head = dict(ver=ver, fmt=fmt, res=res, n=len(entries))
        refs = {}
        for el in re.finditer(r"<[^<>]*crs:(?:MaskDigest|pm_patch\w*|IngestInfo)=\"[0-9A-Fa-f]{32}\"[^<>]*>", self.xmp):
            a = dict(re.findall(r'crs:(\w+)="([^"]*)"', el.group(0)))
            for k in ("MaskDigest", "pm_patch", "pm_patch_variation", "pm_patch_mask", "IngestInfo"):
                if k in a and re.fullmatch(r"[0-9A-Fa-f]{32}", a[k]):
                    refs.setdefault(a[k].upper(), dict(a, _ref=k))
        for m in re.finditer(r'crs:pm_patch_variation="([0-9A-F]{32})"', self.xmp, re.I):   # element text form
            refs.setdefault(m.group(1).upper(), {"_ref": "pm_patch_variation"})
        self.records = []
        for i, (md5, size, off) in sorted(enumerate(entries), key=lambda e: e[1][2]):
            kind, body, _ = classify(self.acr[off:off + size])
            r = dict(idx=i, md5=md5, size=size, off=off, kind=kind, ref=refs.get(md5, {}))
            if kind == "raster":
                import tifffile
                r["img"] = tifffile.imread(io.BytesIO(body))
                r["tags"] = tiff_info(body)
            else:
                r["inflated"] = body
            self.records.append(r)
        self.records.sort(key=lambda r: r["off"])

    def rec_label(self, r):
        a, ref = r["ref"], r["ref"].get("_ref", "")
        if ref == "MaskDigest":
            return re.sub(r"\s*\d+$", "", a.get("MaskName", "")).strip() or "AI object selection"
        return {"IngestInfo": "receipt", "pm_patch": "chosen fill", "pm_patch_variation": "candidate fill",
                "pm_patch_mask": "fill mask"}.get(ref, "?")

    def attr(self, k, default=None):
        m = re.search(r'crs:%s="([^"]*)"' % k, self.xmp)
        return m.group(1) if m else default

    def photo(self, which="Original"):
        p = self.stem + ("-Original.JPG" if which == "Original" else "-pass0.jpg" if which == "pass0" else ".jpg")
        return ImageOps.exif_transpose(Image.open(p)).convert("RGB")


def rot(img, orient):
    return {3: img.rotate(180, expand=True), 6: img.rotate(-90, expand=True),
            8: img.rotate(90, expand=True)}.get(orient, img)

def u8(a):
    a = np.asarray(a)
    if a.dtype != np.uint8:
        lo, hi = np.percentile(a, 0.5), np.percentile(a, 99.5)
        a = ((a.astype(np.float64) - lo) / max(1.0, hi - lo) * 255).clip(0, 255).astype(np.uint8)
    return a

def tint(mask, color, base=None, ghost=0.25):
    """Mask (L) -> RGBA: tinted where selected, faint photo (or dark) elsewhere."""
    m = np.asarray(mask, np.float32)[..., None] / 255.0
    col = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0
    if base is None:
        b = np.full(m.shape[:2] + (3,), 0.06, np.float32)
    else:
        b = np.asarray(base.resize(mask.size), np.float32) / 255.0 * ghost
    rgb = b * (1 - m) + (col * 0.9 + 0.1) * m
    return Image.fromarray((rgb.clip(0, 1) * 255).astype(np.uint8), "RGB")


# ================================================================== figures
def fig_tiff(F, out):
    a = F.a
    g = Fig(1600, 960)
    g.header("TIFF is a pointer chase, not a stream",
             f"the format under both the ARW and every ACR raster · real offsets and bytes from {F.name}.ARW",
             kicker="TIFF 101", color=CYAN)

    # ---- A: the file as offsets
    g.card(60, 200, 1480, 300, CYAN, "the file, read by jumping", tag="not to scale")
    segs = [("header", 0, 110, PURPLE), ("IFD0", 8, 150, CYAN), ("ExifIFD", a["exif"], 150, DIM),
            (None, None, 70, None), ("SubIFD", a["sub"], 150, RED), (None, None, 110, None),
            ("sensor strip", a["strip"], 520, GREEN)]
    x, y0, h, pos = 150, 350, 56, {}
    for name, off, w, col in segs:
        if name is None:
            g.add(f'<rect x="{x + 6}" y="{y0 + 20}" width="{w - 12}" height="16" rx="8" fill="none" '
                  f'stroke="{FAINT}" stroke-dasharray="3 5"/>')
        else:
            g.add(f'<rect x="{x + 3}" y="{y0}" width="{w - 6}" height="{h}" rx="10" fill="{col}" fill-opacity="0.16" '
                  f'stroke="{col}" stroke-width="2"/>')
            g.text(x + w / 2, y0 + 35, name, 17, col, SANS, "bold", "middle")
            g.text(x + w / 2, y0 + h + 30, hx(off), 15, DIM, MONO, "normal", "middle")
            pos[name] = (x + w / 2, w)
        x += w
    def hop(a_, b_, lift, label, col, dx=12):
        (x1, _), (x2, _) = pos[a_], pos[b_]
        x1o, x2o = x1 + dx, x2 - 12
        mx = (x1o + x2o) / 2
        g.arrow(f"M {x1o:.0f} {y0 - 4} C {x1o:.0f} {y0 - lift}, {x2o:.0f} {y0 - lift}, {x2o:.0f} {y0 - 6}", col)
        g.chip(mx, y0 - lift * 0.75 + 5, label, col, 14, "middle")
    hop("header", "IFD0", 70, "→ 0x8", PURPLE)
    hop("IFD0", "SubIFD", 120, "0x014A", RED, -40)
    hop("IFD0", "ExifIFD", 56, "0x8769", DIM, 40)
    hop("SubIFD", "sensor strip", 104, "0x0111 StripOffsets", GREEN)
    g.text(150, 478, "nothing is found by scanning: the 8-byte header points at a directory, the directory points at data",
           16, DIM)

    # ---- B: one entry
    g.card(60, 540, 960, 370, ORANGE, "one IFD entry = 12 bytes", tag="from the SubIFD")
    fields = [("tag", 2, PURPLE), ("type", 2, BLUE), ("count", 4, CYAN), ("value / offset", 4, ORANGE)]
    X0, U = 100, 52
    x = X0
    for name, n, col in fields:
        g.add(f'<rect x="{x + 2}" y="606" width="{n * U - 4}" height="44" rx="8" fill="{col}" fill-opacity="0.18" '
              f'stroke="{col}"/>')
        g.text(x + n * U / 2, 634, f"{name} · {n} B", 15, col, MONO, "bold", "middle")
        x += n * U
    rows = [(0x0100, "ImageWidth = %d" % a["strip_w"], "fits in 4 bytes → stored inline", GREEN),
            (0x0111, "StripOffsets → " + hx(a["strip"]), "too big → an offset: jump there", ORANGE)]
    for k, (tag, what, why, col) in enumerate(rows):
        y = 676 + k * 82
        raw = F.sub_tags[tag]["raw"]
        x = X0
        for (name, n, fc), chunk in zip(fields, (raw[0:2], raw[2:4], raw[4:8], raw[8:12])):
            hot = name.startswith("value")
            g.add(f'<rect x="{x + 2}" y="{y}" width="{n * U - 4}" height="50" rx="8" fill="{col if hot else CARD}" '
                  f'fill-opacity="{0.16 if hot else 1}" stroke="{col if hot else RULE}"/>')
            g.text(x + n * U / 2, y + 32, chunk.hex(" ").upper(), 16, col if hot else TXT, MONO, "normal", "middle")
            x += n * U
        g.text(X0 + 12 * U + 26, y + 22, what, 17, col, MONO, "bold")
        g.text(X0 + 12 * U + 26, y + 44, why, 15, DIM)
    g.add(f'<rect x="{X0 + 2}" y="842" width="{12 * U - 4}" height="40" rx="8" fill="none" stroke="{FAINT}" '
          f'stroke-dasharray="6 5"/>')
    g.text(X0 + 6 * U, 868, "… N entries, then 4 B: next IFD, or 0", 15, DIM, MONO, "normal", "middle")
    g.text(X0 + 12 * U + 26, 868, "little-endian: bytes read backwards", 15, DIM)

    # ---- C: stream vs chase
    g.card(1060, 540, 480, 370, GREEN, "stream vs pointer chase")
    g.text(1090, 618, "PNG · read top to bottom", 16, TXT, SANS, "bold")
    for i, n in enumerate(["sig", "IHDR", "IDAT", "IDAT", "IEND"]):
        g.add(f'<rect x="{1090 + i * 84}" y="634" width="76" height="34" rx="7" fill="{BLUE}" fill-opacity="0.15" stroke="{BLUE}"/>')
        g.text(1128 + i * 84, 657, n, 14, BLUE, MONO, "bold", "middle")
    g.arrow("M 1090 688 L 1500 688", BLUE, 2, glow=False)
    g.text(1090, 740, "TIFF · jump, jump, jump", 16, TXT, SANS, "bold")
    for i, n in enumerate(["hdr", "data", "IFD", "data"]):
        g.add(f'<rect x="{1090 + i * 104}" y="790" width="92" height="34" rx="7" fill="{ORANGE}" fill-opacity="0.15" stroke="{ORANGE}"/>')
        g.text(1136 + i * 104, 813, n, 14, ORANGE, MONO, "bold", "middle")
    g.arrow("M 1136 786 C 1136 752, 1344 752, 1344 784", ORANGE, 2, glow=False)          # hdr -> IFD (over)
    g.arrow("M 1330 828 C 1330 852, 1150 852, 1150 830", ORANGE, 2, glow=False)          # IFD -> data (under)
    g.arrow("M 1366 828 C 1366 852, 1440 852, 1440 830", ORANGE, 2, glow=False)          # IFD -> data (under)
    g.text(1090, 880, "ARW: 49 49 2A 00 at byte 0", 15, DIM, MONO)
    g.text(1090, 902, "ACR raster: 49 49 2A 00 at byte 16", 15, DIM, MONO)
    g.signature()
    g.render(os.path.join(out, "blog-tiff-pointer-chase"))


def bayer(img, cell=6):
    """A crop drawn as the colour-filter mosaic a sensor actually records."""
    a = np.asarray(img, np.float32) / 255.0
    h, w = a.shape[:2]
    m = np.zeros_like(a)
    m[0::2, 0::2, 0] = a[0::2, 0::2, 0]       # R G
    m[0::2, 1::2, 1] = a[0::2, 1::2, 1]       # G B
    m[1::2, 0::2, 1] = a[1::2, 0::2, 1]
    m[1::2, 1::2, 2] = a[1::2, 1::2, 2]
    m = (m * 1.6).clip(0, 1)
    big = Image.fromarray((m * 255).astype(np.uint8)).resize((w * cell, h * cell), Image.NEAREST)
    g = np.asarray(big).copy()
    g[::cell, :, :] = g[::cell, :, :] // 3          # cell grid
    g[:, ::cell, :] = g[:, ::cell, :] // 3
    return Image.fromarray(g)


def fig_arw(F, out):
    a = F.a
    g = Fig(1600, 1150)
    g.header(f"{F.name}.ARW: the photo hides one level down",
             f"{a['size']:,} bytes of little-endian TIFF · every offset read from the file", kicker="ARW", color=RED)

    # ---- A: to scale
    g.card(60, 200, 1480, 210, GREEN, "where the 45.6 MB go", tag="to scale")
    X0, X1, y = 100, 1500, 290
    sc = (X1 - X0) / a["size"]
    meta_end = a["full"]
    parts = [(0, meta_end, PURPLE), (a["full"], a["full"] + a["full_len"], ORANGE),
             (a["strip"], a["strip"] + a["strip_len"], GREEN)]
    for s, e, col in parts:
        x0, x1 = X0 + s * sc, X0 + e * sc
        g.add(f'<rect x="{x0:.1f}" y="{y}" width="{max(3, x1 - x0):.1f}" height="60" rx="4" fill="{col}" '
              f'fill-opacity="0.25" stroke="{col}" stroke-width="1.5"/>')
    fx0 = X0 + a["full"] * sc
    g.text(fx0 + (a["full_len"] * sc) / 2, y + 27, "full JPEG", 14, ORANGE, SANS, "bold", "middle")
    g.text(fx0 + (a["full_len"] * sc) / 2, y + 47, kb(a["full_len"]), 13, ORANGE, MONO, "normal", "middle")
    sx = X0 + a["strip"] * sc
    pct = a["strip_len"] / a["size"] * 100
    g.text(sx + 30, y + 38, f"RAW sensor strip · {a['strip_w']}×{a['strip_h']} · {kb(a['strip_len'])} · "
                            f"{pct:.1f}% of the file", 20, GREEN, SANS, "bold")
    g.text(X0, y - 14, f"headers, EXIF, MakerNotes, thumbnail, preview: {kb(meta_end)} ↓", 15, PURPLE, MONO)
    g.text(X0, y + 88, "0x0", 14, DIM, MONO)
    g.text(sx, y + 88, hx(a["strip"]), 14, DIM, MONO, "normal", "middle")
    g.text(X1, y + 88, f"EOF {hx(a['size'])}", 14, DIM, MONO, "normal", "end")

    # ---- B: the pointer tree
    g.card(60, 440, 1480, 650, CYAN, "the pointer chase", tag="tag numbers on the arrows")
    C = [470, 830, 1190]
    CW = [280, 280, 310]
    R = [500, 640, 780, 920]
    NH = 110
    nodes = {}
    def node(key, c, r, title, sub, col, img=None, w=None, glow=False):
        x, yy, w = C[c], R[r], w or CW[c]
        g.card(x, yy, w, NH, col, None, glow=glow, rx=14)
        tx = x + 18
        if img is not None:
            g.image(x + 10, yy + 10, 132, NH - 20, img, "JPEG")
            g.add(f'<rect x="{x + 10}" y="{yy + 10}" width="132" height="{NH - 20}" rx="6" fill="none" stroke="{col}" stroke-opacity="0.5"/>')
            tx = x + 156
        g.text(tx, yy + 40, title, 18, col, SANS, "bold")
        for i, s in enumerate(sub):
            g.text(tx, yy + 66 + i * 22, s, 14, DIM, MONO)
        nodes[key] = (x, yy, w)
    # root
    g.card(100, 640, 250, NH, CYAN, None, glow=True, rx=14)
    g.text(122, 680, "IFD0", 22, CYAN, SANS, "bold")
    g.text(122, 706, f"{a['ifd0_n']} entries @ 0x8", 14, DIM, MONO)
    g.text(122, 728, "the root directory", 14, DIM)

    full = F.jpeg(a["full"], a["full_len"])
    # the brightest, most colourful 22x15 patch: a lantern-lit part of the dragon
    small = np.asarray(full.resize((full.width // 8, full.height // 8)), np.float32)
    score = small.mean(2) + small.std(2) * 2
    score[:, :4] = score[:, -4:] = 0
    cy_, cx_ = np.unravel_index(np.argmax(score[4:-4, 4:-4]), score[4:-4, 4:-4].shape)
    cx_, cy_ = (cx_ + 4) * 8, (cy_ + 4) * 8
    crop = full.crop((cx_ - 11, cy_ - 7, cx_ + 11, cy_ + 8))
    node("exif", 0, 0, "ExifIFD", [f"{a['exif_n']} entries @ {hx(a['exif'])}", "dates, lens, exposure"], DIM)
    node("maker", 1, 0, "MakerNotes", [f"{a['maker_len']:,} B · Sony-private", "WB matrices, lens data"], DIM)
    node("sub", 0, 1, "SubIFD", [f"{a['sub_n']} entries @ {hx(a['sub'])}", "holds THE photo"], RED)
    node("strip", 1, 1, "sensor strip", [f"{a['strip_w']}×{a['strip_h']}", kb(a["strip_len"])], GREEN,
         img=bayer(crop))
    node("prev", 0, 2, "preview", [kb(a["prev_len"]), f"@ {hx(a['prev'])}"], YELLOW,
         img=F.jpeg(a["prev"], a["prev_len"]))
    node("ifd1", 0, 3, "IFD1", [f"@ {hx(a['ifd1'])}", f"+ {kb(a['thumb_len'])} thumb"], DIM,
         img=F.jpeg(a["thumb"], a["thumb_len"]))
    node("ifd2", 1, 3, "IFD2", [f"{a['ifd2_n']} entries", f"@ {hx(a['ifd2'])}"], DIM)
    node("full", 2, 3, "full-size JPEG", [f"{full.width}×{full.height}", kb(a["full_len"])], ORANGE, img=full, glow=True)

    chips = []
    def edge(src, dst, label, col, dash=False, from_root=False):
        if from_root:
            x1, y1 = 350, 695
        else:
            x, yy, w = nodes[src]; x1, y1 = x + w, yy + NH / 2
        x2, yy2, _ = nodes[dst]; y2 = yy2 + NH / 2
        mx = (x1 + x2) / 2
        g.arrow(f"M {x1} {y1} C {mx + 20} {y1}, {mx - 30} {y2}, {x2 - 4} {y2}", col, 2.2, dash)
        chips.append((x2 - 44 if from_root else mx, y2 + 5, label, col))     # drawn after every edge
    edge(None, "exif", "0x8769", DIM, from_root=True)
    edge(None, "sub", "0x014A", RED, from_root=True)
    edge(None, "prev", "0x0201", YELLOW, from_root=True)
    edge(None, "ifd1", "next", DIM, True, from_root=True)
    edge("exif", "maker", "0x927C", DIM)
    edge("sub", "strip", "0x0111", GREEN)
    edge("ifd1", "ifd2", "next", DIM, True)
    edge("ifd2", "full", "0x0201", ORANGE)
    for cx, cy, s, col in chips:
        g.chip(cx, cy, s, col, 13, "middle")

    # notes in the free column
    g.card(1190, 500, 310, 250, RED, "gotcha", dash=True, rx=14)
    for i, s in enumerate(["IFD0's own 0x0201 is a", f"{kb(a['prev_len'])} preview, not the frame.",
                           "The full frame hangs off", "IFD2: same tag, two", "next-IFD hops away."]):
        g.text(1214, 580 + i * 26, s, 16, TXT if i < 2 else DIM)
    g.card(1190, 780, 310, 110, GREEN, "recovery trick", dash=True, rx=14)
    g.text(1214, 846, "scan FFD8…FFD9, keep the", 15, DIM, MONO)
    g.text(1214, 868, "largest span → IFD2's frame", 15, DIM, MONO)
    g.text(100, 1060, "thumbnails shown as stored: the camera writes the frame sideways and sets Orientation = "
                      f"{a['orient']}; the sensor tile is drawn as the colour-filter mosaic it records", 14, DIM)
    g.signature()
    g.render(os.path.join(out, "blog-arw-map"))


def xmp_masks(F):
    kinds = {}
    for m in re.finditer(r'crs:What="(Mask/[A-Za-z]+)"', F.xmp):
        kinds[m.group(1)] = kinds.get(m.group(1), 0) + 1
    return kinds


def fig_xmp(F, out):
    g = Fig(1600, 1080)
    n_attr = len(set(re.findall(r'\scrs:(\w+)=', F.xmp[:F.xmp.find("<crs:")])))
    g.header("XMP is the program: numbers, points, recipes and pointers",
             f"{F.name}.xmp · {len(F.xmp.encode()):,} bytes of plain RDF/XML · open it in any text editor",
             kicker="XMP", color=PURPLE)

    # ---- editor
    EX, EY, EW, EH = 60, 200, 760, 800
    g.card(EX, EY, EW, EH, PURPLE, None)
    for i, c in enumerate((RED, YELLOW, GREEN)):
        g.add(f'<circle cx="{EX + 28 + i * 22}" cy="{EY + 28}" r="6" fill="{c}" fill-opacity="0.8"/>')
    g.text(EX + 110, EY + 34, f"{F.name}.xmp", 15, DIM, MONO)
    g.add(f'<line x1="{EX}" y1="{EY + 54}" x2="{EX + EW}" y2="{EY + 54}" stroke="{RULE}"/>')
    T, A, V, Cm = PURPLE, CYAN, ORANGE, FAINT
    code = [
        [("<x:xmpmeta ", T), ('xmlns:x="adobe:ns:meta/">', A)],
        [(" <rdf:RDF>", T)],
        [("  <rdf:Description ", T), ('xmlns:crs=".../camera-raw-settings/1.0/"', A)],
        [("    crs:Temperature=", A), ('"%s"' % F.attr("Temperature"), V), ("  crs:Tint=", A), ('"%s"' % F.attr("Tint"), V)],
        [("    crs:Exposure2012=", A), ('"%s"' % F.attr("Exposure2012"), V), ("  crs:Contrast2012=", A), ('"%s"' % F.attr("Contrast2012"), V)],
        [("    crs:Vibrance=", A), ('"%s"' % F.attr("Vibrance"), V), ("  … %d more attributes" % (n_attr - 6), Cm)],
        [("   <crs:ToneCurvePV2012><rdf:Seq>", T)],
        [("    <rdf:li>", T), ("0, 0", V), ("</rdf:li> <rdf:li>", T), ("62, 48", V), ("</rdf:li> …", T)],
        [("   <crs:MaskGroupBasedCorrections><rdf:Seq>", T)],
        [("    <rdf:li crs:CorrectionName=", T), ('"Mask 4"', V)],
        [("      crs:LocalExposure2012=", A), ('"0.05"', V), (">", T)],
        [("     <rdf:li crs:What=", T), ('"Mask/Gradient"', GREEN)],
        [("       crs:ZeroX=", A), ('"0.644674"', V), (" crs:ZeroY=", A), ('"0.528152"', V)],
        [("       crs:FullX=", A), ('"0.184809"', V), (" crs:FullY=", A), ('"0.500445"', V), ("/>", T)],
        [("    <rdf:li crs:CorrectionName=", T), ('"Mask 1"', V), (" …", Cm)],
        [("     <rdf:li crs:What=", T), ('"Mask/Image"', PINK), (" crs:MaskName=", A), ('"Sky"', V)],
        [("       crs:MaskDigest=", A), ('"329726F25D1981C3…"', PINK)],
        [("       crs:Origin=", A), ('"1567,0"', V), (" crs:FullMaskSize=", A), ('"2880,1920"', V), ("/>", T)],
        [("   <crs:RetouchAreas> ", T), ("crs:fill_method=", A), ('"firefly"', PINK)],
        [("       crs:pm_patch=", A), ('"C422DC2499BA83C7…"', PINK), (" …", Cm)],
    ]
    for i, parts in enumerate(code):
        y = EY + 92 + i * 34
        g.text(EX + 40, y, str(i + 1), 14, FAINT, MONO, "normal", "end")
        g.rich(EX + 56, y, parts, 15.5)
    # brackets: line ranges -> right cards
    groups = [(3, 5, CYAN, 300), (6, 7, BLUE, 510), (11, 13, GREEN, 710), (15, 19, PINK, 910)]   # -> card middles
    for l0, l1, col, ty in groups:
        y0, y1 = EY + 92 + l0 * 34 - 22, EY + 92 + l1 * 34 + 8
        g.add(f'<path d="M {EX + EW - 24} {y0} h 10 v {y1 - y0} h -10" fill="none" stroke="{col}" stroke-width="2.5" filter="url(#glow)"/>')
        g.arrow(f"M {EX + EW - 14} {(y0 + y1) / 2:.0f} C {EX + EW + 30} {(y0 + y1) / 2:.0f}, {EX + EW + 20} {ty}, 876 {ty}", col, 2.2)

    RX, RW = 880, 660
    # ---- globals = numbers (sliders)
    g.card(RX, 200, RW, 200, CYAN, "globals = numbers", tag=f"{n_attr} crs: attributes")
    sliders = [("Temp", float(F.attr("Temperature")), 2000, 50000, F.attr("Temperature") + "K", True),
               ("Exposure", float(F.attr("Exposure2012")), -5, 5, F.attr("Exposure2012"), False),
               ("Contrast", float(F.attr("Contrast2012")), -100, 100, F.attr("Contrast2012"), False),
               ("Vibrance", float(F.attr("Vibrance")), -100, 100, F.attr("Vibrance"), False)]
    for i, (name, v, lo, hi, txt, logs) in enumerate(sliders):
        col, row = i % 2, i // 2
        sx, sy = RX + 30 + col * 320, 280 + row * 66
        g.text(sx, sy, name, 15, TXT)
        g.text(sx + 280, sy, txt.replace("-", "−"), 15, CYAN, MONO, "bold", "end")
        f = (np.log(v) - np.log(lo)) / (np.log(hi) - np.log(lo)) if logs else (v - lo) / (hi - lo)
        g.add(f'<rect x="{sx}" y="{sy + 14}" width="280" height="6" rx="3" fill="#ffffff" fill-opacity="0.08"/>')
        a0, a1 = (0, f * 280) if logs else sorted((140, f * 280))      # fill from the left, or from zero
        g.add(f'<rect x="{sx + a0:.1f}" y="{sy + 14}" width="{max(2, a1 - a0):.1f}" height="6" rx="3" '
              f'fill="{CYAN}" fill-opacity="0.7"/>')
        g.add(f'<circle cx="{sx + f * 280:.1f}" cy="{sy + 17}" r="8" fill="{BG}" stroke="{CYAN}" stroke-width="2.5" filter="url(#glow)"/>')

    # ---- curves = points
    g.card(RX, 420, RW, 180, BLUE, "curves = a list of points", tag="ToneCurvePV2012")
    pts = [tuple(map(int, p.split(","))) for p in re.findall(r"<rdf:li>(\d+, \d+)</rdf:li>",
           F.xmp[F.xmp.find("<crs:ToneCurvePV2012>"):F.xmp.find("</crs:ToneCurvePV2012>")])]
    cx, cy, cs = RX + 30, 470, 110
    g.add(f'<rect x="{cx}" y="{cy}" width="{cs}" height="{cs}" fill="#ffffff" fill-opacity="0.03" stroke="{RULE}"/>')
    g.add(f'<line x1="{cx}" y1="{cy + cs}" x2="{cx + cs}" y2="{cy}" stroke="{FAINT}" stroke-dasharray="4 4"/>')
    P = [(cx + px / 255 * cs, cy + cs - py / 255 * cs) for px, py in pts]
    g.add(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in P)}" fill="none" stroke="{BLUE}" stroke-width="3" filter="url(#glow)"/>')
    for x, y in P:
        g.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{BG}" stroke="{BLUE}" stroke-width="2"/>')
    g.text(cx + cs + 34, 498, "  ".join(f"{a},{b}" for a, b in pts), 16, BLUE, MONO, "bold")
    g.text(cx + cs + 34, 528, "a gentle pull-down of shadows and midtones;", 15, DIM)
    g.text(cx + cs + 34, 552, "anything that won't fit an attribute", 15, DIM)
    g.text(cx + cs + 34, 574, "becomes a child rdf:Seq", 15, DIM)

    # ---- masks: recipe vs pointer
    km = xmp_masks(F)
    g.card(RX, 620, RW, 180, GREEN, "most masks = a recipe", tag="re-run every render")
    icons = [("linear", km.get("Mask/Gradient", 0), "4 floats"), ("radial", km.get("Mask/CircularGradient", 0), "box + feather"),
             ("brush", km.get("Mask/Paint", 0), "stroke points"), ("range", km.get("Mask/RangeMask", 0), "a colour/luma range")]
    for i, (n, c, what) in enumerate(icons):
        x = RX + 30 + i * 158
        g.add(f'<rect x="{x}" y="680" width="140" height="62" rx="10" fill="{GREEN}" fill-opacity="0.08" stroke="{GREEN}" stroke-opacity="0.5"/>')
        g.text(x + 14, 706, f"{n} ×{c}", 16, GREEN, SANS, "bold")
        g.text(x + 14, 730, what, 13.5, DIM)
    g.text(RX + 30, 774, "geometry and thresholds only: no pixels, nothing to store", 15, DIM)

    g.card(RX, 820, RW, 180, PINK, "AI masks + Remove = a pointer", tag="→ the .acr", glow=True)
    g.text(RX + 30, 894, f"Mask/Image ×{km.get('Mask/Image', 0)}   ·   Generative Remove ×1", 17, PINK, SANS, "bold")
    g.text(RX + 30, 924, "a model's output can't be re-derived exactly, so the XMP", 15, DIM)
    g.text(RX + 30, 946, "keeps an MD5 (MaskDigest, pm_patch …) and an Origin", 15, DIM)
    g.text(RX + 30, 974, "the pixels themselves live in the ACR", 15, TXT)
    g.signature()
    g.render(os.path.join(out, "blog-xmp-anatomy"))


def fig_xmp_rules(F, out):
    g = Fig(1600, 760)
    g.header("Two XMP rules that decide whether anything works",
             "the name must match byte for byte · the same payload wears different envelopes", kicker="XMP", color=PURPLE)
    # naming
    g.card(60, 200, 600, 480, GREEN, "rule 1 · the name")
    rows = [(f"{F.name}.ARW", TXT, None), (f"{F.name}.xmp", GREEN, "✓ read"), (f"{F.name}.acr", GREEN, "✓ read"),
            (f"2026-09-25_{F.name}.xmp", RED, "✗ ignored")]
    for i, (n, col, verdict) in enumerate(rows):
        y = 272 + i * 74
        g.add(f'<rect x="100" y="{y}" width="520" height="54" rx="10" fill="{col}" fill-opacity="0.08" stroke="{col}" '
              f'stroke-opacity="0.6"{" stroke-dasharray=" + chr(34) + "7 5" + chr(34) if col == RED else ""}/>')
        g.text(124, y + 34, n, 18, col, MONO, "bold")
        if verdict:
            g.text(600, y + 34, verdict, 16, col, SANS, "bold", "end")
    g.text(100, 600, "same folder, byte-identical base name.", 16, TXT)
    g.text(100, 626, "a renamed sidecar fails silently: no warning anywhere", 16, DIM)
    g.text(100, 652, "the most expensive lesson of the recovery", 16, DIM)
    # envelopes
    g.card(700, 200, 840, 480, ORANGE, "rule 2 · the envelope")
    def payload(x, y, w):
        g.add(f'<rect x="{x}" y="{y}" width="{w}" height="44" rx="8" fill="{ORANGE}" fill-opacity="0.16" stroke="{ORANGE}"/>')
        g.text(x + w / 2, y + 28, "<x:xmpmeta> crs:* …", 15, ORANGE, MONO, "bold", "middle")
    def box(x, y, w, s, col):
        g.add(f'<rect x="{x}" y="{y}" width="{w}" height="44" rx="8" fill="{col}" fill-opacity="0.12" stroke="{col}"/>')
        g.text(x + w / 2, y + 28, s, 14, col, MONO, "normal", "middle")
    rows = [("cache settings\\", "bare, named by sha256"), ("cache auxiliary\\", "length + zlib(frame + XMP)"),
            ("Lightroom export", "bare, like the cache"), ("my recovery", "wrapped in <?xpacket?>")]
    for i, (where, how) in enumerate(rows):
        y = 266 + i * 96
        g.text(730, y + 20, where, 16, TXT, SANS, "bold")
        g.text(730, y + 44, how, 14, DIM)
        if i == 0 or i == 2:
            payload(990, y, 260)
        elif i == 1:
            box(990, y, 70, "u32", BLUE)
            g.add(f'<rect x="1066" y="{y - 8}" width="450" height="60" rx="10" fill="none" stroke="{PURPLE}" stroke-dasharray="6 4"/>')
            box(1076, y, 110, "12-B frame", DIM)
            payload(1194, y, 260)
            g.text(1506, y + 30, "zlib", 13, PURPLE, MONO, "bold", "end")
        else:
            box(990, y, 120, "<?xpacket?>", DIM)
            payload(1118, y, 260)
            box(1386, y, 130, "<?xpacket?>", DIM)
    g.text(730, 652, "the export adds nothing: copy the bare blob and give it the right name", 15, DIM)
    g.signature()
    g.render(os.path.join(out, "blog-xmp-rules"))


# cache measurements (docs/diagrams.md §6.8; 2,648 edit blobs, 84 export sidecars)
MASK_CENSUS = [("recipe", "linear gradient", 2932), ("recipe", "radial gradient", 167), ("recipe", "brush", 67),
               ("recipe", "range", 9), ("recipe", "ellipse", 6), ("recipe", "aggregate", 1),
               ("pixels", "AI scene: sky, background …", 11419), ("pixels", "AI subject", 5113),
               ("pixels", "AI people parts", 268), ("pixels", "Generative Remove (spots)", 44),
               ("pixels", "Remove (spots)", 16)]


def fig_acr_when(F, out):
    g = Fig(1600, 900)
    g.header("Which edits make an .acr? Only the ones with computed pixels",
             "84 export sidecars for the rule · 2,648 cached edit blobs for the census", kicker="ACR", color=ORANGE)
    g.card(60, 200, 520, 640, GREEN, "the export rule", tag="84 / 84")
    g.stat(100, 340, "77 / 77", "sidecars with an AI mask", GREEN, "→ every one came with an .acr", 76)
    g.stat(100, 530, "0 / 7", "sidecars without an AI mask", DIM, "→ none of them did", 76)
    g.add(f'<line x1="100" y1="610" x2="540" y2="640" stroke="{RULE}"/>')
    for i, (s, c) in enumerate([("an .acr exists exactly when", TXT), ("the edit contains an AI mask", TXT),
                                ("Remove fills ride along: 3 of the 77", DIM),
                                ("complex is not enough: a long brush", DIM), ("stroke is still just a recipe", DIM)]):
        g.text(100, 660 + i * 32, s, 18 if c == TXT else 16, GREEN if c == TXT else c, SANS, "bold" if c == TXT else "normal")

    g.card(620, 200, 920, 640, ORANGE, "every mask in my cache, by type", tag="log scale")
    LX, BX, BW = 660, 960, 440
    top = max(v for _, _, v in MASK_CENSUS)
    lg = lambda v: np.log10(v + 1) / np.log10(top * 1.6)
    y = 280
    for grp, col, head in (("recipe", PURPLE, "recipe · stored as geometry in the XMP, never a raster"),
                           ("pixels", ORANGE, "computed pixels · a raster in the ACR")):
        g.text(LX, y, head, 16, col, SANS, "bold")
        y += 22
        for gg, name, v in MASK_CENSUS:
            if gg != grp:
                continue
            g.text(LX, y + 24, name, 16, TXT)
            w = max(4, lg(v) * BW)
            g.add(f'<rect x="{BX}" y="{y + 8}" width="{BW}" height="20" rx="6" fill="#ffffff" fill-opacity="0.03"/>')
            g.add(f'<rect x="{BX}" y="{y + 8}" width="{w:.1f}" height="20" rx="6" fill="{col}" fill-opacity="0.75" '
                  f'filter="url(#glow)"/>')
            g.text(BX + w + 12, y + 25, f"{v:,}", 15, col, MONO, "bold")
            y += 40
        y += 34
    g.signature()
    g.render(os.path.join(out, "blog-acr-when"))


KIND_COL = {"mask": GREEN, "rgb": BLUE, "zlib": ORANGE}

def rkind(r):
    if r["kind"] != "raster":
        return "zlib"
    return "rgb" if np.asarray(r["img"]).ndim == 3 else "mask"


def fig_acr_anatomy(F, out):
    h, n = F.acr_head, F.acr_head["n"]
    size = len(F.acr)
    g = Fig(1600, 1190)
    g.header(f"Anatomy of {F.name}.acr",
             f"{size:,} bytes · a 20-byte header · {n} × 32-byte table entries · {n} records on 4-byte boundaries",
             kicker="ACR", color=ORANGE)
    g.card(60, 200, 1480, 250, CYAN, "the whole file", tag="to scale")
    X0, X1, Y = 100, 1500, 290
    sc = (X1 - X0) / size
    first = 20 + 32 * n
    g.add(f'<rect x="{X0}" y="{Y}" width="4" height="64" fill="{PURPLE}"/>')
    for r in F.records:
        col = KIND_COL[rkind(r)]
        x0, w = X0 + r["off"] * sc, max(3, r["size"] * sc)
        g.add(f'<rect x="{x0 + 1:.1f}" y="{Y}" width="{w - 2:.1f}" height="64" rx="4" fill="{col}" fill-opacity="0.22" '
              f'stroke="{col}" stroke-width="1.5"/>')
        if w > 26:
            g.text(x0 + w / 2, Y + 39, str(r["idx"]), 16, col, MONO, "bold", "middle")
    g.text(X0, Y + 92, "0x0", 14, DIM, MONO)
    g.text(X1, Y + 92, f"EOF {hx(size)}", 14, DIM, MONO, "normal", "end")
    lx = 300
    for col, s in ((PURPLE, f"header + table ({first} B)"), (GREEN, "AI-mask raster"), (BLUE, "Remove RGB patch"),
                   (ORANGE, "zlib receipt")):
        g.add(f'<circle cx="{lx}" cy="{Y + 87}" r="6" fill="{col}"/>')
        g.text(lx + 14, Y + 92, s, 15, TXT)
        lx += 40 + len(s) * 8
    g.text(X0, Y + 128, "numbers = position in the table, which is sorted by MD5, not by file order", 15, DIM)
    # zoom wedge from the header sliver

    # ---- header + table
    g.card(60, 500, 720, 340, PURPLE, "header · 20 bytes", tag="+0x00")
    raw = F.acr[:20]
    labels = [("magic", '"ACR\\0"'), ("version", str(h["ver"])), ("source", f'"{h["fmt"]}\\0"'),
              ("N records", str(n)), ("reserved", str(h["res"]))]
    for i, (lab, val) in enumerate(labels):
        x = 90 + i * 134
        g.add(f'<rect x="{x}" y="566" width="126" height="44" rx="8" fill="{PURPLE}" fill-opacity="0.14" stroke="{PURPLE}"/>')
        g.text(x + 63, 594, raw[i * 4:i * 4 + 4].hex(" ").upper(), 15, TXT, MONO, "normal", "middle")
        g.text(x + 63, 634, lab, 14, DIM, SANS, "normal", "middle")
        g.text(x + 63, 656, val, 15, PURPLE, MONO, "bold", "middle")
    g.text(90, 706, "then N × 32-byte entries, sorted by MD5:", 16, TXT, SANS, "bold")
    e1 = sorted(F.records, key=lambda r: r["idx"])[1]
    for x, w, lab, val in ((90, 330, "md5 · 16 B", e1["md5"][:8] + "…" + e1["md5"][-4:]),
                           (428, 150, "size · u64", f"{e1['size']:,}"), (586, 164, "offset · u64", hx(e1["off"]))):
        g.add(f'<rect x="{x}" y="726" width="{w - 8}" height="44" rx="8" fill="{CYAN}" fill-opacity="0.12" stroke="{CYAN}"/>')
        g.text(x + (w - 8) / 2, 754, val, 15, TXT, MONO, "normal", "middle")
        g.text(x + (w - 8) / 2, 794, lab, 14, DIM, SANS, "normal", "middle")
    g.text(90, 822, f"first record at 20 + 32 × N = {hx(first)}", 14, DIM, MONO)

    # ---- raster record
    nr = sum(1 for r in F.records if r["kind"] == "raster")
    g.card(820, 500, 720, 340, GREEN, f"raster record · {nr} of {n}")
    for i, (s, w) in enumerate((("02 00 00 00", 128), ("01 00 00 00", 128), ("00 × 8", 100))):
        x = 850 + sum(ww for _, ww in ((("", 128), ("", 128), ("", 100))[:i]))
        g.add(f'<rect x="{x}" y="566" width="{w - 8}" height="44" rx="8" fill="{GREEN}" fill-opacity="0.14" stroke="{GREEN}"/>')
        g.text(x + (w - 8) / 2, 594, s, 15, TXT, MONO, "normal", "middle")
    g.arrow("M 1214 588 L 1262 588", GREEN, 2)
    g.add(f'<rect x="1270" y="566" width="240" height="44" rx="8" fill="{GREEN}" fill-opacity="0.3" stroke="{GREEN}"/>')
    g.text(1390, 594, "TIFF · II*\\0 …", 15, GREEN, MONO, "bold", "middle")
    g.text(850, 634, "16-byte signature, same as the cache's auxiliary\\ files", 14, DIM)
    for i, s in enumerate(["one IFD, always the same 12 tags", "tiles compressed with JPEG-XL (52546)",
                           "cropped to the mask's bounding box", "md5 = md5(signature + TIFF)"]):
        g.add(f'<circle cx="858" cy="{682 + i * 36}" r="4" fill="{GREEN}"/>')
        g.text(874, 688 + i * 36, s, 16, TXT)

    # ---- zlib record
    z = next((r for r in F.records if r["kind"] == "zlib"), None)
    g.card(60, 880, 720, 240, ORANGE, f"zlib record · {n - nr} of {n} · the receipt")
    if z:
        zr = F.acr[z["off"]:z["off"] + 8]
        for x, w, s, lab in ((90, 150, zr[:4].hex(" ").upper(), f"u32 = {len(z['inflated'])}"),
                             (248, 150, zr[4:6].hex(" ").upper() + " …", "zlib stream")):
            g.add(f'<rect x="{x}" y="944" width="{w - 8}" height="44" rx="8" fill="{ORANGE}" fill-opacity="0.14" stroke="{ORANGE}"/>')
            g.text(x + (w - 8) / 2, 972, s, 15, TXT, MONO, "normal", "middle")
            g.text(x + (w - 8) / 2, 1010, lab, 14, DIM, SANS, "normal", "middle")
        g.arrow("M 398 966 L 440 966", ORANGE, 2)
        g.add(f'<rect x="448" y="944" width="300" height="44" rx="8" fill="{ORANGE}" fill-opacity="0.3" stroke="{ORANGE}"/>')
        g.text(598, 972, "12-B frame + <x:xmpmeta>", 15, ORANGE, MONO, "bold", "middle")
    g.text(90, 1052, "md5 = md5(inflated bytes) · referenced as crs:IngestInfo", 15, DIM)
    g.text(90, 1080, "a re-export rewrote it (empty Request/ResponseInfo): new md5, new slot", 15, DIM)

    g.card(820, 880, 720, 240, CYAN, "read it in five steps")
    for i, s in enumerate(['check "ACR\\0", read N at 0x0C', "read N × 32-byte entries at 0x14",
                           "record = data[offset : offset + size]", "starts 02 00 00 00 → TIFF, else inflate",
                           "match each md5 to the XMP"]):
        g.text(850, 950 + i * 32, f"{i + 1}", 16, CYAN, MONO, "bold")
        g.text(876, 950 + i * 32, s, 16, TXT, MONO)
    g.signature()
    g.render(os.path.join(out, "blog-acr-anatomy"))


def place(F, r, canvas_wh):
    """Raster r placed at its XMP Origin on a FullMaskSize canvas (sensor orientation), as L image."""
    cw, ch = canvas_wh
    c = np.zeros((ch, cw), np.uint8)
    ox, oy = map(int, r["ref"].get("Origin", "0,0").split(","))
    a = u8(r["img"])
    c[oy:oy + a.shape[0], ox:ox + a.shape[1]] = a[:ch - oy, :cw - ox]
    return Image.fromarray(c)


def fig_acr_decomposed(F, out):
    o = F.a["orient"]
    fms = next((r["ref"]["FullMaskSize"] for r in F.records if "FullMaskSize" in r["ref"]), "2880,1920")
    cw, ch = map(int, fms.split(","))
    photo = F.photo("Original")
    photo_s = rot(photo, {8: 6, 6: 8}.get(o, o)).resize((cw, ch), Image.LANCZOS)   # back to sensor orientation
    masks = [r for r in F.records if r["ref"].get("_ref") == "MaskDigest" and r["ref"].get("What") == "Mask/Image"
             and "RemoveAreas" not in r["ref"] and F.rec_label(r) != "AI object selection"]
    sel = [r for r in F.records if r["ref"].get("_ref") == "MaskDigest" and r not in masks]
    cands = [r for r in F.records if r["ref"].get("_ref") in ("pm_patch_variation", "pm_patch")]
    chosen = next((r for r in F.records if r["ref"].get("_ref") == "pm_patch"), None)
    fillm = next((r for r in F.records if r["ref"].get("_ref") == "pm_patch_mask"), None)
    rcpt = next((r for r in F.records if r["kind"] == "zlib"), None)
    pal = [BLUE, GREEN, ORANGE, PURPLE, YELLOW, CYAN]
    colmap = {}
    g = Fig(1600, 1300)
    g.header(f"{F.name}.acr, taken apart",
             f"{len(F.records)} records decoded, named from the XMP by MD5, then placed back on the photo",
             kicker="ACR", color=ORANGE)

    # ---- AI masks
    g.card(60, 200, 1000, 480, GREEN, f"AI masks · {len(masks)} rasters", tag="1 channel, 8 bit")
    TW, TH = 176, 264
    for i, r in enumerate(masks):
        col = pal[i % len(pal)]
        colmap[r["md5"]] = col
        x, y = 92 + i * 192, 264
        tile = tint(rot(place(F, r, (cw, ch)), o).resize((TW, TH), Image.BILINEAR), col,
                    rot(photo_s, o).resize((TW, TH)), 0.28)
        g.image(x, y, TW, TH, tile, "JPEG")
        a = np.asarray(r["img"])
        ox, oy = map(int, r["ref"].get("Origin", "0,0").split(","))
        # the raster's own box, drawn on the tile (display orientation)
        bx, by, bw, bh = ox, oy, a.shape[1], a.shape[0]
        if o == 8:   # rotate 90 CCW: (x, y) -> (y, W - x)
            bx, by, bw, bh = oy, cw - (ox + bw), bh, bw
        sx, sy = TW / (ch if o in (6, 8) else cw), TH / (cw if o in (6, 8) else ch)
        g.add(f'<rect x="{x + bx * sx:.1f}" y="{y + by * sy:.1f}" width="{bw * sx:.1f}" height="{bh * sy:.1f}" '
              f'fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="5 4"/>')
        g.add(f'<rect x="{x}" y="{y}" width="{TW}" height="{TH}" rx="4" fill="none" stroke="{col}" stroke-opacity="0.6"/>')
        g.text(x, y + TH + 32, F.rec_label(r), 18, col, SANS, "bold")
        g.text(x, y + TH + 56, f"{a.shape[1]}×{a.shape[0]}", 14, TXT, MONO)
        g.text(x, y + TH + 76, f"@ {r['ref'].get('Origin')}", 14, DIM, MONO)
        g.text(x, y + TH + 96, f"record {r['idx']} · {kb(r['size'])}", 14, DIM, MONO)
    g.text(92, 654, "dashed box = the stored raster: each one is cropped to its mask; only Background spans the frame",
           15, DIM)

    # ---- Generative Remove
    g.card(60, 710, 1000, 520, PINK, "Generative Remove · 5 records", tag="Firefly, kept locally")
    def strip(r, x, y, w, glow=False, col=PINK):
        im = Image.fromarray(u8(r["img"])).convert("RGB")
        hh = w * im.height / im.width
        g.image(x, y, w, hh, im.resize((int(w * 2), int(hh * 2)), Image.LANCZOS), "JPEG")
        g.add(f'<rect x="{x}" y="{y}" width="{w}" height="{hh:.1f}" rx="4" fill="none" stroke="{col}" '
              f'stroke-width="{3 if glow else 1.5}"{" filter=" + chr(34) + "url(#glow)" + chr(34) if glow else ""}/>')
        return hh
    y0 = 780
    g.text(92, y0, "① what to erase", 16, TXT, SANS, "bold")
    if sel:
        hh = strip(sel[0], 92, y0 + 16, 250)
        g.text(92, y0 + 36 + hh, f"AI selection · record {sel[0]['idx']}", 14, DIM, MONO)
    if fillm:
        hh2 = strip(fillm, 92, y0 + 150, 250)
        g.text(92, y0 + 170 + hh2, f"fill mask · record {fillm['idx']}", 14, DIM, MONO)
    g.arrow(f"M 360 {y0 + 140} L 420 {y0 + 140}", PINK, 2.5)
    g.text(440, y0, "② three generated candidates", 16, TXT, SANS, "bold")
    for i, r in enumerate(sorted(cands, key=lambda r: r is chosen)):
        yy = y0 + 16 + i * 108
        hh = strip(r, 440, yy, 330, r is chosen, ORANGE if r is chosen else PINK)
        g.text(790, yy + hh / 2 + 6, ("chosen · " if r is chosen else "") + f"record {r['idx']}", 15,
               ORANGE if r is chosen else DIM, MONO, "bold" if r is chosen else "normal")
        if r is chosen:
            g.text(790, yy + hh / 2 + 30, "pasted at pm_target", 14, DIM, MONO)
    if rcpt:
        g.chip(92, 1200, f"③ receipt · record {rcpt['idx']} · zlib XMP · {len(rcpt['inflated'])} B", ORANGE, 14)
    g.text(560, 1206, "patches are stored as the sensor sees them: sideways", 14, DIM)

    # ---- placed on the photo
    g.card(1100, 200, 440, 1030, CYAN, "placed on the photo")
    disp = rot(photo_s, o)
    PW, PH = 380, 570
    base = disp.resize((PW * 2, PH * 2), Image.LANCZOS)
    rgba_ = base.convert("RGBA")
    for r in masks + sel:
        col = colmap.get(r["md5"], PINK)
        m = rot(place(F, r, (cw, ch)), o).resize((PW * 2, PH * 2), Image.BILINEAR)
        b = m.point(lambda v: 255 if v > 127 else 0)
        edge = np.asarray(b.filter(ImageFilter.MaxFilter(5)), bool) & ~np.asarray(b, bool)
        e = np.zeros((PH * 2, PW * 2, 4), np.uint8)
        e[edge] = tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
        rgba_ = Image.alpha_composite(rgba_, Image.fromarray(e, "RGBA"))
    g.image(1130, 264, PW, PH, rgba_.convert("RGB"), "JPEG")
    sp = dict(re.findall(r'crs:(pm_\w+)="([^"]*)"', F.xmp))
    if "pm_target_left" in sp:              # the Generative Remove target, sensor -> display coordinates
        fw, fh = float(sp["pm_full_image_right"]), float(sp["pm_full_image_bottom"])
        l, t = float(sp["pm_target_left"]) / fw, float(sp["pm_target_top"]) / fh
        rr, b = float(sp["pm_target_right"]) / fw, float(sp["pm_target_bottom"]) / fh
        if o == 8:
            l, t, rr, b = t, 1 - rr, b, 1 - l
        g.add(f'<rect x="{1130 + l * PW:.1f}" y="{264 + t * PH:.1f}" width="{(rr - l) * PW:.1f}" '
              f'height="{(b - t) * PH:.1f}" fill="none" stroke="{ORANGE}" stroke-width="2" stroke-dasharray="5 3"/>')
    g.add(f'<rect x="1130" y="264" width="{PW}" height="{PH}" rx="4" fill="none" stroke="{CYAN}" stroke-opacity="0.6"/>')
    yy = 880
    for r in masks:
        g.add(f'<circle cx="1140" cy="{yy - 5}" r="6" fill="{colmap[r["md5"]]}"/>')
        g.text(1156, yy, F.rec_label(r), 16, TXT)
        yy += 30
    g.add(f'<circle cx="1140" cy="{yy - 5}" r="6" fill="{PINK}"/>')
    g.text(1156, yy, "Remove selection", 16, TXT)
    yy += 30
    g.add(f'<rect x="1134" y="{yy - 11}" width="12" height="12" fill="none" stroke="{ORANGE}" stroke-width="2"/>')
    g.text(1156, yy, "Remove target (pm_target)", 16, TXT)
    for i, s in enumerate(["outlines drawn from the stored", "rasters at their XMP Origin on", f"the {cw}×{ch} canvas,",
                           "then rotated for display"]):
        g.text(1130, yy + 50 + i * 24, s, 15, DIM)
    g.signature()
    g.render(os.path.join(out, "blog-acr-decomposed"))


def fig_binding(F, out):
    o = F.a["orient"]
    r = next(r for r in F.records if r["ref"].get("MaskName", "").startswith("Sky"))
    a = r["ref"]
    cw, ch = map(int, a["FullMaskSize"].split(","))
    ox, oy = map(int, a["Origin"].split(","))
    img = np.asarray(r["img"])
    g = Fig(1600, 900)
    g.header("How a raster finds its mask: by MD5",
             f"{a['MaskName']}, followed from the XMP into the .acr and back onto the canvas", kicker="ACR", color=ORANGE)
    g.card(60, 200, 430, 330, PURPLE, "XMP · the decision")
    lines = [[('<rdf:li crs:What=', PURPLE), ('"Mask/Image"', PINK)], [('crs:MaskName=', CYAN), (f'"{a["MaskName"]}"', ORANGE)],
             [('crs:MaskDigest=', CYAN)], [(f'"{r["md5"][:16]}…"', PINK, "b")],
             [('crs:FullMaskSize=', CYAN), (f'"{a["FullMaskSize"]}"', ORANGE)], [('crs:Origin=', CYAN), (f'"{a["Origin"]}"', ORANGE)]]
    for i, ln in enumerate(lines):
        g.rich(88, 284 + i * 36, ln, 16)
    g.card(590, 200, 420, 150, ORANGE, f"table entry {r['idx']}")
    g.text(618, 284, f"md5  {r['md5'][:16]}…", 16, PINK, MONO, "bold")
    g.text(618, 312, f"size {r['size']:,} · offset {hx(r['off'])}", 15, DIM, MONO)
    g.card(590, 380, 420, 150, GREEN, f"record {r['idx']} @ {hx(r['off'])}")
    g.text(618, 464, f"02 00 00 00 01 … + TIFF {img.shape[1]}×{img.shape[0]}", 15, TXT, MONO)
    g.text(618, 492, "md5(record) = the entry's md5", 15, DIM, MONO)
    g.arrow("M 490 392 C 540 392, 540 275, 586 275", PINK, 2.5)
    g.chip(540, 470, "same 32 hex", PINK, 13, "middle")
    g.arrow("M 800 352 L 800 376", ORANGE, 2.5)

    # canvas
    g.card(1050, 200, 490, 620, CYAN, "placed by Origin")
    S = 440 / cw
    x0, y0 = 1075, 262
    photo_s = rot(F.photo("Original"), {8: 6, 6: 8}.get(o, o)).resize((cw, ch))
    g.image(x0, y0, cw * S, ch * S, tint(place(F, r, (cw, ch)), BLUE, photo_s, 0.35).resize((int(cw * S * 2), int(ch * S * 2))), "JPEG")
    g.add(f'<rect x="{x0}" y="{y0}" width="{cw * S:.1f}" height="{ch * S:.1f}" fill="none" stroke="{CYAN}" stroke-dasharray="6 4"/>')
    g.add(f'<rect x="{x0 + ox * S:.1f}" y="{y0 + oy * S:.1f}" width="{img.shape[1] * S:.1f}" height="{img.shape[0] * S:.1f}" '
          f'fill="none" stroke="{GREEN}" stroke-width="2.5" filter="url(#glow)"/>')
    g.text(x0, y0 + ch * S + 30, f"canvas {cw}×{ch} · sensor orientation", 14, CYAN, MONO)
    g.text(x0, y0 + ch * S + 52, f"raster {img.shape[1]}×{img.shape[0]} at ({ox}, {oy})", 14, GREEN, MONO)
    # rotated thumb
    th = 150
    tw = th * ch / cw
    disp = rot(tint(place(F, r, (cw, ch)), BLUE, photo_s, 0.35), o)
    g.image(x0, y0 + ch * S + 80, tw, th, disp.resize((int(tw * 2), th * 2)), "JPEG")
    g.add(f'<rect x="{x0}" y="{y0 + ch * S + 80:.1f}" width="{tw:.1f}" height="{th}" fill="none" stroke="{CYAN}" stroke-opacity="0.6"/>')
    g.text(x0 + tw + 20, y0 + ch * S + 140, f"rotate last (Orientation {o})", 15, TXT)
    g.text(x0 + tw + 20, y0 + ch * S + 164, "composite first, then rotate", 14, DIM)
    g.arrow("M 1010 455 C 1040 455, 1040 400, 1072 400", GREEN, 2.5)

    g.card(60, 570, 950, 250, GREEN, "measured, not guessed")
    stats = [("311 / 311", "ACR records ↔ XMP refs"), ("77 / 77", "tables sorted by MD5"),
             ("4,504", "cache files named by own MD5"), ("106", "ACR records also in the cache")]
    for i, (b, l) in enumerate(stats):
        x = 92 + i * 230
        g.text(x, 680, b, 34, GREEN, SANS, "bold")
        g.text(x, 712, l, 14, DIM)
    g.text(92, 780, "no order, no index: a reader looks the hash up", 15, TXT)
    g.signature()
    g.render(os.path.join(out, "blog-mask-binding"))


def fig_lifecycle(F, out):
    g = Fig(1600, 820)
    g.header("From cache to export and back", "what lives where, and what the .acr changes when the edit comes back",
             kicker="ROUND TRIP", color=GREEN)
    g.card(60, 200, 430, 470, DIM, "Lightroom's local cache")
    for i, (n, s1, s2, col) in enumerate((("settings\\<sha256>", "bare develop XMPs", "named by the hash of the content", ORANGE),
                                         ("auxiliary\\<md5>", "AI-mask rasters, Remove patches", "named by the XMP's MaskDigest", GREEN))):
        y = 270 + i * 190
        g.card(90, y, 370, 160, col, None, rx=12)
        g.text(112, y + 42, n, 18, col, MONO, "bold")
        g.text(112, y + 76, s1, 16, TXT)
        g.text(112, y + 102, s2, 14, DIM)
    g.card(560, 350, 220, 120, CYAN, None, glow=True)
    g.text(670, 400, "export", 22, CYAN, SANS, "bold", "middle")
    g.text(670, 430, "original + settings", 15, DIM, SANS, "normal", "middle")
    g.arrow("M 460 350 C 510 350, 510 400, 556 400", ORANGE)
    g.arrow("M 460 540 C 510 540, 510 430, 556 430", GREEN)
    g.card(850, 220, 330, 430, GREEN, "the trio, same folder")
    for i, (n, s, col) in enumerate(((f"{F.name}.ARW", "untouched, not one byte added", TXT),
                                     (f"{F.name}.xmp", "the bare blob, renamed", ORANGE),
                                     (f"{F.name}.acr", "only if there is an AI mask", GREEN))):
        y = 290 + i * 116
        g.add(f'<rect x="880" y="{y}" width="270" height="88" rx="12" fill="{col}" fill-opacity="0.08" stroke="{col}" stroke-opacity="0.6"/>')
        g.text(902, y + 38, n, 18, col, MONO, "bold")
        g.text(902, y + 66, s, 14, DIM)
    g.arrow("M 780 410 L 846 410", CYAN)
    g.card(1250, 220, 290, 190, GREEN, "with the .acr", glow=True)
    g.text(1276, 300, "masks restored exactly,", 16, TXT)
    g.text(1276, 326, "from the stored rasters", 16, DIM)
    g.card(1250, 450, 290, 200, DIM, "without it")
    g.text(1276, 530, "AI models re-run on", 16, TXT)
    g.text(1276, 556, "the XMP: close, not", 16, DIM)
    g.text(1276, 582, "always identical", 16, DIM)
    g.arrow("M 1180 380 C 1215 380, 1215 315, 1246 315", GREEN)
    g.arrow("M 1180 520 C 1215 520, 1215 550, 1246 550", DIM, dash=True)
    g.arrow("M 275 672 C 275 730, 1015 730, 1015 654", PURPLE, 2.2, dash=True)
    g.chip(645, 738, "offline: rebuild the .acr from auxiliary\\ (header + sorted table + records)", PURPLE, 14, "middle")
    g.signature()
    g.render(os.path.join(out, "blog-lifecycle"))


FIGS = {"tiff": fig_tiff, "arw": fig_arw, "xmp": fig_xmp, "xmp-rules": fig_xmp_rules, "acr-when": fig_acr_when,
        "acr-anatomy": fig_acr_anatomy, "acr-decomposed": fig_acr_decomposed, "binding": fig_binding,
        "lifecycle": fig_lifecycle}

def main():
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    stem = args[0]
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "docs", "assets", "blog")
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else list(FIGS)
    os.makedirs(out, exist_ok=True)
    F = Family(stem)
    for k in only:
        FIGS[k](F, out)

if __name__ == "__main__":
    main()
