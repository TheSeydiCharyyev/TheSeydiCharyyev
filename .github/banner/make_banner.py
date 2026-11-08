"""Generates about-banner.gif for the "About me" section of the profile README.

Glitch terminal: sha256 "block hash" background, the motto in two lines,
and a typed "> freedom tech · bitcoin · lightning · nostr" line.

Run from the repo root:
    python .github/banner/make_banner.py 2 about-banner.gif

Arguments: <scale> <out.gif>. The layout is designed at 830x260 and multiplied
by <scale>; 2 gives 1660x520 (sharp on HiDPI screens, about 2 MB).
To change the text, edit HEADS and SUB below.

Needs: Python 3 with Pillow and numpy, ffmpeg on PATH, and the Windows fonts
Bahnschrift and Consolas (paths in BAHN and MONO).

The loop starts on a frame where the line is fully typed, so a paused GIF
(GitHub "autoplay animated images" off) still shows the whole text.
"""
import hashlib
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
OUT_GIF = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else "about-banner.gif")
W, H = round(830 * S), round(260 * S)
FPS, N, START = 20, 60, 30
BAHN = r"C:\Windows\Fonts\bahnschrift.ttf"
MONO = r"C:\Windows\Fonts\consola.ttf"

CYAN, ORANGE, YELLOW, PURPLE = "#05d9e8", "#f7931a", "#ffd319", "#b45cff"
HEADS = (("NIL SATIS", 72), ("NISI OPTIMUM", 138))
SUB = "> freedom tech \u00b7 bitcoin \u00b7 lightning \u00b7 nostr"
WORD_COLORS = {"bitcoin": ORANGE, "lightning": YELLOW, "nostr": PURPLE}


def px(v):
    return v * S


def ipx(v):
    return int(round(v * S))


def rgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)


