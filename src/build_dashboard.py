"""
Builds a self-contained HTML dashboard from the project's SQLite database.

Reads `dashboard/dashboard_config.json`, which holds the project title, the SQL
behind every card and chart, and the chart definitions. Runs each query, writes
the results to `dashboard/data.json`, and renders `dashboard/index.html`.

The point of driving this from SQL in a config file is that the dashboard cannot
drift from the analysis. Every figure on the page is the output of a query in
this repository, run against the same database as `sql/06_sql_analysis.sql`.

Usage:
    python src/load_sqlite.py      # database must exist first
    python src/build_dashboard.py

Output is a single HTML file with the data inlined, so it works from the local
filesystem and from GitHub Pages with no server and no build step.
"""

import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DASH = os.path.join(ROOT, "dashboard")
CONFIG = os.path.join(DASH, "dashboard_config.json")


def run_queries(db_path, queries):
    if not os.path.exists(db_path):
        sys.exit(f"Database not found at {db_path}. Run python src/load_sqlite.py first.")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    out = {}
    for name, sql in queries.items():
        try:
            rows = [dict(r) for r in con.execute(sql).fetchall()]
        except sqlite3.Error as e:
            sys.exit(f"Query '{name}' failed: {e}")
        if not rows:
            sys.exit(f"Query '{name}' returned no rows. A dashboard tile would be blank.")
        out[name] = rows
        print(f"  {name:<28} {len(rows):>4} rows")
    con.close()
    return out


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #0f1419;
    --panel: #171d24;
    --panel-2: #1e2630;
    --line: #2a333f;
    --text: #e6edf3;
    --muted: #8b98a5;
    --accent: #4c9aff;
    --good: #35b77d;
    --warn: #e0a33e;
    --bad: #e05c5c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  header {
    padding: 28px 32px 22px; border-bottom: 1px solid var(--line);
    background: linear-gradient(180deg, #131a21, var(--bg));
  }
  h1 { margin: 0 0 6px; font-size: 22px; letter-spacing: -0.2px; }
  .sub { color: var(--muted); font-size: 13.5px; max-width: 900px; }
  .synthetic {
    display: inline-block; margin-top: 12px; padding: 5px 11px; border-radius: 4px;
    background: rgba(76,154,255,.12); border: 1px solid rgba(76,154,255,.32);
    color: #9dc4ff; font-size: 12px; font-weight: 500;
  }
  main { padding: 24px 32px 56px; max-width: 1560px; margin: 0 auto; }
  .kpis {
    display: grid; gap: 12px; margin-bottom: 26px;
    grid-template-columns: repeat(auto-fit, minmax(178px, 1fr));
  }
  .kpi {
    background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
    padding: 15px 16px 14px;
  }
  .kpi .label {
    color: var(--muted); font-size: 11.5px; text-transform: uppercase;
    letter-spacing: .07em; font-weight: 600; margin-bottom: 9px;
  }
  .kpi .value { font-size: 27px; font-weight: 650; letter-spacing: -0.5px; line-height: 1.1; }
  .kpi .note { color: var(--muted); font-size: 12px; margin-top: 6px; }
  .kpi.good .value { color: var(--good); }
  .kpi.warn .value { color: var(--warn); }
  .kpi.bad  .value { color: var(--bad); }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(12, 1fr); }
  .card {
    background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
    padding: 17px 18px 14px; min-width: 0;
  }
  .card.w4 { grid-column: span 4; }
  .card.w6 { grid-column: span 6; }
  .card.w8 { grid-column: span 8; }
  .card.w12 { grid-column: span 12; }
  @media (max-width: 1080px) { .card.w4, .card.w6, .card.w8 { grid-column: span 12; } }
  .card h2 { margin: 0 0 3px; font-size: 14.5px; font-weight: 620; }
  .card .desc { color: var(--muted); font-size: 12.5px; margin: 0 0 14px; }
  .chart-wrap { position: relative; height: 290px; }
  .chart-wrap.tall { height: 380px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); }
  th {
    color: var(--muted); font-size: 11.5px; text-transform: uppercase;
    letter-spacing: .05em; font-weight: 600; white-space: nowrap;
  }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tbody tr:hover { background: var(--panel-2); }
  .scroll { max-height: 430px; overflow-y: auto; }
  .pill { padding: 2px 8px; border-radius: 10px; font-size: 11.5px; font-weight: 600; }
  .pill.good { background: rgba(53,183,125,.15); color: var(--good); }
  .pill.warn { background: rgba(224,163,62,.15); color: var(--warn); }
  .pill.bad  { background: rgba(224,92,92,.15);  color: var(--bad); }
  footer {
    border-top: 1px solid var(--line); padding: 22px 32px 40px;
    color: var(--muted); font-size: 12.5px; max-width: 1560px; margin: 0 auto;
  }
  footer p { margin: 0 0 9px; max-width: 900px; }
  footer code {
    background: var(--panel-2); padding: 1.5px 5px; border-radius: 3px;
    font-size: 12px; color: #b9c6d3;
  }
  a { color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <p class="sub">__SUBTITLE__</p>
  <div class="synthetic">Fully synthetic data &middot; no employer, patient or confidential information</div>
</header>
<main>
  <div class="kpis" id="kpis"></div>
  <div class="grid" id="grid"></div>
</main>
<footer>
  <p><strong>How this page is built.</strong> Every value comes from a SQL query stored in
  <code>dashboard/dashboard_config.json</code> and run against <code>__DB__</code> by
  <code>src/build_dashboard.py</code>. Nothing is typed in by hand, so the dashboard cannot
  drift away from the analysis in <code>sql/</code>. Rebuild with
  <code>python src/load_sqlite.py &amp;&amp; python src/build_dashboard.py</code>.</p>
  <p><strong>Limitations.</strong> __LIMITS__</p>
  <p>__FOOTER__</p>
</footer>
<script>
const DATA = __DATA__;
const SPEC = __SPEC__;

const FONT = getComputedStyle(document.body).fontFamily;
Chart.defaults.font.family = FONT;
Chart.defaults.font.size = 12;
Chart.defaults.color = '#8b98a5';
Chart.defaults.borderColor = '#2a333f';
Chart.defaults.plugins.legend.labels.boxWidth = 11;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.maintainAspectRatio = false;

const PALETTE = ['#4c9aff','#35b77d','#e0a33e','#e05c5c','#a77bde','#3fb8c4','#d98ab8','#8b98a5'];
const SEMANTIC = { good:'#35b77d', warn:'#e0a33e', bad:'#e05c5c', accent:'#4c9aff', muted:'#8b98a5' };

function colourFor(i, spec) {
  if (spec && spec.colour) return SEMANTIC[spec.colour] || spec.colour;
  return PALETTE[i % PALETTE.length];
}

function fmt(v, unit) {
  if (v === null || v === undefined) return '\\u2014';
  if (typeof v !== 'number') return v;
  let s = Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, {maximumFractionDigits: 2});
  if (unit === 'pct') s += '%';
  if (unit === 'usd') s = '$' + Math.round(v).toLocaleString();
  if (unit === 'hours') s += 'h';
  if (unit === 'days') s += 'd';
  return s;
}

