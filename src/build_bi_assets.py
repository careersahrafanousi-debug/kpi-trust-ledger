"""Generate Tableau, Power BI, Excel and static-chart assets from the same
dashboard_config.json that drives the HTML dashboard.

One config, four outputs. Nothing is typed in by hand, so no artifact can drift
away from the SQL in sql/.

Run from the repository root:

    python src/load_sqlite.py && python src/build_bi_assets.py

Writes:
    bi_extracts/<query>.csv        tidy aggregate extracts, one per query
    excel/<repo>_dashboard.xlsx    Excel workbook, native charts
    tableau/<repo>.twb             Tableau workbook (XML), reads bi_extracts/
    powerbi/                       semantic model (TMDL + TMSL) and DAX measures
    charts/<name>.png              static chart images for the README
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "dashboard" / "dashboard_config.json"

# Chart types we can render in Excel / Tableau / Power BI. Tables and scatter
# plots are deliberately excluded: they belong on the HTML page, not in a
# six-tile executive workbook.
CHARTABLE = {"bar", "hbar", "line", "doughnut"}

ACCENT = "3B82F6"
GOOD = "22C55E"
BAD = "EF4444"
WARN = "F59E0B"
MUTED = "94A3B8"
COLOURS = {"accent": ACCENT, "good": GOOD, "bad": BAD, "warn": WARN, "muted": MUTED}
PALETTE = [ACCENT, GOOD, WARN, BAD, MUTED, "A855F7", "14B8A6", "F472B6"]


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def safe_sheet(name: str) -> str:
    """Excel sheet names: 31 chars, no []:*?/\\ ."""
    cleaned = re.sub(r"[\[\]:*?/\\]", "", name)
    return cleaned[:31]


# --------------------------------------------------------------------------- #
# load config and run every query once
# --------------------------------------------------------------------------- #

def load() -> tuple[dict, dict[str, list[dict]]]:
    if not CONFIG.exists():
        die(f"missing {CONFIG}")
    cfg = json.loads(CONFIG.read_text())
    db = ROOT / cfg["database"]
    if not db.exists():
        die(f"database not found at {db} - run python src/load_sqlite.py first")

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    results: dict[str, list[dict]] = {}
    for name, sql in cfg["queries"].items():
        try:
            rows = [dict(r) for r in con.execute(sql).fetchall()]
        except sqlite3.Error as exc:
            die(f"query '{name}' failed: {exc}")
        if not rows:
            die(f"query '{name}' returned no rows")
        results[name] = rows
    con.close()
    return cfg, results


def numeric(rows: list[dict], field: str) -> bool:
    for row in rows:
        val = row.get(field)
        if val is None:
            continue
        return isinstance(val, (int, float))
    return False


def chart_cards(cfg: dict) -> list[dict]:
    """Cards we can render as a real chart, in config order."""
    out = []
    for card in cfg["cards"]:
        if card.get("type") not in CHARTABLE:
            continue
        if not card.get("label_field") or not card.get("series"):
            continue
        out.append(card)
    return out


# --------------------------------------------------------------------------- #
# tidy CSV extracts - the shared source for Tableau and Excel
# --------------------------------------------------------------------------- #

def write_extracts(results: dict[str, list[dict]]) -> dict[str, Path]:
    outdir = ROOT / "bi_extracts"
    outdir.mkdir(exist_ok=True)
    paths = {}
    for name, rows in results.items():
        path = outdir / f"{name}.csv"
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        paths[name] = path
    return paths


# --------------------------------------------------------------------------- #
# Excel workbook
# --------------------------------------------------------------------------- #

def build_excel(cfg: dict, results: dict[str, list[dict]], repo: str) -> Path:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, DoughnutChart, LineChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    # Light theme on purpose. The HTML dashboard is dark; an Excel workbook
    # with a dark canvas and white chart panels looks like a mistake, and it
    # prints badly. Native look, print-ready.
    DARK = "FFFFFF"
    PANEL = "F1F5F9"
    INK = "0F172A"
    DIM = "475569"

    # Single column of charts. Two columns made the sheet ~31cm wide, which
    # paginated into shredded pages on print and forced horizontal scrolling.
    CHART_W = 24.0
    CHART_H = 9.4
    ROWS_PER_CHART = 19
    LAST_COL = 22          # charts span B..V

    wb = Workbook()
    dash = wb.active
    dash.title = "Dashboard"
    dash.sheet_view.showGridLines = False
    dash.sheet_properties.tabColor = ACCENT
    dash.page_setup.orientation = "landscape"
    dash.page_setup.fitToWidth = 1
    dash.page_setup.fitToHeight = 0
    dash.sheet_properties.pageSetUpPr.fitToPage = True

    fill = PatternFill("solid", fgColor=DARK)
    panel = PatternFill("solid", fgColor=PANEL)
    edge = Side(style="thin", color="CBD5E1")
    box = Border(left=edge, right=edge, top=edge, bottom=edge)

    dash.column_dimensions["A"].width = 2
    for i in range(2, LAST_COL + 2):
        dash.column_dimensions[get_column_letter(i)].width = 11

    def paint(r1: int, r2: int) -> None:
        for row in dash.iter_rows(min_row=r1, max_row=r2, min_col=1,
                                  max_col=LAST_COL + 2):
            for cell in row:
                cell.fill = fill

    def block(row: int, text: str, size: int, colour: str, height: int,
              bold: bool = False, span: int = 3) -> None:
        cell = dash.cell(row=row, column=2, value=text)
        cell.font = Font(name="Calibri", size=size, bold=bold, color=colour)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        dash.merge_cells(start_row=row, start_column=2,
                         end_row=row + span - 1, end_column=LAST_COL)
        for r in range(row, row + span):
            dash.row_dimensions[r].height = height

    # ---- title
    block(2, cfg["title"], 22, INK, 30, bold=True, span=1)
    block(3, cfg["subtitle"], 10, DIM, 14, span=3)

    # ---- KPI tiles, four per row so they stay inside the chart width
    # darker tones so they stay legible on white
    tone_colour = {"good": "15803D", "bad": "B91C1C", "warn": "B45309"}
    kpis = cfg.get("kpis", [])[:8]
    row = 7
    for i, kpi in enumerate(kpis):
        if i and i % 4 == 0:
            row += 5
        col = 2 + (i % 4) * 5
        rows = results[kpi["query"]]
        val = rows[0].get(kpi["field"])
        unit = kpi.get("unit")
        if isinstance(val, (int, float)):
            if unit == "pct":
                text = f"{val:,.2f}%"
            elif unit == "usd":
                text = f"${val:,.0f}"
            elif unit == "hours":
                text = f"{val:,.1f}h"
            elif unit == "days":
                text = f"{val:,.1f}d"
            else:
                text = f"{val:,.0f}" if float(val).is_integer() else f"{val:,.2f}"
        else:
            text = str(val)

        c = dash.cell(row=row, column=col, value=kpi["label"].upper())
        c.font = Font(size=7, bold=True, color=DIM)
        c = dash.cell(row=row + 1, column=col, value=text)
        c.font = Font(size=16, bold=True,
                      color=tone_colour.get(kpi.get("tone"), INK))
        c = dash.cell(row=row + 2, column=col, value=kpi.get("note", ""))
        c.font = Font(size=7, color=DIM)
        c.alignment = Alignment(wrap_text=True, vertical="top")

        for r, span in ((row, 1), (row + 1, 1), (row + 2, 2)):
            dash.merge_cells(start_row=r, start_column=col,
                             end_row=r + span - 1, end_column=col + 4)
        for r in range(row, row + 4):
            for cc in range(col, col + 5):
                cell = dash.cell(row=r, column=cc)
                cell.fill = panel
                cell.border = box
        dash.row_dimensions[row].height = 12
        dash.row_dimensions[row + 1].height = 22
        dash.row_dimensions[row + 2].height = 12
        dash.row_dimensions[row + 3].height = 12

    anchor_row = row + 6

    # ---- charts, one per band
    cards = chart_cards(cfg)[:8]
    for card in cards:
        rows = results[card["query"]]
        label_field = card["label_field"]
        series = [s for s in card["series"] if numeric(rows, s["field"])]
        if not series:
            continue

        # Group by axis, then pick a type per group. A percentage next to a
        # count in the thousands becomes an invisible sliver on a shared axis,
        # and a series flagged as a line in the config must actually be a line
        # or the caption describing it is wrong.
        primary = [s for s in series if s.get("axis") != "right"]
        secondary = [s for s in series if s.get("axis") == "right"]
        if not primary:
            primary, secondary = secondary, []

        sheet_name = safe_sheet(f"q_{card['query']}")
        n = 1
        while sheet_name in wb.sheetnames:
            n += 1
            sheet_name = safe_sheet(f"q_{card['query']}_{n}")
        ws = wb.create_sheet(sheet_name)
        ordered = primary + secondary
        ws.append([label_field] + [s["label"] for s in ordered])
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for r in rows:
            ws.append([r.get(label_field)] + [r.get(s["field"]) for s in ordered])
        for i, width in enumerate([30] + [17] * len(ordered), start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        ws.freeze_panes = "A2"

        cnt = len(rows)
        cats = Reference(ws, min_col=1, min_row=2, max_row=cnt + 1)

        def make(defs: list[dict], first_col: int, axis_id: int | None):
            """Build one axis group as its own chart object."""
            as_line = all(d.get("as") == "line" for d in defs)
            if card["type"] == "line" or as_line:
                sub = LineChart()
                is_line = True
            else:
                sub = BarChart()
                sub.type = "bar" if card["type"] == "hbar" else "col"
                sub.grouping = "stacked" if card.get("stacked") else "clustered"
                if card.get("stacked"):
                    sub.overlap = 100
                else:
                    sub.gapWidth = 60
                is_line = False
            sub.add_data(Reference(ws, min_col=first_col,
                                   max_col=first_col + len(defs) - 1,
                                   min_row=1, max_row=cnt + 1),
                         titles_from_data=True)
            sub.set_categories(cats)
            for i, ser in enumerate(sub.series):
                raw = str(defs[i].get("colour", ""))
                colour = (raw[1:].upper() if raw.startswith("#") else
                          COLOURS.get(raw, PALETTE[i % len(PALETTE)]))
                if is_line:
                    ser.smooth = False
                    ser.graphicalProperties.line.width = 26000
                    ser.graphicalProperties.line.solidFill = colour
                elif str(defs[i].get("colour", "")).startswith("rgba(0,0,0,0)"):
                    ser.graphicalProperties.noFill = True        # waterfall offset
                    ser.graphicalProperties.line.noFill = True
                else:
                    ser.graphicalProperties.solidFill = colour
                    ser.graphicalProperties.line.noFill = True
                if not is_line:
                    # Absent this flag, LibreOffice draws negative bars upward.
                    ser.invertIfNegative = False
            # A bar chart whose value axis does not start at zero exaggerates
            # small differences - Excel autoscales to 55-62 on a set of
            # percentages in the high fifties and makes a 4-point spread look
            # like a chasm. Force zero whenever nothing is negative.
            if not is_line:
                vals = [r.get(d["field"]) for d in defs for r in rows
                        if isinstance(r.get(d["field"]), (int, float))]
                if vals and min(vals) >= 0:
                    sub.y_axis.scaling.min = 0
                elif vals:
                    # Negative values put the category axis through the middle
                    # of the plot, printing the labels over the bars. Push them
                    # to the low edge instead.
                    sub.x_axis.tickLblPos = "low"
            # Without an explicit crossing point LibreOffice draws negative
            # bars upward from zero, as if they were positive.
            sub.x_axis.crosses = "autoZero"
            if axis_id is None:
                sub.y_axis.crosses = "autoZero"
            if card.get("y_min") is not None:
                sub.y_axis.scaling.min = card["y_min"]
            if axis_id is not None:
                sub.y_axis.axId = axis_id
                sub.y_axis.majorGridlines = None
            return sub

        if card["type"] == "doughnut":
            chart = DoughnutChart(holeSize=55)
            chart.add_data(Reference(ws, min_col=2, min_row=1, max_row=cnt + 1),
                           titles_from_data=True)
            chart.set_categories(cats)
            # No data labels: six categories inside a ring overlap into mush.
            # The legend carries the names and the caption carries the number.
            chart.dataLabels = None
        else:
            chart = make(primary, 2, None)
            if card.get("y_title"):
                chart.y_axis.title = card["y_title"]
            elif len(primary) == 1:
                chart.y_axis.title = primary[0]["label"]
            if secondary:
                second = make(secondary, 2 + len(primary), 200)
                second.y_axis.title = (card.get("y1_title")
                                       or secondary[0]["label"])
                second.y_axis.crosses = "max"
                chart += second

        chart.title = card["title"]
        chart.style = 2
        chart.height = CHART_H
        chart.width = CHART_W
        if len(ordered) == 1 and card["type"] != "doughnut":
            chart.legend = None
        elif chart.legend is not None:
            chart.legend.position = "b"
            chart.legend.overlay = False

        paint(anchor_row, anchor_row + ROWS_PER_CHART)
        dash.add_chart(chart, f"B{anchor_row}")
        desc_row = anchor_row + ROWS_PER_CHART - 1
        if card.get("desc"):
            c = dash.cell(row=desc_row, column=2, value=card["desc"])
            c.font = Font(size=8, color=DIM)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            dash.merge_cells(start_row=desc_row, start_column=2,
                             end_row=desc_row + 1, end_column=LAST_COL)
        anchor_row += ROWS_PER_CHART + 2

    # ---- notes
    block(anchor_row, "How this workbook is built", 11, INK, 16, bold=True, span=1)
    block(anchor_row + 1,
          "Every figure here is produced by a SQL query stored in "
          "dashboard/dashboard_config.json and run against " + cfg["database"] +
          " by src/build_bi_assets.py. The q_* sheets are the raw query output; "
          "the charts on this sheet read those sheets directly, so the workbook "
          "cannot drift away from the analysis in sql/. Rebuild with: "
          "python src/load_sqlite.py && python src/build_bi_assets.py",
          9, DIM, 14, span=3)
    block(anchor_row + 5, "Limitations", 11, INK, 16, bold=True, span=1)
    block(anchor_row + 6, cfg["limitations"], 9, DIM, 14, span=4)
    block(anchor_row + 11, cfg["footer"], 8, DIM, 13, span=3)
    paint(1, anchor_row + 15)
    for r in range(1, anchor_row + 16):
        for c in range(2, LAST_COL + 1):
            cell = dash.cell(row=r, column=c)
            if cell.font and cell.font.size and cell.value is not None:
                cell.fill = fill
    # repaint KPI panels flattened by the pass above
    row = 7
    for i, _kpi in enumerate(kpis):
        if i and i % 4 == 0:
            row += 5
        col = 2 + (i % 4) * 5
        for r in range(row, row + 4):
            for cc in range(col, col + 5):
                dash.cell(row=r, column=cc).fill = panel

    outdir = ROOT / "excel"
    outdir.mkdir(exist_ok=True)
    path = outdir / f"{repo}_dashboard.xlsx"
    wb.save(path)
    return path


# --------------------------------------------------------------------------- #
# static charts for the README
# --------------------------------------------------------------------------- #

def build_charts(cfg: dict, results: dict[str, list[dict]]) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter

    outdir = ROOT / "charts"
    outdir.mkdir(exist_ok=True)
    written = []

    plt.rcParams.update({
        "figure.facecolor": "#0f172a",
        "axes.facecolor": "#0f172a",
        "axes.edgecolor": "#2a3750",
        "axes.labelcolor": "#94a3b8",
        "text.color": "#e7edf6",
        "xtick.color": "#94a3b8",
        "ytick.color": "#94a3b8",
        "grid.color": "#1f2a3d",
        "font.size": 9,
    })

    def col(s, i):
        c = s.get("colour", "")
        if c.startswith("rgba(0,0,0,0)"):
            return (0, 0, 0, 0)
        if c.startswith("#"):
            return c
        return "#" + COLOURS.get(c, PALETTE[i % len(PALETTE)])

    for card in chart_cards(cfg)[:6]:
        rows = results[card["query"]]
        labels = [str(r.get(card["label_field"])) for r in rows]
        series = [s for s in card["series"] if numeric(rows, s["field"])]
        if not series:
            continue

        fig, ax = plt.subplots(figsize=(8.4, 4.4), dpi=150)
        ax.grid(axis="x" if card["type"] == "hbar" else "y", lw=0.6, alpha=0.6)
        ax.set_axisbelow(True)

        if card["type"] == "doughnut":
            vals = [r.get(series[0]["field"]) or 0 for r in rows]
            wedges, _ = ax.pie(vals, startangle=90,
                               colors=["#" + PALETTE[i % len(PALETTE)]
                                       for i in range(len(vals))],
                               wedgeprops={"width": 0.42, "edgecolor": "#0f172a"})
            ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
                      frameon=False, fontsize=8)
            ax.set_aspect("equal")
            ax.grid(False)
        elif card["type"] == "line":
            ax2 = ax.twinx() if any(s.get("axis") == "right" for s in series) else None
            for i, s in enumerate(series):
                target = ax2 if (ax2 is not None and s.get("axis") == "right") else ax
                target.plot(labels, [r.get(s["field"]) for r in rows], marker="o",
                            ms=4, lw=2, label=s["label"], color=col(s, i))
            if ax2 is not None:
                right = [s for s in series if s.get("axis") == "right"]
                ax2.set_ylabel(card.get("y1_title") or right[0]["label"])
                ax2.spines["top"].set_visible(False)
                h1, l1 = ax.get_legend_handles_labels()
                h2, l2 = ax2.get_legend_handles_labels()
                ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="lower left",
                          bbox_to_anchor=(0, 1.0), ncol=len(h1 + h2))
                ax._twin_legend = True
            elif len(series) > 1:
                ax.legend(frameon=False, fontsize=8)
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        elif card["type"] == "hbar":
            width = 0.8 / len(series)
            pos = range(len(labels))
            for i, s in enumerate(series):
                ax.barh([p + i * width for p in pos],
                        [r.get(s["field"]) or 0 for r in rows], height=width,
                        label=s["label"], color=col(s, i))
            ax.set_yticks([p + 0.4 - width / 2 for p in pos])
            ax.set_yticklabels(labels, fontsize=8)
            ax.invert_yaxis()
            if len(series) > 1:
                ax.legend(frameon=False, fontsize=8)
        elif card.get("stacked"):
            pos = list(range(len(labels)))
            bottom = [0.0] * len(labels)
            for i, s in enumerate(series):
                vals = [r.get(s["field"]) or 0 for r in rows]
                ax.bar(pos, vals, bottom=bottom, width=0.7, color=col(s, i),
                       label=None if s["label"].startswith("(") else s["label"])
                bottom = [b + v for b, v in zip(bottom, vals)]
            ax.set_xticks(pos)
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
            ax.legend(frameon=False, fontsize=8)
        else:
            bars = [s for s in series if s.get("as") != "line"] or series
            width = 0.8 / len(bars)
            pos = range(len(labels))
            # Series flagged axis="right" (a rate beside a count) get their own
            # scale; on one shared axis they flatten into a line along zero.
            ax2 = ax.twinx() if any(s.get("axis") == "right" for s in series) else None
            for i, s in enumerate(series):
                target = ax2 if (ax2 is not None and s.get("axis") == "right") else ax
                vals = [r.get(s["field"]) or 0 for r in rows]
                if s.get("as") == "line":
                    target.plot([p + 0.4 - width / 2 for p in pos], vals, marker="o",
                                ms=4, lw=2, label=s["label"], color=col(s, i), zorder=3)
                else:
                    b = bars.index(s)
                    target.bar([p + b * width for p in pos], vals, width=width,
                               label=s["label"], color=col(s, i))
            if ax2 is not None:
                # Whichever axis carries the lines sits on top; gridlines live on
                # the bottom axis only so they never cut across the bars.
                left_lines = any(s.get("as") == "line" for s in series
                                 if s.get("axis") != "right")
                top, bottom_ax = (ax, ax2) if left_lines else (ax2, ax)
                top.set_zorder(bottom_ax.get_zorder() + 1)
                top.patch.set_visible(False)
                ax.grid(False)
                ax2.grid(False)
                bottom_ax.grid(axis="y", lw=0.6, alpha=0.6)
                bottom_ax.set_axisbelow(True)
            ax.set_xticks([p + 0.4 - width / 2 for p in pos])
            ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
            if ax2 is not None:
                right = [s for s in series if s.get("axis") == "right"]
                ax2.set_ylabel(card.get("y1_title") or right[0]["label"])
                ax2.set_ylim(bottom=0)
                ax2.spines["top"].set_visible(False)
                ax2.yaxis.set_major_formatter(FuncFormatter(
                    lambda v, _: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:g}"))
                h1, l1 = ax.get_legend_handles_labels()
                h2, l2 = ax2.get_legend_handles_labels()
                ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="lower left",
                          bbox_to_anchor=(0, 1.0), ncol=len(h1 + h2))
                ax._twin_legend = True
                if any(s.get("axis") != "right" and s.get("as") != "line" for s in series):
                    ax.set_ylim(bottom=0)
                if not card.get("y_title"):
                    left = [s for s in series if s.get("axis") != "right"]
                    ax.set_ylabel(left[0]["label"] if len(left) == 1 else "")
            elif len(series) > 1:
                ax.legend(frameon=False, fontsize=8)

        if card.get("y_min") is not None:
            ax.set_ylim(bottom=card["y_min"])
        if card.get("y_title") and card["type"] != "doughnut":
            (ax.set_xlabel if card["type"] == "hbar" else ax.set_ylabel)(card["y_title"])
        if card["type"] != "doughnut":
            (ax.xaxis if card["type"] == "hbar" else ax.yaxis).set_major_formatter(FuncFormatter(
                lambda v, _: f"{v:,.0f}" if abs(v) >= 1000 else f"{v:g}"))
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        ax.set_title(card["title"], color="#e7edf6", fontsize=11, loc="left",
                     pad=26 if getattr(ax, "_twin_legend", False) else 12,
                     fontweight="bold")
        fig.tight_layout()
        path = outdir / f"{slug(card['query'])}.png"
        fig.savefig(path, facecolor="#0f172a")
        plt.close(fig)
        written.append(path)
    return written


# --------------------------------------------------------------------------- #
# Tableau workbook (.twb is XML)
# --------------------------------------------------------------------------- #

def tableau_type(rows: list[dict], field: str) -> tuple[str, str]:
    """Return (datatype, role) for a column."""
    if numeric(rows, field):
        sample = next(r[field] for r in rows if r.get(field) is not None)
        dt = "integer" if isinstance(sample, int) else "real"
        return dt, "measure"
    return "string", "dimension"


def build_tableau(cfg: dict, results: dict[str, list[dict]], repo: str) -> Path:
    cards = chart_cards(cfg)[:6]
    used = []
    seen = set()
    for card in cards:
        if card["query"] in seen:
            continue
        seen.add(card["query"])
        used.append(card)

    wb = ET.Element("workbook", {
        "xmlns:user": "http://www.tableausoftware.com/xml/user",
        "source-build": "2023.1.0",
        "source-platform": "win",
        "version": "18.1",
    })
    ET.SubElement(wb, "preferences")
    datasources = ET.SubElement(wb, "datasources")

    for card in used:
        q = card["query"]
        rows = results[q]
        ds_name = f"federated.{q}"
        ds = ET.SubElement(datasources, "datasource", {
            "caption": q, "inline": "true", "name": ds_name, "version": "18.1"})
        conn = ET.SubElement(ds, "connection", {
            "class": "federated"})
        named = ET.SubElement(conn, "named-connections")
        nc = ET.SubElement(named, "named-connection", {
            "caption": "bi_extracts", "name": f"textscan.{q}"})
        ET.SubElement(nc, "connection", {
            "class": "textscan",
            "directory": "../bi_extracts",
            "filename": f"{q}.csv",
            "password": "",
            "server": "",
        })
        relation = ET.SubElement(conn, "relation", {
            "connection": f"textscan.{q}",
            "name": f"{q}.csv",
            "table": f"[{q}#csv]",
            "type": "table",
        })
        cols = ET.SubElement(relation, "columns", {
            "gridOrigin": "A1", "header": "yes", "outcome": "6"})
        for field in rows[0].keys():
            dt, _role = tableau_type(rows, field)
            ET.SubElement(cols, "column", {
                "datatype": dt, "name": field, "ordinal": str(
                    list(rows[0].keys()).index(field))})

        # column metadata so Tableau assigns dimension/measure correctly
        for field in rows[0].keys():
            dt, role = tableau_type(rows, field)
            ET.SubElement(ds, "column", {
                "caption": field.replace("_", " "),
                "datatype": dt,
                "name": f"[{field}]",
                "role": role,
                "type": "quantitative" if role == "measure" else "nominal",
            })

    worksheets = ET.SubElement(wb, "worksheets")
    for card in used:
        q = card["query"]
        rows = results[q]
        label_field = card["label_field"]
        series = [s for s in card["series"] if numeric(rows, s["field"])][:2]
        if not series:
            continue
        measure = series[0]["field"]
        title = card["title"][:250]

        ws = ET.SubElement(worksheets, "worksheet", {"name": title})
        table = ET.SubElement(ws, "table")
        view = ET.SubElement(table, "view")
        ET.SubElement(view, "datasources")
        dss = view.find("datasources")
        ET.SubElement(dss, "datasource", {"caption": q, "name": f"federated.{q}"})
        ET.SubElement(view, "datasource-dependencies",
                      {"datasource": f"federated.{q}"})
        dep = view.find("datasource-dependencies")
        dt, _ = tableau_type(rows, label_field)
        ET.SubElement(dep, "column", {
            "datatype": dt, "name": f"[{label_field}]", "role": "dimension",
            "type": "nominal"})
        for s in series:
            mdt, _ = tableau_type(rows, s["field"])
            ET.SubElement(dep, "column", {
                "datatype": mdt, "name": f"[{s['field']}]", "role": "measure",
                "type": "quantitative"})
            ET.SubElement(dep, "column-instance", {
                "column": f"[{s['field']}]",
                "derivation": "Sum",
                "name": f"[sum:{s['field']}:qk]",
                "pivot": "key",
                "type": "quantitative",
            })
        ET.SubElement(dep, "column-instance", {
            "column": f"[{label_field}]",
            "derivation": "None",
            "name": f"[none:{label_field}:nk]",
            "pivot": "key",
            "type": "nominal",
        })

        mark_type = {"bar": "Bar", "hbar": "Bar", "line": "Line",
                     "doughnut": "Pie"}[card["type"]]
        style = ET.SubElement(table, "style")
        ET.SubElement(style, "style-rule", {"element": "mark"})
        panes = ET.SubElement(table, "panes")
        pane = ET.SubElement(panes, "pane", {"selection-relaxation-option":
                                             "selection-relaxation-allow"})
        ET.SubElement(pane, "view")
        ET.SubElement(pane, "mark", {"class": mark_type})
        enc = ET.SubElement(pane, "encodings")
        if card["type"] == "doughnut":
            ET.SubElement(enc, "color", {"column": f"[federated.{q}].[none:{label_field}:nk]"})
            ET.SubElement(enc, "size", {"column": f"[federated.{q}].[sum:{measure}:qk]"})
        elif len(series) > 1:
            ET.SubElement(enc, "color", {"column": "[Measure Names]"})

        rowsel = ET.SubElement(table, "rows")
        colsel = ET.SubElement(table, "cols")
        dim_ref = f"[federated.{q}].[none:{label_field}:nk]"
        if len(series) > 1:
            measure_ref = "([Multiple Fields])"
            measure_ref = " + ".join(
                f"[federated.{q}].[sum:{s['field']}:qk]" for s in series)
        else:
            measure_ref = f"[federated.{q}].[sum:{measure}:qk]"

        if card["type"] == "hbar":
            rowsel.text = dim_ref
            colsel.text = measure_ref
        elif card["type"] == "doughnut":
            rowsel.text = ""
            colsel.text = ""
        else:
            rowsel.text = measure_ref
            colsel.text = dim_ref

    # ---- one dashboard holding every worksheet in a vertical flow
    dashboards = ET.SubElement(wb, "dashboards")
    dash = ET.SubElement(dashboards, "dashboard", {"name": cfg["title"][:120]})
    ET.SubElement(dash, "style")
    size = ET.SubElement(dash, "size", {"maxheight": "3200", "maxwidth": "1400",
                                        "minheight": "3200", "minwidth": "1400"})
    zones = ET.SubElement(dash, "zones")
    outer = ET.SubElement(zones, "zone", {
        "h": "100000", "id": "1", "type-v2": "layout-basic", "w": "100000",
        "x": "0", "y": "0"})
    flow = ET.SubElement(outer, "zone", {
        "h": "100000", "id": "2", "param": "vert", "type-v2": "layout-flow",
        "w": "100000", "x": "0", "y": "0"})

    n = max(len(used), 1)
    title_h = 6000
    each = (100000 - title_h) // n
    tz = ET.SubElement(flow, "zone", {
        "h": str(title_h), "id": "3", "type-v2": "text", "w": "100000",
        "x": "0", "y": "0"})
    fmt = ET.SubElement(tz, "formatted-text")
    run = ET.SubElement(fmt, "run", {"fontsize": "18", "bold": "true"})
    run.text = cfg["title"]
    run2 = ET.SubElement(fmt, "run", {"fontsize": "9"})
    run2.text = "\n" + cfg["subtitle"]

    zid = 4
    y = title_h
    for card in used:
        ET.SubElement(flow, "zone", {
            "h": str(each), "id": str(zid), "name": card["title"][:250],
            "w": "100000", "x": "0", "y": str(y)})
        zid += 1
        y += each

    outdir = ROOT / "tableau"
    outdir.mkdir(exist_ok=True)
    path = outdir / f"{repo}.twb"
    xml = ET.tostring(wb, encoding="unicode")
    path.write_text(
        "<?xml version='1.0' encoding='utf-8' ?>\n\n<!-- build "
        "20231.23.0217.0949 -->\n" + xml)
    # fail loudly rather than shipping malformed XML
    ET.parse(path)
    return path


# --------------------------------------------------------------------------- #
# Power BI semantic model: TMDL + TMSL + a readable DAX file
# --------------------------------------------------------------------------- #

def dax_measures(cfg: dict, results: dict[str, list[dict]]) -> list[dict]:
    """One measure per KPI, plus SUM/AVG measures for every charted field."""
    measures: list[dict] = []
    seen: set[str] = set()

    for kpi in cfg.get("kpis", []):
        table = kpi["query"]
        field = kpi["field"]
        name = kpi["label"]
        if name in seen:
            continue
        seen.add(name)
        unit = kpi.get("unit")
        fmt = {"pct": '0.00"%"', "usd": '\\$#,0', "hours": '#,0.0"h"',
               "days": '#,0.0"d"'}.get(unit, "#,0")
        measures.append({
            "name": name,
            "expression": f"SELECTEDVALUE ( '{table}'[{field}] )",
            "formatString": fmt,
            "description": (kpi.get("note") or
                            f"{name} from the {table} query extract."),
        })

    for card in chart_cards(cfg):
        table = card["query"]
        rows = results[table]
        for s in card["series"]:
            if not numeric(rows, s["field"]):
                continue
            name = f"{s['label']} ({table})"
            if name in seen:
                continue
            seen.add(name)
            agg = "AVERAGE" if "%" in s["label"] or "Avg" in s["label"] else "SUM"
            measures.append({
                "name": name,
                "expression": f"{agg} ( '{table}'[{s['field']}] )",
                "formatString": "#,0.00",
                "description": f"{s['label']} for the '{card['title']}' visual.",
            })
    return measures


def build_powerbi(cfg: dict, results: dict[str, list[dict]], repo: str) -> list[Path]:
    outdir = ROOT / "powerbi"
    outdir.mkdir(exist_ok=True)
    model_dir = outdir / f"{repo}.SemanticModel"
    defn_dir = model_dir / "definition"
    defn_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    tables = {name: rows for name, rows in results.items()}
    measures = dax_measures(cfg, results)

    def pbi_type(rows: list[dict], field: str) -> tuple[str, str]:
        if numeric(rows, field):
            sample = next(r[field] for r in rows if r.get(field) is not None)
            if isinstance(sample, int):
                return "int64", "int64"
            return "double", "double"
        return "string", "string"

    # ---- TMDL, one file per table (this is the diff-friendly format)
    for name, rows in tables.items():
        lines = [f"table {name}", ""]
        for field in rows[0].keys():
            dtype, _ = pbi_type(rows, field)
            lines += [
                f"\tcolumn {field}",
                f"\t\tdataType: {dtype}",
                f"\t\tsummarizeBy: {'sum' if dtype != 'string' else 'none'}",
                f"\t\tsourceColumn: {field}",
                "",
            ]
        for m in measures:
            if f"'{name}'[" not in m["expression"]:
                continue
            lines += [
                f"\tmeasure '{m['name']}' = {m['expression']}",
                f"\t\tformatString: {m['formatString']}",
                f"\t\tdisplayFolder: Measures",
                "\t\t/// " + m["description"],
                "",
            ]
        lines += [
            f"\tpartition {name} = m",
            "\t\tmode: import",
            "\t\tsource =",
            "\t\t\t\tlet",
            f'\t\t\t\t    Source = Csv.Document(File.Contents(ExtractFolder & "\\{name}.csv"),',
            "\t\t\t\t        [Delimiter=\",\", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),",
            "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
            "\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {",
        ]
        typed = []
        for field in rows[0].keys():
            dtype, _ = pbi_type(rows, field)
            m_type = {"int64": "Int64.Type", "double": "type number",
                      "string": "type text"}[dtype]
            typed.append(f'\t\t\t\t        {{"{field}", {m_type}}}')
        lines.append(",\n".join(typed))
        lines += [
            "\t\t\t\t    })",
            "\t\t\t\tin",
            "\t\t\t\t    Typed",
            "",
        ]
        path = defn_dir / f"{name}.tmdl"
        path.write_text("\n".join(lines))
        written.append(path)

    # ---- model + expressions (the folder parameter)
    model_tmdl = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        "annotation PBI_QueryOrder = [" + ", ".join(
            f'"{n}"' for n in tables) + "]",
        "",
    ] + [f"ref table {n}" for n in tables] + ["", "ref expression ExtractFolder"]
    (defn_dir / "model.tmdl").write_text("\n".join(model_tmdl))
    written.append(defn_dir / "model.tmdl")

    expr = [
        "expression ExtractFolder = \"..\\..\\bi_extracts\" meta "
        "[IsParameterQuery=true, Type=\"Text\", IsParameterQueryRequired=true]",
        "\tlineageTag: extract-folder-parameter",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
        "\t/// Folder holding the CSV extracts written by src/build_bi_assets.py.",
        "\t/// Point this at the absolute path of bi_extracts/ after cloning.",
    ]
    (defn_dir / "expressions.tmdl").write_text("\n".join(expr))
    written.append(defn_dir / "expressions.tmdl")

    (defn_dir / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1567\n")
    written.append(defn_dir / "database.tmdl")

    (model_dir / "definition.pbism").write_text(json.dumps({
        "version": "4.2",
        "settings": {},
    }, indent=2))
    written.append(model_dir / "definition.pbism")

    (model_dir / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": repo},
        "config": {"version": "2.0", "logicalId":
                   "00000000-0000-0000-0000-000000000000"},
    }, indent=2))
    written.append(model_dir / ".platform")

    # ---- TMSL equivalent, for Tabular Editor / XMLA deploy
    bim_tables = []
    for name, rows in tables.items():
        cols = []
        for field in rows[0].keys():
            dtype, _ = pbi_type(rows, field)
            cols.append({
                "name": field,
                "dataType": dtype,
                "sourceColumn": field,
                "summarizeBy": "sum" if dtype != "string" else "none",
            })
        tbl = {"name": name, "columns": cols,
               "partitions": [{
                   "name": name, "mode": "import",
                   "source": {"type": "m", "expression":
                              f'Csv.Document(File.Contents(ExtractFolder & "\\{name}.csv"), '
                              '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv])'},
               }]}
        tms = [m for m in measures if f"'{name}'[" in m["expression"]]
        if tms:
            tbl["measures"] = [{
                "name": m["name"], "expression": m["expression"],
                "formatString": m["formatString"],
                "description": m["description"],
            } for m in tms]
        bim_tables.append(tbl)

    bim = {
        "name": repo,
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {"legacyRedirects": True,
                                  "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": bim_tables,
            "expressions": [{
                "name": "ExtractFolder",
                "kind": "m",
                "expression": '"..\\..\\bi_extracts" meta [IsParameterQuery=true, '
                              'Type="Text", IsParameterQueryRequired=true]',
                "description": "Folder holding the CSV extracts written by "
                               "src/build_bi_assets.py.",
            }],
        },
    }
    (outdir / "model.bim").write_text(json.dumps(bim, indent=2))
    written.append(outdir / "model.bim")

    # ---- plain DAX file a reviewer can read in a pull request
    dax_lines = [
        f"// DAX measures - {cfg['title']}",
        "// Generated by src/build_bi_assets.py from dashboard/dashboard_config.json.",
        "// Paste into Power BI Desktop, or open powerbi/model.bim in Tabular Editor.",
        "",
    ]
    for m in measures:
        dax_lines += [
            f"// {m['description']}",
            f"{m['name']} =",
            f"    {m['expression']}",
            f"// format: {m['formatString']}",
            "",
        ]
    (outdir / "measures.dax").write_text("\n".join(dax_lines))
    written.append(outdir / "measures.dax")

    return written



# --------------------------------------------------------------------------- #
# per-folder READMEs, so each artifact explains itself
# --------------------------------------------------------------------------- #

def build_readmes(cfg: dict, results: dict[str, list[dict]], repo: str) -> None:
    n_extracts = len(results)
    n_charts = len(chart_cards(cfg)[:6])
    n_measures = len(dax_measures(cfg, results))
    title = cfg["title"]

    (ROOT / "bi_extracts" / "README.md").write_text(f"""# Query extracts

