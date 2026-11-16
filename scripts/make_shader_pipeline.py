r"""One edit drawn as a shader pipeline: RAW in -> XMP x ACR passes -> JPG out.

The middle is an exploded 3D stack: the decoded photo with the global XMP
settings, the Generative Remove pass, one plane per AI-mask group (tinted
by its real ACR raster) and one plane for the parametric masks, which have
no raster. Everything is read from the files; nothing is typed in by hand.

Needs: pip install tifffile imagecodecs numpy pillow  (and Chrome or Edge)
Run:   python scripts/make_shader_pipeline.py <dir>/<NAME>
       expects <NAME>.ARW (optional), <NAME>-Original.JPG, <NAME>.xmp,
       <NAME>.acr and <NAME>.jpg (the final export)
Writes docs/assets/shader-pipeline.svg + .png (or --out <stem>)
"""
import os, re, sys, io, base64, struct, subprocess, tempfile, shutil
import xml.etree.ElementTree as ET
import numpy as np, tifffile
from PIL import Image, ImageOps, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acr_reader import read_table, classify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
NS = {"rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
      "crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
      "tiff": "http://ns.adobe.com/tiff/1.0/"}
C, R = "{%s}" % NS["crs"], "{%s}" % NS["rdf"]
BG, TXT, DIM = "#0b0f15", "#e6edf3", "#8b949e"
BLUE, ORANGE, GREEN, PURPLE, PINK, CYAN = "#58a6ff", "#ffa657", "#7ee787", "#d2a8ff", "#f778ba", "#79c0ff"
MONO, SANS = "Consolas, 'Cascadia Mono', monospace", "'Segoe UI', sans-serif"
TEX_W, TEX_H = 600, 900          # plane texture size (display orientation, 2:3)

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def b64(img, fmt="PNG"):
    buf = io.BytesIO()
    img.save(buf, fmt, **({"quality": 88} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()

def fmt(v):
    f = float(v)
    s = f"{f:+.2f}" if abs(f) < 10 else f"{f:+.0f}"
    return s.replace("-", "−")

# ------------------------------------------------------------------ inputs
def load(stem):
    xmp_text = open(stem + ".xmp", "rb").read().decode("utf-8", "replace")
    desc = ET.fromstring(xmp_text).find(".//rdf:Description", NS)
    data = open(stem + ".acr", "rb").read()
    rasters = {}
    for md5, size, off in read_table(data)[3]:
        kind, body, _ = classify(data[off:off + size])
        if kind == "raster":
            rasters[md5] = tifffile.imread(io.BytesIO(body))
    return xmp_text, desc, rasters

def groups(desc):
    out = []
    mg = desc.find("crs:MaskGroupBasedCorrections", NS)
    for li in mg.find("rdf:Seq", NS).findall("rdf:li", NS):
        d = li.find("rdf:Description", NS)
        d = d if d is not None else li
        adj = {k[len(C):]: v for k, v in d.attrib.items()
               if k.startswith(C + "Local") and "Refine" not in k and "Hue" not in k
               and float(v) not in (0.0,) and not (k.endswith("Saturation") and float(v) in (100.0,))
               and k[len(C):] not in ("LocalCurveRefineSaturation",)}
        masks = []
        for m in d.find("crs:CorrectionMasks", NS).iter(R + "li"):
            md = m if m.get(C + "What") else m.find("rdf:Description", NS)
            if md is not None and md.get(C + "What"):
                masks.append({k[len(C):]: v for k, v in md.attrib.items() if k.startswith(C)})
        out.append((d.get(C + "CorrectionName"), adj, masks))
    return out

def spot(xmp_text):
    """Attributes of the Generative Remove / Remove spot, merged across its elements."""
    i = xmp_text.find("crs:SpotType")
    if i < 0:
        return {}
    j = xmp_text.find("</crs:RetouchAreas>", i)
    return dict(re.findall(r'crs:(\w+)="([^"]*)"', xmp_text[xmp_text.rfind("<rdf:li", 0, i):j]))

def remove_masks(xmp_text):
    i = xmp_text.find("<crs:RemoveAreas>")
    if i < 0:
        return []
    j = xmp_text.find("</crs:RemoveAreas>", i)
    return re.findall(r'crs:MaskDigest="([0-9A-F]{32})"', xmp_text[i:j], re.I)

# ------------------------------------------------------------------ textures
def rot(img, orient):
    return {3: img.rotate(180, expand=True), 6: img.rotate(-90, expand=True),
            8: img.rotate(90, expand=True)}.get(orient, img)

def mask_canvas(masks, rasters, size):
    """Union of AI-mask rasters placed at Origin on the FullMaskSize canvas (sensor)."""
    cw, ch = size
    acc = np.zeros((ch, cw), np.float32)
    for m in masks:
        dg = m.get("MaskDigest", "").upper()
        if dg in rasters and "Origin" in m:
            r = rasters[dg].astype(np.float32) / 255.0
            ox, oy = map(int, m["Origin"].split(","))
            sub = acc[oy:oy + r.shape[0], ox:ox + r.shape[1]]
            np.maximum(sub, r[:sub.shape[0], :sub.shape[1]], out=sub)
    return acc

def glass(photo_disp, mask_disp, color, ghost=0.22):
    """RGBA plane: faint photo, mask tinted in color."""
    p = np.asarray(photo_disp.resize((TEX_W, TEX_H)), np.float32) / 255.0
    m = np.asarray(mask_disp.resize((TEX_W, TEX_H), Image.BILINEAR), np.float32)[..., None] / 255.0
    col = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255.0
    rgb = p * ghost * (1 - m) + (col * 0.85 + p * 0.25) * m
    alpha = 0.42 + 0.5 * m
    return Image.fromarray((np.dstack([rgb, alpha]).clip(0, 1) * 255).astype(np.uint8), "RGBA")

def stretch(a):
    a = np.asarray(a, np.float64)
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    return ((a - lo) / max(1e-6, hi - lo) * 255).clip(0, 255).astype(np.uint8)

# ------------------------------------------------------------------ svg
class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.s = w, h, []
    def add(self, x): self.s.append(x)
    def text(self, x, y, s, size=15, fill=TXT, font=SANS, weight="normal", anchor="start", op=1):
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-family="{font}" '
                 f'font-weight="{weight}" text-anchor="{anchor}" opacity="{op}">{esc(s)}</text>')
    def render(self, stem):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" font-family="{SANS}">')
        svg = stem + ".svg"
        open(svg, "w", encoding="utf-8").write(head + "\n".join(self.s) + "</svg>")
        with tempfile.TemporaryDirectory() as td:
            shot = os.path.join(td, "s.png")
            subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", f"--screenshot={shot}",
                            f"--window-size={self.w},{self.h}", "--force-device-scale-factor=1",
                            "file:///" + svg.replace("\\", "/")], check=True, capture_output=True, timeout=180)
            shutil.copy(shot, stem + ".png")
        print("written:", stem + ".png")

