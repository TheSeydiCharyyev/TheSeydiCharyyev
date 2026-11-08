"""Generates the Projects cards (projects/*.gif) for the profile README.

Frosted-glass card: blurred colour blobs behind "glass", rounded corners, the logo,
name, tagline and a footer pill. A light sweep crosses each card once per loop,
staggered so it runs across the grid card by card.

Run from the repo root:
    python .github/banner/make_project_cards.py

Optional arguments: <scale> <outdir> (default 1.75 and projects/).
The layout is designed at 280x296; 1.75 gives 490x518.
Logos are read from orgs/ and used as-is. To add or change a card, edit CARDS below.

Needs: Python 3 with Pillow and numpy, ffmpeg on PATH, and the Windows font Bahnschrift.

Why Pillow writes the GIF: the rounded corners are transparent, and with transparency
ffmpeg's GIF encoder stores every frame in full (about 10 MB per card). ffmpeg still
builds one shared palette and palettises the frames (ordered dither keeps unchanged
areas identical); Pillow then stores each frame cropped to the region that changed.
"""
import glob
import os
import shutil
import subprocess
import sys
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S = float(sys.argv[1]) if len(sys.argv) > 1 else 1.75
OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(REPO, "projects")
CW, CH = 280, 296
W, H = round(CW * S), round(CH * S)
FPS, N = 20, 60
SHINE_FRAMES = 10
BAHN = r"C:\Windows\Fonts\bahnschrift.ttf"

CARDS = [
    dict(key="shapak", logo="orgs/shapak.png", name="Shapak-Apps", base="#140d16",
         c1="#ff851b", c2="#ff3d6e", tagline="Open-source mobile apps built in Turkmenistan",
         foot="shapak-apps.github.io", shine=4),
    dict(key="proofstone", logo="orgs/proofstone.png", name="proofstone", base="#0c1022",
         c1="#6e9cff", c2="#a06bff", tagline="Engineering roadmaps you can prove",
         foot="proofstone.dev", shine=14),
    dict(key="ykjam", logo="orgs/ykjam.png", name="Ykjam Terjime", base="#08141d",
         c1="#2ea3dd", c2="#23d3a8", tagline="Phrasebook & translator \u00b7 React Native / Expo",
         foot="App Store \u00b7 Google Play", shine=24),
    dict(key="hytay", logo="orgs/hytay.png", name="Hytaý dili 1", base="#1a0b0c",
         c1="#e53935", c2="#f5b82e", tagline="Chinese course for Turkmen speakers \u00b7 React Native / Expo",
         foot="App Store \u00b7 Google Play", shine=34),
]


def px(v):
    return v * S


def ipx(v):
    return int(round(v * S))


def rgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)], np.float32)


def bahn(size, var):
    f = ImageFont.truetype(BAHN, size)
    f.set_variation_by_name(var)
    return f


def fit_font(text, var, max_w, start, min_size=10):
    for s in range(start, min_size - 1, -1):
        f = bahn(s, var)
        if f.getlength(text) <= max_w:
            return f
    return bahn(min_size, var)


def mask_of(draw_fn):
    m = Image.new("L", (W, H), 0)
    draw_fn(ImageDraw.Draw(m))
    return np.asarray(m, np.float32) / 255


def blob(cx, cy, r):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    return np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))


