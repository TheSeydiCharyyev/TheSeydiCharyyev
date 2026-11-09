"""Generates what-i-work-with.svg for the "What I Work With" section of the profile README.

Dark cards: one tile per technology with its brand icon (from stack/, used as-is), a soft glow
in the icon's colour and the name. Five tiles per row, the last row centred. Animated once on load.
The tiles have their own dark background, so the image looks the same in light and dark themes.

Run from the repo root:
    python .github/banner/make_what_i_work_with.py

To add a technology: put a 100x100 single-colour icon into stack/ (same format as the others)
and add a line to ITEMS.
"""
import os
import re
from html import escape

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(REPO, "what-i-work-with.svg")
ITEMS = [("JavaScript", "javascript"), ("TypeScript", "typescript"), ("React", "react"),
         ("React Native", "react"), ("Node.js", "nodedotjs"), ("Vue.js", "vuedotjs"),
         ("Svelte", "svelte"), ("Rust", "rust"), ("Delphi", "delphi")]
PER_ROW = 5
W, GAP, TILE_H, ICON = 840, 14, 116, 42
TILE_W = (W - GAP * (PER_ROW - 1)) / PER_ROW


def icon(name):
    s = open(os.path.join(REPO, "stack", f"{name}.svg"), encoding="utf-8").read()
    assert 'viewBox="0 0 100 100"' in s, f"stack/{name}.svg must use viewBox 0 0 100 100"
    inner = re.search(r"<svg[^>]*>(.*)</svg>", s, flags=re.S).group(1)
    color = re.search(r'fill="(#[0-9A-Fa-f]{6})"', s).group(1)
    return inner, color


rows = [ITEMS[i:i + PER_ROW] for i in range(0, len(ITEMS), PER_ROW)]
defs, tiles, k = [], [], 0
for r, row in enumerate(rows):
    row_w = len(row) * TILE_W + (len(row) - 1) * GAP
    x0 = (W - row_w) / 2
    y = r * (TILE_H + GAP)
    for c, (label, name) in enumerate(row):
        inner, color = icon(name)
        x = x0 + c * (TILE_W + GAP)
        cx = x + TILE_W / 2
        defs.append(f'<radialGradient id="g{k}" cx="50%" cy="50%" r="50%">'
                    f'<stop offset="0" stop-color="{color}" stop-opacity=".28"/>'
                    f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></radialGradient>')
        tiles.append(
            f'<g class="f" style="animation-delay:{0.05 + k * 0.07:.2f}s">'
            f'<rect x="{x:.1f}" y="{y + 0.5:.1f}" width="{TILE_W:.1f}" height="{TILE_H - 1}" rx="14" class="tile"/>'
            f'<circle cx="{cx:.1f}" cy="{y + 44:.1f}" r="40" fill="url(#g{k})"/>'
            f'<svg x="{cx - ICON / 2:.1f}" y="{y + 23:.1f}" width="{ICON}" height="{ICON}" viewBox="0 0 100 100">{inner}</svg>'
            f'<text x="{cx:.1f}" y="{y + 94:.1f}" class="t" text-anchor="middle">{escape(label)}</text>'
            f'</g>')
        k += 1
H = len(rows) * TILE_H + (len(rows) - 1) * GAP

STYLE = """
text { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; }
.t { font-size: 15px; font-weight: 600; fill: #e6edf3; }
.tile { fill: #161b22; stroke: #30363d; }
.f { animation: fadeUp .6s cubic-bezier(.2,.8,.2,1) both; }
@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { .f { animation: none; } }
"""
names = ", ".join(l for l, _ in ITEMS)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
       f'role="img" aria-labelledby="t"><title id="t">{escape(names)}</title>'
       f'<defs>{"".join(defs)}</defs><style>{STYLE}</style>{"".join(tiles)}</svg>\n')
with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(svg)
print(f"{OUT}: {W}x{H}, {len(ITEMS)} cards, {len(svg.encode()) // 1024} KB")