{n_extracts} CSV files, one per query in
[`../dashboard/dashboard_config.json`](../dashboard/dashboard_config.json),
written by [`../src/build_bi_assets.py`](../src/build_bi_assets.py) against
`{cfg['database']}`.

These exist so the Tableau workbook and the Power BI model can read the *same*
aggregates the HTML dashboard and the Excel workbook use, without needing a
SQLite ODBC driver installed. They are the output of the analysis, not a second
copy of the source data - the row-level tables stay in `../data/`.

Regenerate:

```
python src/load_sqlite.py
python src/build_bi_assets.py
```

If a query changes in `dashboard_config.json`, every artifact downstream of it
changes on the next build. That is the point: there is one definition of each
number.

Synthetic data only. No employer data, patient information, protected health
information, or confidential business information.
""")

    (ROOT / "excel" / "README.md").write_text(f"""# Excel workbook

`{repo}_dashboard.xlsx` - {title}

Open it and the first sheet is the dashboard: KPI tiles across the top, then
{n_charts}+ native Excel charts, each with the caption stating what it shows.
Every `q_*` sheet behind it is the raw output of one SQL query, and the charts
reference those sheets directly.

Built by [`../src/build_bi_assets.py`](../src/build_bi_assets.py) using
`openpyxl`. Nothing is pasted in by hand, so the workbook cannot disagree with
the SQL in [`../sql/`](../sql/).

