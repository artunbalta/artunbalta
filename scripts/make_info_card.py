#!/usr/bin/env python3
"""Hand-author a neofetch-style info card as a self-contained animated SVG.

A little terminal window (traffic-light title bar + dark rounded panel) whose
body reads like the output of ``neofetch``: a ``user@host`` header, a divider,
then colored key/value rows telling the story that stat numbers can't. Each line
fades + slides in on a short stagger, plays ONCE, then freezes.

    python scripts/make_info_card.py            ->  info-card.svg (animated)
    STATIC=1 python scripts/make_info_card.py    ->  info-card.svg (frozen frame)
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "info-card.svg"

# ---- Config -----------------------------------------------------------------
GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "artunbalta")
NAME = "Artun"
NOW = "MRes Neurotechnology @ Imperial College London"
PREV = "EEE @ Bilkent University"
STACK = "Python, PyTorch/NumPy, Bayesian inference, voice AI infra"
BUILDING = "ECHO (persistent virtual world) · Volina AI (voice agents)"
HIGHLIGHTS = "TEF Fellow · founder · neurotech + BCI"

ROWS = [
    ("Now", NOW),
    ("Prev", PREV),
    ("Stack", STACK),
    ("Building", BUILDING),
    ("Highlights", HIGHLIGHTS),
]

STATIC = os.environ.get("STATIC") == "1"

# ---- Palette ----------------------------------------------------------------
PANEL = "#0d1117"
TITLEBAR = "#161b22"
BORDER = "#30363d"
FG = "#c9d1d9"
MUTED = "#8b949e"
KEY = "#39d353"     # green, ties to the heatmap
ACCENT = "#58a6ff"  # blue for the "@host" half of the header
DOT_R, DOT_Y, DOT_G = "#ff5f56", "#ffbd2e", "#27c93f"

# ---- Geometry ---------------------------------------------------------------
WIDTH = 490
FS = 13.5           # body font size
ADV = FS * 0.6      # monospace advance width
LH = 22             # line height
PAD_L = 22
PAD_R = 22
KEYW = 12           # key column width in chars (value starts here)
TITLEBAR_H = 30

FONT = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def wrap(text: str, width_chars: int):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width_chars:
            lines.append(cur)
            cur = w
        else:
            cur = w if not cur else cur + " " + w
    if cur:
        lines.append(cur)
    return lines or [""]


def render():
    value_x = PAD_L + KEYW * ADV
    value_chars = max(8, int((WIDTH - PAD_R - value_x) / ADV))

    # Build the list of visual lines: (kind, key, text)
    visual = [("header", None, None), ("divider", None, None)]
    for key, val in ROWS:
        wrapped = wrap(val, value_chars)
        for i, seg in enumerate(wrapped):
            visual.append(("row", key if i == 0 else "", seg))
    visual.append(("blocks", None, None))

    body_top = TITLEBAR_H + 26
    height = body_top + len(visual) * LH + 14

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{height}" viewBox="0 0 {WIDTH} {height}" '
        f'font-family="{FONT}" role="img" '
        f'aria-label="{esc(NAME)} — neofetch info card">'
    )

    # ---- Styles -------------------------------------------------------------
    if STATIC:
        p.append("<style>.ln{opacity:1}</style>")
    else:
        p.append(
            "<style>\n"
            "  @keyframes lineIn {\n"
            "    from { opacity: 0; transform: translateX(-10px); }\n"
            "    to   { opacity: 1; transform: translateX(0); }\n"
            "  }\n"
            "  .ln { opacity: 0; animation: lineIn 0.45s ease-out forwards; }\n"
            "  @media (prefers-reduced-motion: reduce) {\n"
            "    .ln { opacity: 1 !important; animation: none !important;\n"
            "          transform: none !important; }\n"
            "  }\n"
            "</style>"
        )

    # ---- Window panel + title bar ------------------------------------------
    p.append(
        f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{height - 1}" '
        f'rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
    )
    p.append(
        f'<path d="M0.5 8.5 A8 8 0 0 1 8.5 0.5 H{WIDTH - 8.5} '
        f'A8 8 0 0 1 {WIDTH - 0.5} 8.5 V{TITLEBAR_H} H0.5 Z" '
        f'fill="{TITLEBAR}" stroke="{BORDER}"/>'
    )
    for i, col in enumerate((DOT_R, DOT_Y, DOT_G)):
        p.append(f'<circle cx="{18 + i * 18}" cy="{TITLEBAR_H / 2}" r="5.5" '
                 f'fill="{col}"/>')
    p.append(
        f'<text x="{WIDTH / 2}" y="{TITLEBAR_H / 2 + 4}" text-anchor="middle" '
        f'font-size="11.5" fill="{MUTED}">{esc(GITHUB_USERNAME)}@github: '
        f'~/whoami</text>'
    )

    # ---- Body lines ---------------------------------------------------------
    def anim(idx):
        if STATIC:
            return ""
        return f' style="animation-delay:{0.12 + idx * 0.11:.2f}s"'

    header_txt = f"{GITHUB_USERNAME}@github"
    at = header_txt.index("@")
    y = body_top
    for idx, (kind, key, text) in enumerate(visual):
        if kind == "header":
            p.append(
                f'<text class="ln"{anim(idx)} x="{PAD_L}" y="{y}" '
                f'font-size="{FS}" font-weight="700" xml:space="preserve">'
                f'<tspan fill="{KEY}">{esc(header_txt[:at])}</tspan>'
                f'<tspan fill="{MUTED}">@</tspan>'
                f'<tspan fill="{ACCENT}">{esc(header_txt[at + 1:])}</tspan></text>'
            )
        elif kind == "divider":
            dash = "─" * len(header_txt)
            p.append(
                f'<text class="ln"{anim(idx)} x="{PAD_L}" y="{y}" '
                f'font-size="{FS}" fill="{MUTED}">{dash}</text>'
            )
        elif kind == "row":
            label = (key + ":").ljust(KEYW) if key else " " * KEYW
            p.append(
                f'<text class="ln"{anim(idx)} x="{PAD_L}" y="{y}" '
                f'font-size="{FS}" xml:space="preserve">'
                f'<tspan fill="{KEY}" font-weight="600">{esc(label)}</tspan>'
                f'<tspan fill="{FG}">{esc(text)}</tspan></text>'
            )
        elif kind == "blocks":
            swatches = ["#161b22", "#0e4429", "#006d32", "#26a641",
                        "#39d353", "#69f0a0", ACCENT, MUTED]
            g = [f'<g class="ln"{anim(idx)}>']
            for i, col in enumerate(swatches):
                g.append(
                    f'<rect x="{PAD_L + i * 20}" y="{y - LH + 8}" width="15" '
                    f'height="15" rx="2" fill="{col}"/>'
                )
            g.append("</g>")
            p.append("".join(g))
        y += LH

    p.append("</svg>")
    OUT.write_text("\n".join(p), encoding="utf-8")
    mode = "static frame" if STATIC else "animated"
    print(f"Wrote {OUT.relative_to(ROOT)}  ({mode}, {WIDTH}x{height})")


if __name__ == "__main__":
    render()
