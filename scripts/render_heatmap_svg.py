#!/usr/bin/env python3
"""Render data/contributions.json as a self-contained animated SVG heatmap.

The classic 53-week x 7-day GitHub calendar of rounded boxes, drawn onto a dark
rounded panel so it stays readable on both light and dark GitHub themes. Boxes
reveal ONCE on load with a diagonal top-left -> bottom-right sweep (CSS
keyframes, ``animation-fill-mode: forwards``, single iteration) then FREEZE.

    python scripts/render_heatmap_svg.py  ->  contrib-heatmap.svg
"""

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "contrib-heatmap.svg"

# Level 0-4 map to the first five; #69f0a0 (level 5) is a neon top end reserved
# for the very-best day(s).
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

# Geometry (px). Tuned so the intrinsic width is ~860 to line up with README.
CELL = 12          # box side
GAP = 3            # gap between boxes
STRIDE = CELL + GAP
PAD_L = 30         # left gutter for weekday labels
PAD_T = 30         # top gutter for month labels
RADIUS = 2         # box corner radius (rx)

WEEKDAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}  # Sun=0 .. Sat=6
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

FG = "#c9d1d9"      # primary text
MUTED = "#8b949e"   # labels
PANEL = "#0d1117"   # panel background
BORDER = "#30363d"  # panel border


def sun_index(date: dt.date) -> int:
    """Day-of-week with Sunday=0 (matches GitHub's calendar rows)."""
    return (date.weekday() + 1) % 7


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_grid(days):
    """Return (grid, n_weeks). grid[week][row] = day dict or None."""
    first = dt.date.fromisoformat(days[0]["date"])
    week0_sunday = first - dt.timedelta(days=sun_index(first))
    n_weeks = 0
    placed = {}
    for d in days:
        date = dt.date.fromisoformat(d["date"])
        col = (date - week0_sunday).days // 7
        row = sun_index(date)
        placed[(col, row)] = d
        n_weeks = max(n_weeks, col + 1)
    grid = [[placed.get((c, r)) for r in range(7)] for c in range(n_weeks)]
    return grid, n_weeks, week0_sunday