## Choices worth explaining

- **Native Excel chart objects, not images.** A reviewer can click a bar and see
  the cell range behind it. A pasted picture proves nothing.
- **Percentages and counts are on separate axes.** A reopen rate of 6% next to a
  case count of 12,000 on one axis is a flat line at zero. Where a chart mixes
  the two, the count sits on the secondary axis and the caption says so.
- **Light theme.** The HTML dashboard is dark; a workbook is a thing people
  print and paste into decks, so this one is white and print-scaled to fit page
  width in landscape.
- **No pivot tables.** The aggregation already happened in SQL, where it can be
  reviewed. Re-aggregating in a pivot would hide it.

Synthetic data only. No employer data, patient information, protected health
information, or confidential business information.
""")

    (ROOT / "tableau" / "README.md").write_text(f"""# Tableau workbook

`{repo}.twb` - {title}

A `.twb` is XML, so this one is generated by
[`../src/build_bi_assets.py`](../src/build_bi_assets.py) and is readable and
diffable in a pull request. It carries {n_charts} worksheets plus one dashboard,
each wired to a CSV in [`../bi_extracts/`](../bi_extracts/).

## Opening it

1. Clone the repository. Keep the folder structure - the workbook points at
   `../bi_extracts/*.csv` with relative paths.
2. Rebuild the extracts if they are missing:
   `python src/load_sqlite.py && python src/build_bi_assets.py`