def rgb_tuple(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def blank():
    m = Image.new("L", (W, H), 0)
    return m, ImageDraw.Draw(m)


def arr(m):
    return np.asarray(m, np.float32) / 255.0


def to_mask(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "L")


def bahn(size, var):
    f = ImageFont.truetype(BAHN, size)
    f.set_variation_by_name(var)
    return f


def spaced_positions(text, f, cx, spacing):
    widths = [f.getlength(c) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    xs, x = [], cx - total / 2
    for w in widths:
        xs.append(x)
        x += w + spacing
    return xs, total


def text_mask(text, f, cx, cy, spacing=0):
    m, d = blank()
    xs, _ = spaced_positions(text, f, cx, spacing)
    for ch, x in zip(text, xs):
        d.text((x, cy), ch, font=f, fill=255, anchor="lm")
    return m


def fit_font(text, var, max_w, spacing, start, min_size=11):
    for s in range(start, min_size - 1, -1):
        f = bahn(s, var)
        if spaced_positions(text, f, 0, spacing)[1] <= max_w:
            return f
    return bahn(min_size, var)


def glow(mask, color, radii, core):
    """Additive neon light; radii are in 1x units."""
    c = rgb(color)
    acc = np.zeros((H, W), np.float32)
    for r, w in radii:
        acc += arr(mask.filter(ImageFilter.GaussianBlur(r * S))) * w
    tube = arr(mask.filter(ImageFilter.GaussianBlur(0.7 * S)))
    return acc[..., None] * c + tube[..., None] * (0.45 * c + 0.55) * core


def main():
    rng = np.random.default_rng(5)
    base = np.zeros((H, W, 3), np.float32) + rgb("#03050c")

    # static background: block-hash-like sha256 lines
    lh, lines = px(15), 20
    mono12 = ImageFont.truetype(MONO, ipx(12))
    strip = Image.new("L", (W, int(lh * lines) + 1), 0)
    sd = ImageDraw.Draw(strip)
    for i in range(lines):
        for col, x0 in enumerate((8, 430)):
            h = hashlib.sha256(f"seydi:{i}:{col}".encode()).hexdigest()
            sd.text((px(x0), i * lh), "0" * 19 + h[19:], font=mono12, fill=255)
    strip = arr(strip.filter(ImageFilter.GaussianBlur(0.5 * S)))[:H]
    base += strip[..., None] * rgb("#1fe0a0") * 0.13

    # corner labels
    base += glow(text_mask("[ PROOF OF WORK ]", mono12, px(90), px(18)), CYAN,
                 ((1, .4), (4, .2)), .6) * 0.7
    tr, td = blank()
    td.text((W - px(14), px(18)), "DON'T TRUST, VERIFY", font=mono12, fill=255, anchor="rm")
    base += glow(tr, ORANGE, ((1, .4), (4, .2)), .6) * 0.7

    # headline (motto)
    hf = fit_font(max((t for t, _ in HEADS), key=len), "Bold", W - px(80), px(8), ipx(70))
    sp = max(2, round(hf.size * 0.08))
    head = to_mask(sum(arr(text_mask(t, hf, W / 2, px(cy), sp)) for t, cy in HEADS))
    base += glow(head, CYAN, ((4, .35), (14, .3), (34, .25)), 0)
    nm = arr(head)

    # subtitle, typed letter by letter
    mono17 = ImageFont.truetype(MONO, ipx(17))
    cw = mono17.getlength("M")
    sx0 = W / 2 - cw * (len(SUB) + 1) / 2
    sub_y = px(196)
    chars, idx = [], 0
    for word in SUB.split(" "):
        col = rgb_tuple(WORD_COLORS.get(word, CYAN))
        for ch in word + " ":
            if idx < len(SUB):
                chars.append((ch, col))
            idx += 1
    full, fd = blank()
    for i, (ch, _) in enumerate(chars):
        if ch != " ":
            fd.text((sx0 + i * cw, sub_y), ch, font=mono17, fill=255, anchor="lm")
    sub_glow = glow(full, CYAN, ((2, .3), (8, .2)), 0)
    cache = {}

    def sub_layer(k):
        if k not in cache:
            cache.clear()
            img = Image.new("RGB", (W, H), (0, 0, 0))
            d = ImageDraw.Draw(img)
            for i, (ch, col) in enumerate(chars[:k]):
                if ch != " ":
                    d.text((sx0 + i * cw, sub_y), ch, font=mono17, fill=col, anchor="lm")
            cache[k] = np.asarray(img, np.float32) / 255
        return cache[k]

    cyan = rgb(CYAN)
    glitch = {11: 1, 12: 1, 13: .6, 37: 1, 38: .7, 50: .5}
    scan = np.ones((H, 1, 1), np.float32)
    scan[(np.floor(np.arange(H) / S).astype(int) % 3) == 0] = 0.72

    tmp = OUT_GIF + ".frames"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    L = len(chars)
    for t in range(N):
        frame = base.copy()
        gi = glitch.get(t, 0)
        a = ipx(2) + ipx(int(gi * 9))
        r_ch = np.roll(nm, -a, axis=1)
        c_ch = np.roll(nm, a, axis=1)
        frame[..., 0] += r_ch
        frame[..., 1] += c_ch * 0.92
        frame[..., 2] += c_ch
        frame += (nm * 0.25)[..., None]
        typed = min(L, int(t * 1.6))
        frame += sub_layer(typed) + sub_glow * (typed / L) * 0.6
        if (t // 6) % 2 == 0:
            x = sx0 + typed * cw
            y0, y1 = int(px(187)), int(px(205))
            x0, x1 = int(x + px(1)), int(x + cw - px(1))
            frame[y0:y1 + 1, x0:x1 + 1] += cyan * 0.85
        frame *= scan
        if gi:
            for _ in range(int(3 + gi * 4)):
                y0 = int(rng.integers(0, H - ipx(10)))
                hh = int(rng.integers(ipx(3), ipx(18)))
                dx = int(rng.integers(ipx(10), ipx(45))) * (1 if rng.random() < .5 else -1)
                frame[y0:y0 + hh] = np.roll(frame[y0:y0 + hh], dx, axis=1)
            if gi == 1:
                y0 = int(rng.integers(ipx(40), ipx(160)))
                frame[y0:y0 + ipx(6)] = 1 - np.clip(frame[y0:y0 + ipx(6)], 0, 1)
        out_i = (t - START) % N
        Image.fromarray((np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
            os.path.join(tmp, f"{out_i:03d}.png"), compress_level=1)

    vf = ("split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
          "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i",
                    os.path.join(tmp, "%03d.png"), "-vf", vf, "-loop", "0", OUT_GIF], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{OUT_GIF}: {W}x{H}, {N} frames, headline {hf.size}px, "
          f"{os.path.getsize(OUT_GIF) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