// KPI cards
const kpiHost = document.getElementById('kpis');
for (const k of SPEC.kpis) {
  const row = DATA[k.query][0];
  const el = document.createElement('div');
  el.className = 'kpi' + (k.tone ? ' ' + k.tone : '');
  el.innerHTML = '<div class="label"></div><div class="value"></div>' + (k.note ? '<div class="note"></div>' : '');
  el.querySelector('.label').textContent = k.label;
  el.querySelector('.value').textContent = fmt(row[k.field], k.unit);
  if (k.note) el.querySelector('.note').textContent = k.note;
  kpiHost.appendChild(el);
}

// Cards
const grid = document.getElementById('grid');
for (const card of SPEC.cards) {
  const rows = DATA[card.query];
  const el = document.createElement('div');
  el.className = 'card w' + (card.width || 6);
  const h = document.createElement('h2'); h.textContent = card.title; el.appendChild(h);
  if (card.desc) { const d = document.createElement('p'); d.className = 'desc'; d.textContent = card.desc; el.appendChild(d); }

  if (card.type === 'table') {
    const wrap = document.createElement('div');
    wrap.className = card.scroll === false ? '' : 'scroll';
    const t = document.createElement('table');
    const thead = document.createElement('thead');
    const htr = document.createElement('tr');
    for (const c of card.columns) {
      const th = document.createElement('th');
      th.textContent = c.label;
      if (c.unit || c.numeric) th.className = 'num';
      htr.appendChild(th);
    }
    thead.appendChild(htr); t.appendChild(thead);
    const tb = document.createElement('tbody');
    for (const r of rows) {
      const tr = document.createElement('tr');
      for (const c of card.columns) {
        const td = document.createElement('td');
        if (c.unit || c.numeric) td.className = 'num';
        if (c.pill) {
          const sp = document.createElement('span');
          sp.className = 'pill ' + (card.pillMap && card.pillMap[r[c.field]] ? card.pillMap[r[c.field]] : 'warn');
          sp.textContent = r[c.field];
          td.appendChild(sp);
        } else {
          td.textContent = fmt(r[c.field], c.unit);
        }
        tr.appendChild(td);
      }
      tb.appendChild(tr);
    }
    t.appendChild(tb); wrap.appendChild(t); el.appendChild(wrap);
    grid.appendChild(el);
    continue;
  }

  const wrap = document.createElement('div');
  wrap.className = 'chart-wrap' + (card.tall ? ' tall' : '');
  const cv = document.createElement('canvas');
  wrap.appendChild(cv); el.appendChild(wrap); grid.appendChild(el);

  const labels = rows.map(r => r[card.label_field]);
  let cfg;

  if (card.type === 'scatter') {
    cfg = {
      type: 'scatter',
      data: { datasets: rows.map((r, i) => ({
        label: String(r[card.label_field]),
        data: [{x: r[card.x], y: r[card.y]}],
        backgroundColor: PALETTE[i % PALETTE.length],
        pointRadius: 8, pointHoverRadius: 10
      })) },
      options: {
        scales: {
          x: { title: {display: true, text: card.x_title}, grid: {color: '#222a34'} },
          y: { title: {display: true, text: card.y_title}, grid: {color: '#222a34'} }
        }
      }
    };
  } else if (card.type === 'doughnut') {
    cfg = {
      type: 'doughnut',
      data: { labels, datasets: [{
        data: rows.map(r => r[card.series[0].field]),
        backgroundColor: PALETTE, borderColor: '#171d24', borderWidth: 2
      }] },
      options: { cutout: '58%', plugins: { legend: { position: 'right' } } }
    };
  } else {
    const horizontal = card.type === 'hbar';
    cfg = {
      type: card.type === 'line' ? 'line' : 'bar',
      data: { labels, datasets: card.series.map((s, i) => ({
        label: s.label,
        data: rows.map(r => r[s.field]),
        type: s.as === 'line' ? 'line' : undefined,
        backgroundColor: colourFor(i, s),
        borderColor: colourFor(i, s),
        borderWidth: s.as === 'line' || card.type === 'line' ? 2 : 0,
        borderRadius: s.as === 'line' || card.type === 'line' ? 0 : 3,
        tension: 0.28,
        pointRadius: 3,
        fill: false,
        yAxisID: s.axis === 'right' ? 'y1' : 'y',
        order: s.as === 'line' ? 0 : 1
      })) },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        plugins: { legend: { display: card.series.length > 1 } },
        scales: {
          x: { grid: { color: horizontal ? '#222a34' : 'transparent' },
               ticks: { autoSkip: false, maxRotation: card.rotate || 0 },
               stacked: !!card.stacked },
          y: { grid: { color: horizontal ? 'transparent' : '#222a34' },
               beginAtZero: card.beginAtZero !== false,
               stacked: !!card.stacked,
               title: card.y_title ? {display: true, text: card.y_title} : undefined },
          ...(card.series.some(s => s.axis === 'right') ? { y1: {
            position: 'right', grid: {drawOnChartArea: false}, beginAtZero: true,
            title: card.y1_title ? {display: true, text: card.y1_title} : undefined
          } } : {})
        }
      }
    };
  }

  if (card.reference) {
    const v = card.reference.value;
    cfg.options.plugins = cfg.options.plugins || {};
    const label = card.reference.label;
    cfg.plugins = [{
      id: 'refline-' + card.title,
      afterDraw(chart) {
        const {ctx, chartArea, scales} = chart;
        const horizontal = card.type === 'hbar';
        const sc = horizontal ? scales.x : scales.y;
        const p = sc.getPixelForValue(v);
        ctx.save();
        ctx.strokeStyle = '#e0a33e'; ctx.setLineDash([5, 4]); ctx.lineWidth = 1.5;
        ctx.beginPath();
        if (horizontal) { ctx.moveTo(p, chartArea.top); ctx.lineTo(p, chartArea.bottom); }
        else { ctx.moveTo(chartArea.left, p); ctx.lineTo(chartArea.right, p); }
        ctx.stroke();
        ctx.setLineDash([]); ctx.fillStyle = '#e0a33e'; ctx.font = '600 11px ' + FONT;
        if (horizontal) { ctx.textAlign = 'center'; ctx.fillText(label, p, chartArea.top - 4); }
        else { ctx.textAlign = 'right'; ctx.fillText(label, chartArea.right - 2, p - 5); }
        ctx.restore();
      }
    }];
  }

  new Chart(cv, cfg);
}
</script>
</body>
</html>
"""


def main():
    with open(CONFIG) as f:
        cfg = json.load(f)

    db = os.path.join(ROOT, cfg["database"])
    print(f"building dashboard for {cfg['title']}")
    data = run_queries(db, cfg["queries"])

    spec = {"kpis": cfg["kpis"], "cards": cfg["cards"]}
    html = (PAGE
            .replace("__TITLE__", cfg["title"])
            .replace("__SUBTITLE__", cfg["subtitle"])
            .replace("__DB__", cfg["database"])
            .replace("__LIMITS__", cfg["limitations"])
            .replace("__FOOTER__", cfg["footer"])
            .replace("__DATA__", json.dumps(data, separators=(",", ":"), default=str))
            .replace("__SPEC__", json.dumps(spec, separators=(",", ":"))))

    os.makedirs(DASH, exist_ok=True)
    with open(os.path.join(DASH, "index.html"), "w") as f:
        f.write(html)
    with open(os.path.join(DASH, "data.json"), "w") as f:
        json.dump(data, f, indent=1, default=str)

    kb = os.path.getsize(os.path.join(DASH, "index.html")) / 1024
    print(f"\nwrote dashboard/index.html ({kb:.0f} KB, {len(cfg['kpis'])} cards, "
          f"{len(cfg['cards'])} tiles)")
    print("wrote dashboard/data.json")


if __name__ == "__main__":
    main()