3. Open `{repo}.twb` in Tableau Desktop or Tableau Public.

**Honest caveat:** this file is written by script and has not been round-tripped
through Tableau Desktop, because Tableau does not run in the environment that
built it. The XML is schema-shaped and parses, and the data connections and
field roles are correct, but Tableau may re-lay-out the dashboard zones or ask
you to re-point a connection on first open. Open it, adjust, and re-save - the
re-saved file is the authoritative one.

## Why `.twb` and not `.twbx`

A `.twbx` is a zip with the data packaged inside it. That makes it a binary
blob in git: no diffs, no review, and a second copy of the data drifting away
from `../data/`. The `.twb` plus committed extracts gives the same result and
stays reviewable.

Synthetic data only. No employer data, patient information, protected health
information, or confidential business information.
""")

    (ROOT / "powerbi" / "README.md").write_text(f"""# Power BI semantic model

{title}

```
powerbi/
  {repo}.SemanticModel/
    definition/
      model.tmdl          model header, table refs
      database.tmdl       compatibility level
      expressions.tmdl    ExtractFolder parameter
      *.tmdl              one file per table: columns, measures, M partition
    definition.pbism
    .platform
  model.bim               the same model as TMSL, for Tabular Editor / XMLA
  measures.dax            every measure as plain readable DAX
```

