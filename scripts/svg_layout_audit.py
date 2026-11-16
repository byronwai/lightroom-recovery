r"""Audit generated SVG diagrams for layout bugs, using Chrome's own text layout.

For each SVG it reports:
  canvas    text that runs outside the canvas
  overlap   two texts whose rendered boxes overlap
  overflow  text that starts inside a panel (<rect>/<polygon>) but runs past its edge
  crossing  an arrow or connector (<line>/<path>) that passes through a text
  dangling  an arrow whose head lands on nothing (no panel, image or plane near it)

Run:  python scripts/svg_layout_audit.py <file.svg> [...]
Exit status 1 if anything is reported.
"""
import os, sys, json, re, subprocess, tempfile, html

BROWSER = (r"C:\Program Files\Google\Chrome\Application\chrome.exe"
           if os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
           else r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

JS = r"""
(() => {
  const svg = document.querySelector('svg');
  const W = svg.viewBox.baseVal.width || svg.width.baseVal.value;
  const H = svg.viewBox.baseVal.height || svg.height.baseVal.value;
  const box = e => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; };
  const hidden = e => { for (let n = e; n && n !== svg; n = n.parentNode) {
      if (n.tagName === 'defs' || n.tagName === 'marker') return true; } return false; };
  const label = e => (e.textContent || '').trim().slice(0, 60);
  const texts = [...svg.querySelectorAll('text')].filter(e => !hidden(e) && label(e))
      .map(e => ({e, b: box(e), s: label(e)}));
  const panels = [...svg.querySelectorAll('rect, polygon')].filter(e => !hidden(e)).map(e => ({e, b: box(e)}))
      .filter(p => (p.b.r - p.b.l) < W - 2 || (p.b.b - p.b.t) < H - 2)          // not the background
      .filter(p => (p.b.r - p.b.l) > 30 && (p.b.b - p.b.t) > 20);                // not ticks or chips
  const targets = panels.concat([...svg.querySelectorAll('image')].map(e => ({e, b: box(e)})));
  const out = [];
  const inside = (x, y, b, pad = 0) => x >= b.l - pad && x <= b.r + pad && y >= b.t - pad && y <= b.b + pad;
  for (const t of texts) {
    if (t.b.l < -1 || t.b.t < -1 || t.b.r > W + 1 || t.b.b > H + 1)
      out.push({kind: 'canvas', text: t.s, box: t.b});
  }
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i].b, c = texts[j].b;
    const ox = Math.min(a.r, c.r) - Math.max(a.l, c.l), oy = Math.min(a.b, c.b) - Math.max(a.t, c.t);
    if (ox > 2 && oy > 3) out.push({kind: 'overlap', text: texts[i].s, other: texts[j].s});
  }
  for (const t of texts) {
    const x0 = parseFloat(t.e.getAttribute('x')), y0 = parseFloat(t.e.getAttribute('y'));
    const anchor = t.e.getAttribute('text-anchor') || 'start';
    const ax = anchor === 'middle' ? (t.b.l + t.b.r) / 2 : anchor === 'end' ? t.b.r : t.b.l;
    const ay = (t.b.t + t.b.b) / 2;
    const homes = panels.filter(p => inside(ax, ay, p.b)).sort((p, q) =>
        (p.b.r - p.b.l) * (p.b.b - p.b.t) - (q.b.r - q.b.l) * (q.b.b - q.b.t));
    for (const p of targets) {                       // text running into a panel or image it does not start in
      if (homes.includes(p) || inside(ax, ay, p.b)) continue;
      const ox = Math.min(t.b.r, p.b.r) - Math.max(t.b.l, p.b.l), oy = Math.min(t.b.b, p.b.b) - Math.max(t.b.t, p.b.t);
      if (ox > 2 && oy > 3) out.push({kind: 'intrudes', text: t.s, into: p.e.tagName, by: Math.round(ox)});
    }
    if (!homes.length) continue;
    const h = homes[0].b;
    const spill = Math.max(h.l - t.b.l, t.b.r - h.r, t.b.b - h.b, h.t - t.b.t);
    if (spill > 2) out.push({kind: 'overflow', text: t.s, by: Math.round(spill)});
  }
  const decorative = e => {
    const cs = getComputedStyle(e), b = box(e);
    if (parseFloat(cs.strokeOpacity) * parseFloat(cs.opacity) < 0.1) return true;      // faint grid
    return (b.b - b.t) >= H - 2 || (b.r - b.l) >= W - 2;                                 // canvas-spanning rule
  };
  const strokes = [...svg.querySelectorAll('line, path')].filter(e => !hidden(e) &&
      (e.getAttribute('stroke') || '') !== '' && (e.getAttribute('stroke') || 'none') !== 'none' && !decorative(e));
  for (const s of strokes) {
    const len = s.getTotalLength ? s.getTotalLength() : 0;
    if (len < 12) continue;
    const m = s.getScreenCTM();
    const pts = [];
    for (let k = 0; k <= 60; k++) {
      const p = s.getPointAtLength(len * k / 60);
      pts.push(new DOMPoint(p.x, p.y).matrixTransform(m));
    }
    const arrow = !!s.getAttribute('marker-end');
    const hits = new Set();
    for (const t of texts) for (const p of pts.slice(2, -2)) if (inside(p.x, p.y, t.b, 1)) { hits.add(t.s); break; }
    for (const h of hits) out.push({kind: 'crossing', text: h, stroke: arrow ? 'arrow' : 'line'});
    if (arrow) {
      const end = pts[pts.length - 1];
      if (!targets.some(p => inside(end.x, end.y, p.b, 14)))
        out.push({kind: 'dangling', at: [Math.round(end.x), Math.round(end.y)]});
    }
  }
  const seen = new Set();
  return JSON.stringify(out.filter(o => { const k = JSON.stringify(o); if (seen.has(k)) return false; seen.add(k); return true; }));
})()
"""

def audit(svg_path):
    svg = open(svg_path, encoding="utf-8").read()
    svg = re.sub(r"^<\?xml[^>]*>\s*", "", svg)
    page = ("<!doctype html><html><body style='margin:0'>" + svg +
            "<pre id='audit'></pre><script>document.getElementById('audit').textContent=" + JS + ";</script>"
            "</body></html>")
    with tempfile.TemporaryDirectory() as td:
        hp = os.path.join(td, "a.html")
        open(hp, "w", encoding="utf-8").write(page)
        r = subprocess.run([BROWSER, "--headless=new", f"--user-data-dir={td}", "--dump-dom",
                            "--virtual-time-budget=4000", "file:///" + hp.replace("\\", "/")],
                           capture_output=True, timeout=180)
    m = re.search(r"<pre id=\"audit\">(.*?)</pre>", r.stdout.decode("utf-8", "replace"), re.S)
    if not m:
        return [{"kind": "error", "text": "audit script did not run"}]
    return json.loads(html.unescape(m.group(1)) or "[]")

def main():
    bad = 0
    for p in sys.argv[1:]:
        issues = audit(p)
        bad += len(issues)
        print(f"{os.path.basename(p)}: {'clean' if not issues else str(len(issues)) + ' issue(s)'}")
        for i in issues:
            print("   ", i["kind"], "|", {k: v for k, v in i.items() if k != "kind"})
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
