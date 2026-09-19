# Power BI semantic model

KPI Trust Ledger

```
powerbi/
  kpi-trust-ledger.SemanticModel/
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

18 DAX measures over 13 tables, generated from
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