{n_measures} DAX measures over {n_extracts} tables, generated from
[`../dashboard/dashboard_config.json`](../dashboard/dashboard_config.json) by
[`../src/build_bi_assets.py`](../src/build_bi_assets.py).

## Using it

**Tabular Editor** (easiest): open `model.bim`, set the `ExtractFolder`
parameter to the absolute path of `../bi_extracts`, refresh.

**Power BI Desktop:** open the `.SemanticModel` folder as a Power BI project
(requires the preview project-file setting), or create a blank report, connect
to `../bi_extracts/*.csv`, and paste the measures from `measures.dax`.

## Why there is no `.pbix` and no report layer here

A `.pbix` is a binary zip. It cannot be diffed, cannot be reviewed in a pull
request, and cannot be opened at all without a Power BI licence - so committing
one would make this folder less useful, not more.

The **model** is the part that carries the analytical thinking - tables,
typed columns, named measures with format strings and descriptions - and TMDL
is Microsoft's own text format for exactly that, so it is committed in full.

The **report layout** is deliberately not hand-authored. A malformed
`report.json` makes Power BI Desktop refuse to open the whole project, and
shipping a file that might not open is worse than shipping none. The page
layout, visual-by-visual, is specified in
[`../docs/10_dashboard_spec.md`](../docs/10_dashboard_spec.md), and the same
layout is already built and live as an HTML dashboard - so the design is
demonstrated, just not as a binary.