def main():
    stem = sys.argv[1]
    out = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
           else os.path.join(ROOT, "docs", "assets", "shader-pipeline"))
    name = os.path.basename(stem)
    xmp_text, desc, rasters = load(stem)
    orient = int(desc.get("{%s}Orientation" % NS["tiff"]) or 1)
    g = groups(desc)
    sp = spot(xmp_text)
    fms = next((m["FullMaskSize"] for _, _, ms in g for m in ms if "FullMaskSize" in m), "2880,1920")
    cw, ch = map(int, fms.split(","))

    original = ImageOps.exif_transpose(Image.open(stem + "-Original.JPG")).convert("RGB")
    final = ImageOps.exif_transpose(Image.open(stem + ".jpg")).convert("RGB")
    photo_disp = original.resize((TEX_W, TEX_H), Image.LANCZOS)

    # ---- planes, bottom to top
    planes = []
    gl = lambda k: desc.get(C + k)
    planes.append(dict(kind="photo", tex=photo_disp, color=CYAN, title="pass 0 · decode + global settings",
                       src="XMP · crs:* globals",
                       lines=[f"{gl('CameraProfile')} · WB {gl('Temperature')}K / {gl('Tint')}",
                              f"Exposure2012 {fmt(gl('Exposure2012'))} · Contrast2012 {fmt(gl('Contrast2012'))}",
                              f"Highlights {fmt(gl('Highlights2012'))} · Shadows {fmt(gl('Shadows2012'))}"
                              f" · Vibrance {fmt(gl('Vibrance'))} · Saturation {fmt(gl('Saturation'))}"]))
    if sp:
        sel = mask_canvas([{"MaskDigest": d, "Origin": re.search(
            r'crs:MaskDigest="%s"[^>]*?crs:Origin="([^"]+)"|crs:Origin="([^"]+)"[^>]*?crs:MaskDigest="%s"' % (d, d),
            xmp_text, re.I).group(1) or ""} for d in remove_masks(xmp_text)], rasters, (cw, ch))
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        patch = rasters.get(sp.get("pm_patch", "").upper())
        if patch is not None:
            fw = float(sp["pm_full_image_right"]) - float(sp["pm_full_image_left"])
            fh = float(sp["pm_full_image_bottom"]) - float(sp["pm_full_image_top"])
            box = [int(float(sp["pm_target_left"]) * cw / fw), int(float(sp["pm_target_top"]) * ch / fh),
                   int(float(sp["pm_target_right"]) * cw / fw), int(float(sp["pm_target_bottom"]) * ch / fh)]
            pim = Image.fromarray(stretch(patch)).resize((box[2] - box[0], box[3] - box[1]), Image.LANCZOS)
            fill = rasters.get(sp.get("pm_patch_mask", "").upper())
            pm = Image.fromarray(fill).resize(pim.size) if fill is not None else None
            canvas.paste(pim.convert("RGBA"), box[:2], pm)
        sel_img = Image.fromarray((sel * 255).astype(np.uint8))
        edge = np.asarray(sel_img.filter(ImageFilter.MaxFilter(15)), bool) & ~np.asarray(sel_img, bool)
        e = np.zeros((ch, cw, 4), np.uint8); e[edge] = (247, 120, 186, 255)
        canvas = Image.alpha_composite(canvas, Image.fromarray(e, "RGBA"))
        tex = Image.new("RGBA", (TEX_W, TEX_H), (12, 16, 24, 110))
        tex = Image.alpha_composite(tex, rot(canvas, orient).resize((TEX_W, TEX_H), Image.LANCZOS))
        gen = sp.get("fill_method") == "firefly"
        planes.append(dict(kind="tex", tex=tex, color=PINK,
                           title="pass 1 · " + ("Generative Remove (Firefly)" if gen else "Remove"),
                           src="ACR · selection → fill mask → patch",
                           lines=["AI object selection + brush = what to erase",
                                  "3 generated variations stored as RGB patches",
                                  "the chosen one pasted at pm_target (shown)"]))
    palette = [BLUE, ORANGE, GREEN, PURPLE]
    ai_groups, proc = [], []
    for gname, adj, masks in g:
        ai = [m for m in masks if m.get("What") == "Mask/Image" and m.get("MaskDigest", "").upper() in rasters]
        if ai:
            key = tuple(sorted(m["MaskDigest"] for m in ai))
            if ai_groups and ai_groups[-1]["key"] == key:
                ai_groups[-1]["names"].append(gname); ai_groups[-1]["adj"].append(adj)
            else:
                ai_groups.append(dict(key=key, names=[gname], adj=[adj], masks=ai, all=masks))
        else:
            proc.append((gname, adj, masks))
    short = {"LocalExposure2012": "Exposure", "LocalContrast2012": "Contrast", "LocalHighlights2012": "Highlights",
             "LocalShadows2012": "Shadows", "LocalGlow": "Glow", "LocalClarity2012": "Clarity",
             "LocalSaturation": "Saturation", "LocalTexture": "Texture", "LocalDehaze": "Dehaze"}
    adjtxt = lambda a: " · ".join(f"{short.get(k, k)} {fmt(v)}" for k, v in a.items())
    for k, ag in enumerate(ai_groups):
        col = palette[k % len(palette)]
        un = mask_canvas(ag["masks"], rasters, (cw, ch))
        mdisp = rot(Image.fromarray((un * 255).astype(np.uint8)), orient)
        names = " ∪ ".join(re.sub(r"\s*\d+$", "", m.get("MaskName", "AI")) for m in ag["masks"])
        extra = [m["What"].split("/")[1] for m in ag["all"] if m.get("What") != "Mask/Image"]
        lines = [f"{n}: {adjtxt(a)}" + (" (with " + ", ".join(extra) + ")" if extra and j else "")
                 for j, (n, a) in enumerate(zip(ag["names"], ag["adj"]))]
        planes.append(dict(kind="tex", tex=glass(photo_disp, mdisp, col), color=col,
                           title=f"pass {len(planes)} · {names}",
                           src=f"ACR · {len(ag['masks'])} raster{'s' if len(ag['masks']) > 1 else ''}"
                               + " (MaskDigest)", lines=lines))
    if proc:
        kinds = {"Mask/Gradient": "linear", "Mask/CircularGradient": "radial", "Mask/RangeMask": "range",
                 "Mask/Paint": "brush"}
        lines = [f"{n}: {', '.join(kinds.get(m['What'], m['What']) for m in ms)} → {adjtxt(a)}" for n, a, ms in proc]
        planes.append(dict(kind="proc", color=PURPLE, title=f"pass {len(planes)} · parametric masks",
                           src="XMP only · recomputed every render", lines=lines))

    # ---- layout
    W, H = 2300, 1500
    s = Svg(W, H)
    s.add(f'<defs><radialGradient id="bg" cx="50%" cy="40%" r="75%"><stop offset="0" stop-color="#162131"/>'
          f'<stop offset="1" stop-color="{BG}"/></radialGradient>'
          '<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6" result="b"/>'
          '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
          '<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="18" '
          'stdDeviation="16" flood-color="#000" flood-opacity="0.65"/></filter>'
          f'<linearGradient id="flow" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/>'
          f'<stop offset="0.5" stop-color="{PINK}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>'
          f'<linearGradient id="lin" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PURPLE}" stop-opacity="0.75"/>'
          f'<stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient>'
          f'<radialGradient id="rad"><stop offset="0" stop-color="{PURPLE}" stop-opacity="0.7"/>'
          f'<stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>'
          '<marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto">'
          f'<path d="M0,0 L10,5 L0,10 z" fill="{TXT}"/></marker></defs>')
    s.add(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')
    for gx in range(0, W, 46):
        s.add(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{H}" stroke="#ffffff" stroke-opacity="0.025"/>')
    s.text(60, 70, f"{name}: one edit, drawn as a shader pipeline", 38, TXT, SANS, "bold")
    s.text(60, 108, "the ARW is the input texture, the XMP is the program, the ACR holds the textures an AI model "
                    "baked, and the JPG is the framebuffer", 19, DIM)

    # stage header bar
    stages = [(60, 470, "① INPUT", "ARW · sensor data", CYAN), (560, 1640, "② PASSES", "XMP program × ACR textures", PINK),
              (1730, 2240, "③ OUTPUT", "rendered JPG", ORANGE)]
    for x0, x1, a, b, col in stages:
        s.add(f'<rect x="{x0}" y="140" width="{x1 - x0}" height="54" rx="27" fill="{col}" fill-opacity="0.10" '
              f'stroke="{col}" stroke-opacity="0.7"/>')
        s.text(x0 + 26, 175, a, 19, col, MONO, "bold")
        s.text(x0 + 140, 175, b, 17, TXT)

    def card(x, y, img, col, cap):
        w, h = 400, 600
        s.add(f'<g filter="url(#shadow)"><rect x="{x - 8}" y="{y - 8}" width="{w + 16}" height="{h + 16}" rx="14" '
              f'fill="#111822" stroke="{col}" stroke-width="2.5"/></g>')
        s.add(f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" '
              f'href="{b64(img.resize((800, 1200), Image.LANCZOS), "JPEG")}"/>')
        for i, (t, c, f, z) in enumerate(cap):
            s.text(x, y + h + 44 + i * 26, t, z, c, f, "bold" if i == 0 else "normal")
    card(65, 250, original, CYAN, [
        (f"{name}.ARW", CYAN, MONO, 20),
        ("7168×5120 sensor strip, 41.6 MB, in a SubIFD", TXT, SANS, 16),
        (f"shown: {name}-Original.JPG,", DIM, SANS, 15),
        ("the camera's own unedited rendering", DIM, SANS, 15)])
    crop = (float(gl("CropRight") or 1) - float(gl("CropLeft") or 0))
    card(1785, 250, final, ORANGE, [
        (f"{name}.jpg", ORANGE, MONO, 20),
        (f"{final.width}×{final.height} · Lightroom export", TXT, SANS, 16),
        (f"crop keeps {crop * 100:.1f}% of the width,", DIM, SANS, 15),
        (f"straightened {float(gl('CropAngle') or 0):.2f}°", DIM, SANS, 15)])

    # exploded stack: plane = u (width 300) x v (height 450) through an oblique matrix
    U, V = 300.0, 450.0
    A, B, Cc, D = 0.92, -0.30, 0.60, 0.34
    n = len(planes)
    gap = 168
    X0, Ybot = 610, 250 + (n - 1) * gap + 130
    corners = lambda e, f: [(e, f), (e + A * U, f + B * U), (e + A * U + Cc * V, f + B * U + D * V), (e + Cc * V, f + D * V)]
    for i, p in enumerate(planes):
        e, f = X0, Ybot - i * gap
        pts = corners(e, f)
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        if i:   # light rails from the plane below
            for (x1, y1), (x2, y2) in zip(corners(X0, Ybot - (i - 1) * gap), pts):
                s.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{p["color"]}" '
                      f'stroke-opacity="0.22" stroke-dasharray="3 5"/>')
        s.add(f'<polygon points="{poly}" fill="#000" fill-opacity="0.35" filter="url(#shadow)"/>')
        tf = f'matrix({A} {B} {Cc} {D} {e:.1f} {f:.1f})'
        if p["kind"] == "photo":
            s.add(f'<image transform="{tf}" width="{U}" height="{V}" href="{b64(p["tex"], "JPEG")}"/>')
        elif p["kind"] == "tex":
            s.add(f'<image transform="{tf}" width="{U}" height="{V}" href="{b64(p["tex"])}"/>')
        else:
            s.add(f'<g transform="{tf}"><rect width="{U}" height="{V}" fill="#120e1c" fill-opacity="0.55"/>'
                  f'<rect width="{U}" height="{V * 0.45}" fill="url(#lin)"/>'
                  f'<rect y="{V * 0.62}" width="{U}" height="{V * 0.38}" fill="url(#lin)" transform="rotate(180 {U / 2} {V * 0.81})"/>'
                  f'<ellipse cx="{U * 0.55}" cy="{V * 0.48}" rx="{U * 0.42}" ry="{V * 0.22}" fill="url(#rad)"/></g>')
        dash = ' stroke-dasharray="10 7"' if p["kind"] == "proc" else ""
        s.add(f'<polygon points="{poly}" fill="none" stroke="{p["color"]}" stroke-width="2.5"{dash} filter="url(#glow)"/>')
        # label
        rx, ry = pts[2]
        ly = f + B * U + D * V / 2 + 8
        lx = 1225
        s.add(f'<line x1="{pts[1][0] + Cc * V / 2:.1f}" y1="{pts[1][1] + D * V / 2:.1f}" x2="{lx - 14}" y2="{ly - 6:.1f}" '
              f'stroke="{p["color"]}" stroke-opacity="0.7" stroke-width="1.5"/>')
        s.add(f'<circle cx="{lx - 14}" cy="{ly - 6:.1f}" r="4" fill="{p["color"]}"/>')
        s.text(lx, ly - 28, p["title"], 19, p["color"], SANS, "bold")
        s.text(lx, ly - 4, p["src"], 14, DIM, MONO)
        for j, t in enumerate(p["lines"]):
            s.text(lx, ly + 20 + j * 21, t, 14.5, TXT, MONO)

    # flow arrows
    s.add(f'<path d="M 480 560 C 540 560, 540 {Ybot + 60}, {X0 - 6} {Ybot + 70}" fill="none" stroke="{CYAN}" '
          f'stroke-width="3" marker-end="url(#ar)" filter="url(#glow)"/>')
    top = Ybot - (n - 1) * gap
    s.add(f'<path d="M {X0 + A * U:.0f} {top + B * U - 10:.0f} C 1150 {top - 200:.0f}, 1660 200, 1772 300" fill="none" '
          f'stroke="{ORANGE}" stroke-width="3" marker-end="url(#ar)" filter="url(#glow)"/>')
    s.text(1500, 300, "composite → crop → straighten → encode", 15, ORANGE, MONO, "bold", "middle")

    # legend
    ly = H - 70
    s.add(f'<rect x="60" y="{ly - 34}" width="{W - 120}" height="58" rx="12" fill="#ffffff" fill-opacity="0.03" stroke="#30363d"/>')
    items = [(CYAN, "XMP parameters: plain numbers, re-run on every render"),
             (ORANGE, "ACR textures: AI output, stored as rasters so the result does not drift"),
             (PURPLE, "parametric masks: XMP only, no raster"),
             (DIM, "stacked in XMP order; Adobe does not document the engine's internal pass order")]
    x = 85
    for col, t in items:
        s.add(f'<circle cx="{x}" cy="{ly - 5}" r="7" fill="{col}"/>')
        s.text(x + 16, ly, t, 14.5, TXT)
        x += 16 + len(t) * 7.3 + 46
    s.render(out)

if __name__ == "__main__":
    main()
