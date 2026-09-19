# Query extracts

13 CSV files, one per query in
[`../dashboard/dashboard_config.json`](../dashboard/dashboard_config.json),
written by [`../src/build_bi_assets.py`](../src/build_bi_assets.py) against
`data/kpi_trust.db`.

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