def render():
    data = json.loads(DATA.read_text())
    days = data["days"]
    stats = data.get("stats", {})
    total = data.get("total", stats.get("total", 0))
    best_count = stats.get("best_day", {}).get("count", 0) or 0

    grid, n_weeks, week0_sunday = build_grid(days)

    grid_w = n_weeks * STRIDE - GAP
    grid_h = 7 * STRIDE - GAP
    # Panel spans full canvas; canvas width fixed to keep README alignment.
    width = 860
    legend_h = 22
    footer_h = 40
    height = PAD_T + grid_h + legend_h + footer_h + 16

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        f'font-family="ui-monospace, SFMono-Regular, \'SF Mono\', Menlo, '
        f'Consolas, \'Liberation Mono\', monospace" role="img" '
        f'aria-label="{esc(total)} contributions in the last year">'
    )

    # ---- Styles + one-shot diagonal reveal ---------------------------------
    parts.append(
        "<style>\n"
        "  @keyframes cellIn {\n"
        "    from { opacity: 0; transform: scale(0.2); }\n"
        "    to   { opacity: 1; transform: scale(1); }\n"
        "  }\n"
        "  .cell {\n"
        "    opacity: 0;\n"
        "    transform-box: fill-box;\n"
        "    transform-origin: center;\n"
        "    animation: cellIn 0.35s ease-out forwards;\n"
        "  }\n"
        "  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }\n"
        "  .chrome { opacity: 0; animation: fadeIn 0.6s ease-out forwards; }\n"
        "  @media (prefers-reduced-motion: reduce) {\n"
        "    .cell, .chrome { opacity: 1 !important; animation: none !important;\n"
        "                     transform: none !important; }\n"
        "  }\n"
        "</style>"
    )

    # ---- Panel background ---------------------------------------------------
    parts.append(
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
        f'rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
    )

    # ---- Month labels -------------------------------------------------------
    # Label each month at the first column it begins. Suppress a cramped leading
    # label when the first visible month spans < 2 columns (otherwise it would
    # collide with the next month), plus a general min-gap guard.
    col_months = [(week0_sunday + dt.timedelta(weeks=c)).month for c in range(n_weeks)]
    last_month = None
    last_label_x = -1e9
    for c in range(n_weeks):
        m = col_months[c]
        if m == last_month:
            continue
        last_month = m
        x = PAD_L + c * STRIDE
        if x >= width - 24:
            continue
        if c == 0:
            span = 1
            while span < n_weeks and col_months[span] == m:
                span += 1
            if span < 2:
                continue  # leading month too narrow to label cleanly
        if x - last_label_x < 2 * STRIDE:
            continue
        parts.append(
            f'<text class="chrome" x="{x}" y="{PAD_T - 10}" '
            f'font-size="11" fill="{MUTED}">{MONTHS[m]}</text>'
        )
        last_label_x = x

    # ---- Weekday labels -----------------------------------------------------
    for row, label in WEEKDAY_LABELS.items():
        y = PAD_T + row * STRIDE + CELL - 2
        parts.append(
            f'<text class="chrome" x="4" y="{y}" font-size="10" '
            f'fill="{MUTED}">{label}</text>'
        )

    # ---- Day cells ----------------------------------------------------------
    total_span = (n_weeks - 1) + 6  # max value of (week + row)
    for c in range(n_weeks):
        for r in range(7):
            d = grid[c][r]
            if d is None:
                continue
            level = d["level"]
            count = d["count"]
            if best_count > 0 and count >= best_count:
                color = PALETTE[5]  # neon top end for the very-best day(s)
            else:
                color = PALETTE[min(level, 4)]
            x = PAD_L + c * STRIDE
            y = PAD_T + r * STRIDE
            # Diagonal sweep: delay grows with (week + row).
            delay = (c + r) / total_span * 1.1
            title = (
                f'{count} contribution{"" if count == 1 else "s"} on {d["date"]}'
            )
            parts.append(
                f'<rect class="cell" x="{x}" y="{y}" width="{CELL}" '
                f'height="{CELL}" rx="{RADIUS}" fill="{color}" '
                f'style="animation-delay:{delay:.3f}s">'
                f'<title>{esc(title)}</title></rect>'
            )

    # ---- Legend (Less -> More) ---------------------------------------------
    legend_y = PAD_T + grid_h + 16
    lx = width - 24 - 5 * STRIDE - 40
    parts.append(
        f'<text class="chrome" x="{lx - 6}" y="{legend_y + CELL - 2}" '
        f'text-anchor="end" font-size="11" fill="{MUTED}">Less</text>'
    )
    for i in range(5):
        parts.append(
            f'<rect class="chrome" x="{lx + i * STRIDE}" y="{legend_y}" '
            f'width="{CELL}" height="{CELL}" rx="{RADIUS}" fill="{PALETTE[i]}"/>'
        )
    parts.append(
        f'<text class="chrome" x="{lx + 5 * STRIDE + 6}" '
        f'y="{legend_y + CELL - 2}" font-size="11" fill="{MUTED}">More</text>'
    )

    # ---- Footer stats -------------------------------------------------------
    footer_y = legend_y + CELL + 22
    cur = stats.get("current_streak", {}).get("length", 0)
    lon = stats.get("longest_streak", {}).get("length", 0)
    best = stats.get("best_day", {})
    parts.append(
        f'<text class="chrome" x="{PAD_L}" y="{footer_y}" font-size="14" '
        f'fill="{FG}" font-weight="600">{total:,} contributions in the last year'
        f'</text>'
    )
    detail = f"current streak {cur} · longest {lon}"
    if best.get("count"):
        bd = dt.date.fromisoformat(best["date"]).strftime("%b %-d")
        detail += f" · best day {best['count']} on {bd}"
    parts.append(
        f'<text class="chrome" x="{width - 24}" y="{footer_y}" '
        f'text-anchor="end" font-size="11" fill="{MUTED}">{esc(detail)}</text>'
    )

    parts.append("</svg>")
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(
        f"Wrote {OUT.relative_to(ROOT)}  ({n_weeks} weeks, "
        f"{total:,} contributions, {width}x{height})"
    )


if __name__ == "__main__":
    render()
