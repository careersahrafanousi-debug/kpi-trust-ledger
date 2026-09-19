# Excel workbook

`kpi-trust-ledger_dashboard.xlsx` - KPI Trust Ledger

Open it and the first sheet is the dashboard: KPI tiles across the top, then
6+ native Excel charts, each with the caption stating what it shows.
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
