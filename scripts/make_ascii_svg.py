#!/usr/bin/env python3
"""Turn source-prepped.png into a self-contained animated ASCII portrait SVG.

Design: MONOCHROME (one light-gray fill), high contrast, drawn on a dark rounded
panel so it reads on both GitHub themes. Each row is wrapped in a horizontal clip
that wipes left->right with a small block cursor riding the wipe edge; rows are
staggered top-to-bottom so the portrait "types" itself in. Animation is SMIL,
plays ONCE and FREEZES (fill="freeze", no looping).

If source-prepped.png is missing, a small placeholder portrait (a `whoami`
block) is emitted instead so the README still renders.

    python scripts/make_ascii_svg.py  ->  avi-ascii.svg
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREPPED = ROOT / "source-prepped.png"
OUT = ROOT / "avi-ascii.svg"

GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "artunbalta")

# Density ramp: bright/sparse -> dark/dense. Leading SPACE clears white -> blank.
RAMP = " .`:-=+*cs#%@"
COLS = 100                 # character columns
CHAR_ASPECT = 0.5          # cell width / cell height (~2:1 tall chars)

FG = "#c9d1d9"             # single light-gray glyph fill
PANEL = "#0d1117"
BORDER = "#30363d"

FS = 11.0                  # font size (px)
CW = FS * 0.6              # monospace cell width
LH = FS * 1.2              # line height  (== 2*CW so the face isn't squashed)
PAD = 14

FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def image_to_rows():
    """Downsample source-prepped.png to a glyph grid. Returns list[str] or None."""
    if not PREPPED.exists():
        return None
    import numpy as np
    from PIL import Image

    img = Image.open(PREPPED).convert("L")
    w, h = img.size
    rows = max(1, round(COLS * (h / w) * CHAR_ASPECT))
    small = img.resize((COLS, rows), Image.BOX)

    arr = np.asarray(small, dtype=np.float32)
    # Gamma-darken the midtones so lit skin falls into the glyph range and the
    # face gains real definition, while pure white (removed background) stays at
    # 255 -> the leading-space end of the ramp -> blank. Then a mild contrast
    # stretch around the midpoint for punch.
    arr = 255.0 * np.power(np.clip(arr / 255.0, 0, 1), 1.55)
    arr = np.clip((arr - 120.0) * 1.15 + 120.0, 0, 255)
    arr[arr > 250] = 255  # keep the background crisply blank

    n = len(RAMP) - 1
    lines = []
    for y in range(arr.shape[0]):
        chars = []
        for x in range(arr.shape[1]):
            darkness = 255.0 - arr[y, x]          # white -> 0 -> space
            chars.append(RAMP[int(round(darkness / 255.0 * n))])
        lines.append("".join(chars))
    return lines


def placeholder_rows():
    """A small monochrome ASCII block used when no photo is available."""
    return [
        "  $ whoami",
        "",
        "   __ _ _ __| |_ _   _ _ __ ",
        "  / _` | '__| __| | | | '_ \\ ",
        " | (_| | |  | |_| |_| | | | |",
        "  \\__,_|_|   \\__|\\__,_|_| |_|",
        "",
        f"  {GITHUB_USERNAME}",
        "",
        "  [ portrait offline ]",
        "  drop source-photo.png in the repo",
        "  root, then re-run:",
        "    python scripts/prep_photo.py",
        "    python scripts/make_ascii_svg.py",
    ]


def build_svg(rows):
    cols = max((len(r) for r in rows), default=1)
    rows = [r.ljust(cols) for r in rows]           # pad to a rectangle
    n_rows = len(rows)

    width = round(PAD * 2 + cols * CW)
    height = round(PAD * 2 + n_rows * LH)
    row_w = cols * CW

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" font-family="{FONT}" '
        f'role="img" aria-label="ASCII portrait of {esc(GITHUB_USERNAME)}">'
    )
    p.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
    )

    defs = ["<defs>"]
    texts = []
    cursors = []
    STAGGER = 0.03
    BASE = 0.15

    for r, line in enumerate(rows):
        stripped = line.rstrip(" ")
        a = len(line) - len(line.lstrip(" "))       # first non-space col
        b = len(stripped)                            # one past last non-space
        y_top = PAD + r * LH
        baseline = y_top + FS
        begin = BASE + r * STAGGER

        if b <= a:
            # blank row: nothing to type
            continue

        content_x = PAD + a * CW
        content_w = (b - a) * CW
        dur = min(0.5, max(0.12, (b - a) * 0.008))

        # Per-row clip that wipes left -> right, revealing the glyphs.
        defs.append(
            f'<clipPath id="c{r}"><rect x="{content_x:.1f}" y="{y_top:.1f}" '
            f'width="0" height="{LH:.1f}">'
            f'<animate attributeName="width" from="0" to="{content_w:.1f}" '
            f'begin="{begin:.2f}s" dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>'
        )
        # Full-width row text, forced to an exact width so cells align with the
        # clip/cursor geometry regardless of the browser's default advance.
        texts.append(
            f'<text x="{PAD}" y="{baseline:.1f}" font-size="{FS}" fill="{FG}" '
            f'textLength="{row_w:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'xml:space="preserve" clip-path="url(#c{r})">{esc(line)}</text>'
        )
        # Block cursor riding the wipe edge, fading out when the row finishes.
        cursors.append(
            f'<rect x="{content_x:.1f}" y="{y_top + 1:.1f}" width="{CW * 0.9:.1f}" '
            f'height="{LH - 2:.1f}" fill="{FG}" opacity="0">'
            f'<animate attributeName="x" from="{content_x:.1f}" '
            f'to="{content_x + content_w:.1f}" begin="{begin:.2f}s" '
            f'dur="{dur:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" '
            f'keyTimes="0;0.05;0.85;1" begin="{begin:.2f}s" dur="{dur:.2f}s" '
            f'fill="freeze"/></rect>'
        )

    defs.append("</defs>")
    p.extend(defs)
    p.extend(texts)
    p.extend(cursors)
    p.append("</svg>")
    OUT.write_text("\n".join(p), encoding="utf-8")
    return width, height, n_rows


def main():
    rows = image_to_rows()
    if rows is None:
        print("source-prepped.png not found -> emitting placeholder portrait.")
        print("  (run: python scripts/prep_photo.py && python scripts/make_ascii_svg.py)")
        rows = placeholder_rows()
        kind = "placeholder"
    else:
        kind = "portrait"
    w, h, n = build_svg(rows)
    print(f"Wrote {OUT.relative_to(ROOT)}  ({kind}, {n} rows, {w}x{h})")


if __name__ == "__main__":
    main()