Synthetic data only. No employer data, patient information, protected health
information, or confidential business information.
""")

    (ROOT / "charts" / "README.md").write_text(f"""# Static charts

{n_charts} PNG charts rendered with `matplotlib` by
[`../src/build_bi_assets.py`](../src/build_bi_assets.py), from the same queries
in [`../dashboard/dashboard_config.json`](../dashboard/dashboard_config.json)
that drive every other artifact.

These are here so the findings are visible in the README and in the GitHub file
browser, with no tool to install and nothing to open. They are generated, never
edited by hand - if a query changes, rerun the build and the images change with
it.

Synthetic data only. No employer data, patient information, protected health
information, or confidential business information.
""")


# --------------------------------------------------------------------------- #

def main() -> None:
    cfg, results = load()
    repo = ROOT.name
    print(f"building BI assets for {cfg['title']}")

    extracts = write_extracts(results)
    print(f"  bi_extracts/      {len(extracts)} CSV extracts")

    xlsx = build_excel(cfg, results, repo)
    print(f"  excel/            {xlsx.name} ({xlsx.stat().st_size // 1024} KB)")

    twb = build_tableau(cfg, results, repo)
    print(f"  tableau/          {twb.name} ({twb.stat().st_size // 1024} KB)")

    pbi = build_powerbi(cfg, results, repo)
    print(f"  powerbi/          {len(pbi)} files (TMDL, TMSL, DAX)")

    pngs = build_charts(cfg, results)
    print(f"  charts/           {len(pngs)} PNG charts")

    build_readmes(cfg, results, repo)
    print("  README.md         written into each artifact folder")


if __name__ == "__main__":
    main()