def render_frames(c, tmp):
    rad = ipx(18)
    card = mask_of(lambda d: d.rounded_rectangle([0, 0, W - 1, H - 1], radius=rad, fill=255))
    alpha = (card >= 0.5).astype(np.uint8) * 255

    # colour blobs behind frosted glass
    img = np.zeros((H, W, 3), np.float32) + rgb(c["base"])
    img += blob(px(60), px(40), px(120))[..., None] * rgb(c["c1"]) * 0.55
    img += blob(px(250), px(230), px(130))[..., None] * rgb(c["c2"]) * 0.45
    img += blob(px(140), px(330), px(110))[..., None] * rgb(c["c1"]) * 0.25
    img = img * 0.82 + 0.05                                   # frost: lift + flatten
    top = np.clip(1 - np.arange(H, dtype=np.float32) / (H * 0.45), 0, 1)[:, None, None]
    img += top * 0.06                                          # top sheen
    rng = np.random.default_rng(7)
    img += rng.normal(0, 0.008, (H, W, 1)).astype(np.float32)  # glass grain

    # inner border
    bw = max(1, ipx(1))
    border = mask_of(lambda d: d.rounded_rectangle([bw, bw, W - 1 - bw, H - 1 - bw], radius=max(0, rad - bw),
                                                   outline=255, width=bw))
    img += border[..., None] * 0.22

    # text and footer pill
    nf = fit_font(c["name"], "SemiBold", px(236), ipx(28))
    tf = bahn(ipx(13), "Regular")
    ff = bahn(ipx(11), "Regular")
    name = mask_of(lambda d: d.text((W / 2, px(160)), c["name"], font=nf, fill=255, anchor="mm"))
    lines = textwrap.wrap(c["tagline"], 34)
    tag = mask_of(lambda d: [d.text((W / 2, px(190) + i * px(18)), l, font=tf, fill=255, anchor="mm")
                             for i, l in enumerate(lines)])
    fw = ff.getlength(c["foot"]) + px(24)
    pill_box = [W / 2 - fw / 2, px(250), W / 2 + fw / 2, px(272)]
    pill = mask_of(lambda d: d.rounded_rectangle(pill_box, radius=px(11), fill=255))
    pill_line = mask_of(lambda d: d.rounded_rectangle(pill_box, radius=px(11), outline=255, width=bw))
    foot = mask_of(lambda d: d.text((W / 2, px(261)), c["foot"], font=ff, fill=255, anchor="mm"))
    img = img * (1 - pill[..., None] * 0.10) + pill[..., None] * 0.10
    img += pill_line[..., None] * 0.18
    for m, a in ((name, 1.0), (tag, 0.80), (foot, 0.88)):
        img = img * (1 - m[..., None] * a) + m[..., None] * a

    # soft shadow, then the logo on top (logo pixels untouched)
    ls = ipx(92)
    logo = Image.open(os.path.join(REPO, c["logo"])).convert("RGBA").resize((ls, ls), Image.LANCZOS)
    la = np.asarray(logo, np.float32) / 255
    lx, ly = (W - ls) // 2, ipx(30)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([lx + ipx(6), ly + ipx(14), lx + ls - ipx(6), ly + ls + ipx(6)], fill=255)
    shadow = np.asarray(sh.filter(ImageFilter.GaussianBlur(px(10))), np.float32) / 255 * 0.55
    img = img * (1 - shadow[..., None])
    reg = img[ly:ly + ls, lx:lx + ls]
    img[ly:ly + ls, lx:lx + ls] = reg * (1 - la[..., 3:]) + la[..., :3] * la[..., 3:]

    # frames: static card + one diagonal light sweep per loop
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    diag = xx + yy * 0.55
    dmin, dmax = diag.min(), diag.max()
    for t in range(N):
        frame = img
        k = t - c["shine"]
        if 0 <= k < SHINE_FRAMES:
            pos = dmin - px(80) + (dmax - dmin + px(160)) * k / (SHINE_FRAMES - 1)
            frame = img + (np.exp(-((diag - pos) / px(28)) ** 2) * 0.28)[..., None]
        rgb8 = (np.clip(frame, 0, 1) * 255 + 0.5).astype(np.uint8)
        Image.fromarray(np.dstack([rgb8, alpha]), "RGBA").save(
            os.path.join(tmp, f"{t:03d}.png"), compress_level=1)


def assemble(frames_dir, gif):
    pal_dir = frames_dir + ".pal"
    shutil.rmtree(pal_dir, ignore_errors=True)
    os.makedirs(pal_dir)
    palette = os.path.join(pal_dir, "palette.png")
    src = os.path.join(frames_dir, "%03d.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf",
                    "palettegen=max_colors=256:reserve_transparent=1:stats_mode=full", palette], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", palette, "-lavfi",
                    "paletteuse=dither=bayer:bayer_scale=4:alpha_threshold=128",
                    os.path.join(pal_dir, "f%03d.png")], check=True)
    frames = []
    for p in sorted(glob.glob(os.path.join(pal_dir, "f*.png"))):
        with Image.open(p) as im:
            im.load()
            frames.append(im.copy())
    pal = frames[0].getpalette()
    assert all(f.mode == "P" and f.getpalette() == pal for f in frames), "frames do not share one palette"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=1000 // FPS, loop=0,
                   transparency=frames[0].info.get("transparency"), disposal=1, optimize=False)
    shutil.rmtree(pal_dir, ignore_errors=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    for c in CARDS:
        tmp = os.path.join(OUT, c["key"] + ".frames")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        render_frames(c, tmp)
        gif = os.path.join(OUT, c["key"] + ".gif")
        assemble(tmp, gif)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"{gif}: {W}x{H}, {N} frames, {os.path.getsize(gif) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
