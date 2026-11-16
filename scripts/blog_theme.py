r"""Shared look for every figure in the "three files and a photo" post.

One design language, taken from the shader-pipeline figure: a navy radial
background with a faint grid, glowing neon strokes, glass cards, pill
headers, a legend bar and a small signature in the corner. Every figure
script draws through this module, so a colour or font changes in one place.

Rendering: headless Chrome (or Edge) screenshots the SVG, at 2x by default.
"""
import os, io, base64, subprocess, tempfile, shutil

BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

# ------------------------------------------------------------------ palette
BG, BG_HI, CARD = "#0b0f15", "#162131", "#111822"
TXT, DIM, FAINT, RULE = "#e6edf3", "#8b949e", "#5b6573", "#30363d"
CYAN, BLUE, ORANGE, GREEN = "#79c0ff", "#58a6ff", "#ffa657", "#7ee787"
PURPLE, PINK, RED, YELLOW = "#d2a8ff", "#f778ba", "#ff7b72", "#e3b341"
COLORS = (TXT, DIM, CYAN, BLUE, ORANGE, GREEN, PURPLE, PINK, RED, YELLOW)
MONO = "Consolas, 'Cascadia Mono', monospace"
SANS = "'Segoe UI', 'Microsoft JhengHei', sans-serif"
SIGNATURE = "DSC03049 · ARW · XMP · ACR · byronwai.github.io"

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def mid(c): return "m" + c.lstrip("#")          # marker id for an arrow colour

def b64(img, fmt="PNG", quality=88):
    buf = io.BytesIO()
    img.save(buf, fmt, **({"quality": quality} if fmt == "JPEG" else {}))
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(buf.getvalue()).decode()

def rgba(c, a):
    return f"rgba({int(c[1:3], 16)},{int(c[3:5], 16)},{int(c[5:7], 16)},{a})"


class Fig:
    """An SVG canvas with the house background already painted."""

    def __init__(self, w, h, grid=True):
        self.w, self.h, self.s = w, h, []
        markers = "".join(
            f'<marker id="{mid(c)}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="8" markerHeight="8" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>' for c in COLORS)
        self.add('<defs>'
                 f'<radialGradient id="bg" cx="50%" cy="35%" r="80%"><stop offset="0" stop-color="{BG_HI}"/>'
                 f'<stop offset="1" stop-color="{BG}"/></radialGradient>'
                 f'<filter id="glow" filterUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}"><feGaussianBlur stdDeviation="5" '
                 'result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
                 '<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="14"/></filter>'
                 '<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="14" '
                 'stdDeviation="14" flood-color="#000" flood-opacity="0.6"/></filter>'
                 f'<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff" '
                 f'stop-opacity="0.06"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
                 f'<linearGradient id="flow" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}"/>'
                 f'<stop offset="0.5" stop-color="{PINK}"/><stop offset="1" stop-color="{ORANGE}"/></linearGradient>'
                 + markers + '</defs>')
        self.add(f'<rect width="{w}" height="{h}" fill="url(#bg)"/>')
        if grid:
            for gx in range(0, w, 46):
                self.add(f'<line x1="{gx}" y1="0" x2="{gx}" y2="{h}" stroke="#ffffff" stroke-opacity="0.025"/>')

    def add(self, x): self.s.append(x)

    # -------------------------------------------------------------- text
    def text(self, x, y, s, size=17, fill=TXT, font=SANS, weight="normal", anchor="start", op=1, ls=None):
        sp = f' letter-spacing="{ls}"' if ls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" font-family="{font}" '
                 f'font-weight="{weight}" text-anchor="{anchor}" opacity="{op}"{sp}>{esc(s)}</text>')

    def rich(self, x, y, parts, size=16, font=MONO, anchor="start", weight="normal"):
        """One line, several colours: parts = [(text, colour[, 'bold']), ...]."""
        spans = "".join(f'<tspan fill="{p[1]}"{" font-weight=\"bold\"" if len(p) > 2 else ""}>{esc(p[0])}</tspan>'
                        for p in parts)
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-family="{font}" font-weight="{weight}" '
                 f'text-anchor="{anchor}" xml:space="preserve">{spans}</text>')

    def header(self, title, sub, kicker=None, color=CYAN):
        y = 70
        if kicker:
            w = 22 + len(kicker) * 10.2
            self.add(f'<rect x="60" y="34" width="{w:.0f}" height="30" rx="15" fill="{color}" fill-opacity="0.12" '
                     f'stroke="{color}" stroke-opacity="0.7"/>')
            self.text(60 + w / 2, 55, kicker, 15, color, MONO, "bold", "middle", ls=1)
            y = 112
        self.text(60, y, title, 36, TXT, SANS, "bold")
        self.text(60, y + 38, sub, 19, DIM)
        return y + 38

    def signature(self, s=SIGNATURE):
        self.text(self.w - 60, self.h - 22, s, 13, FAINT, MONO, "normal", "end")

    # -------------------------------------------------------------- shapes
    def card(self, x, y, w, h, color, title=None, tag=None, dash=False, glow=False, fill=CARD, rx=16, sw=2):
        d = ' stroke-dasharray="9 6"' if dash else ""
        self.add(f'<g filter="url(#shadow)"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"/></g>')
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}" fill-opacity="0.05"/>')
        hh = min(h, 90)          # sheen as a path, so layout tools don't mistake it for a panel
        self.add(f'<path d="M {x + rx} {y} H {x + w - rx} A {rx} {rx} 0 0 1 {x + w} {y + rx} V {y + hh} H {x} '
                 f'V {y + rx} A {rx} {rx} 0 0 1 {x + rx} {y} Z" fill="url(#sheen)"/>')
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="none" stroke="{color}" '
                 f'stroke-opacity="0.8" stroke-width="{sw}"{d}{" filter=\"url(#glow)\"" if glow else ""}/>')
        if title:
            self.add(f'<circle cx="{x + 26}" cy="{y + 33}" r="5" fill="{color}" filter="url(#glow)"/>')
            self.text(x + 42, y + 40, title, 20, color, SANS, "bold")
        if tag:
            self.text(x + w - 22, y + 39, tag, 14, DIM, MONO, "normal", "end")

    def pill(self, x, y, w, label, text, color, h=50):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h / 2}" fill="{color}" fill-opacity="0.10" '
                 f'stroke="{color}" stroke-opacity="0.7"/>')
        self.text(x + 24, y + h / 2 + 6, label, 17, color, MONO, "bold")
        if text:
            self.text(x + 34 + len(label) * 9.6, y + h / 2 + 6, text, 16, TXT)

    def chip(self, x, y, s, color, size=14, anchor="start"):
        w = len(s) * size * 0.56 + 18
        x0 = x - w / 2 if anchor == "middle" else x
        self.add(f'<rect x="{x0:.1f}" y="{y - size - 4}" width="{w:.1f}" height="{size + 12}" rx="{(size + 12) / 2}" '
                 f'fill="{BG}" stroke="{color}" stroke-opacity="0.8"/>')
        self.text(x0 + w / 2, y + 1, s, size, color, MONO, "bold", "middle")
        return w

    def arrow(self, d, color=TXT, width=2.5, dash=False, glow=True, head=True):
        da = ' stroke-dasharray="8 6"' if dash else ""
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{da}'
                 f'{f" marker-end=\"url(#{mid(color)})\"" if head else ""}'
                 f'{" filter=\"url(#glow)\"" if glow else ""}/>')

    def stat(self, x, y, big, label, color, sub=None, size=64):
        self.text(x, y, big, size, color, SANS, "bold")
        self.text(x, y + 34, label, 17, TXT)
        if sub:
            self.text(x, y + 58, sub, 14.5, DIM)

    def image(self, x, y, w, h, img, fmt="JPEG", slice_=True, transform=None):
        pa = "xMidYMid slice" if slice_ else "xMidYMid meet"
        tf = f' transform="{transform}"' if transform else ""
        self.add(f'<image x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="{pa}"{tf} '
                 f'href="{b64(img, fmt)}"/>')

    def legend(self, items, y=None, x0=60, gap=44):
        y = y if y is not None else self.h - 74
        self.add(f'<rect x="{x0}" y="{y - 32}" width="{self.w - 2 * x0}" height="54" rx="12" fill="#ffffff" '
                 f'fill-opacity="0.03" stroke="{RULE}"/>')
        x = x0 + 26
        for col, t in items:
            self.add(f'<circle cx="{x}" cy="{y - 5}" r="7" fill="{col}"/>')
            self.text(x + 16, y, t, 15, TXT)
            x += 16 + len(t) * 7.6 + gap

    # -------------------------------------------------------------- output
    def render(self, stem, scale=2):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" font-family="{SANS}">')
        svg = stem + ".svg"
        os.makedirs(os.path.dirname(os.path.abspath(svg)), exist_ok=True)
        open(svg, "w", encoding="utf-8").write(head + "\n".join(self.s) + "</svg>")
        with tempfile.TemporaryDirectory() as td:
            shot = os.path.join(td, "s.png")
            subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", f"--screenshot={shot}",
                            f"--window-size={self.w},{self.h}", f"--force-device-scale-factor={scale}",
                            "--hide-scrollbars", "file:///" + os.path.abspath(svg).replace("\\", "/")],
                           check=True, capture_output=True, timeout=180)
            shutil.copy(shot, stem + ".png")
        print("written:", stem + ".png")
