# Dashboard Specification — KPI Trust Ledger (Power BI)

The `.pbix` file is not committed. It is a binary that produces no useful diff and cannot be
reviewed in a pull request, so this specification is the artifact: model, measures, and page
layouts, complete enough to rebuild the report from the CSVs in this repo.

## Data model

Star-ish, with the governance tables treated as facts in their own right.

| Table | Role | Key |
|---|---|---|
| `reporting_layer` | Fact — certified appeals | Appeal_ID |
| `kpi_reconciliation` | Fact — one row per KPI/source pair | KPI_ID + Source |
| `kpi_certification` | Fact — one row per KPI | KPI_ID |
| `dq_exceptions` | Fact — one row per exception | Exception_ID |
| `kpi_catalog` | Dimension | KPI_ID |
| `dim_payer` | Dimension | Payer_ID |
| `dim_team` | Dimension | Team_ID |
| `dim_date` | Dimension, marked as the date table | Date |

Relationships: `kpi_catalog[KPI_ID]` one-to-many into both `kpi_reconciliation` and
`kpi_certification`. `dim_payer` and `dim_team` one-to-many into `reporting_layer`.
`dim_date[Date]` one-to-many into `reporting_layer[Received_Date]`, with an inactive
relationship to `Closed_Date` for closure-based analysis via `USERELATIONSHIP`.

`dq_exceptions` is intentionally left unrelated to `reporting_layer`. Its grain is the
exception, not the appeal, and some exceptions are source-level rather than record-level.
Joining them would double-count. Drill-through from an appeal uses a measure filter instead.

## Measures

```DAX
-- Certified KPI values, read straight from the certification table so the
-- dashboard cannot silently disagree with the pipeline
Certified Appeal Volume =
CALCULATE ( SUM ( kpi_certification[Certified_Value] ),
            kpi_certification[KPI_ID] = "KPI-01" )

Certified Open Backlog =
CALCULATE ( SUM ( kpi_certification[Certified_Value] ),
            kpi_certification[KPI_ID] = "KPI-02" )

Certified Median Turnaround =
CALCULATE ( SUM ( kpi_certification[Certified_Value] ),
            kpi_certification[KPI_ID] = "KPI-03" )

Certified SLA Compliance =
CALCULATE ( SUM ( kpi_certification[Certified_Value] ),
            kpi_certification[KPI_ID] = "KPI-04" )

-- Recalculated from the reporting layer, used only on the trend page
Appeal Volume = COUNTROWS ( reporting_layer )

Open Backlog =
CALCULATE ( COUNTROWS ( reporting_layer ),
            NOT reporting_layer[Status] IN { "Closed", "Cancelled" } )

Closed Appeals =
CALCULATE ( COUNTROWS ( reporting_layer ), reporting_layer[Status] = "Closed" )

Median Turnaround Days =
CALCULATE ( MEDIANX ( reporting_layer, reporting_layer[Turnaround_Days] ),
            reporting_layer[Status] = "Closed" )

SLA Compliance % =
DIVIDE (
    CALCULATE ( COUNTROWS ( reporting_layer ), reporting_layer[SLA_Met] = "Yes" ),
    [Closed Appeals]
) * 100

First Pass Routing Accuracy % =
DIVIDE (
    CALCULATE ( COUNTROWS ( reporting_layer ), reporting_layer[Reassignment_Count] = 0 ),
    CALCULATE ( COUNTROWS ( reporting_layer ),
                NOT ISBLANK ( reporting_layer[Reassignment_Count] ) )
) * 100

Rework Rate % =
DIVIDE (
    CALCULATE ( COUNTROWS ( reporting_layer ), reporting_layer[Rework_Flag] = "Yes" ),
    CALCULATE ( COUNTROWS ( reporting_layer ),
                NOT ISBLANK ( reporting_layer[Rework_Flag] ) )
) * 100

-- Governance measures
KPIs Certified =
CALCULATE ( COUNTROWS ( kpi_certification ), kpi_certification[Certified] = "Yes" )

KPIs Total = COUNTROWS ( kpi_certification )

Certification Rate % = DIVIDE ( [KPIs Certified], [KPIs Total] ) * 100

Pairs Tested =
CALCULATE ( COUNTROWS ( kpi_reconciliation ),
            kpi_reconciliation[Within_Tolerance] <> "N/A" )

Pairs Within Tolerance =
CALCULATE ( COUNTROWS ( kpi_reconciliation ),
            kpi_reconciliation[Within_Tolerance] = "Yes" )

Reconciliation Rate % = DIVIDE ( [Pairs Within Tolerance], [Pairs Tested] ) * 100

Absolute Variance = SUMX ( kpi_reconciliation, ABS ( kpi_reconciliation[Variance] ) )

Open Exceptions =
CALCULATE ( COUNTROWS ( dq_exceptions ), dq_exceptions[Status] = "Open" )

Critical Exceptions =
CALCULATE ( COUNTROWS ( dq_exceptions ),
            dq_exceptions[Severity] = "Critical",
            dq_exceptions[Status] = "Open" )

Unassigned Exceptions =
CALCULATE ( COUNTROWS ( dq_exceptions ), ISBLANK ( dq_exceptions[Owner] ) )

Avg Days To Resolve =
AVERAGEX (
    FILTER ( dq_exceptions, NOT ISBLANK ( dq_exceptions[Resolution_Date] ) ),
    DATEDIFF ( dq_exceptions[Identified_Date], dq_exceptions[Resolution_Date], DAY )
)

Reporting Layer Completeness % =
DIVIDE (
    CALCULATE ( COUNTROWS ( reporting_layer ),
                NOT ISBLANK ( reporting_layer[Reassignment_Count] ) ),
    COUNTROWS ( reporting_layer )
) * 100

-- Drives the banner. If anything Critical is open, nothing is trustworthy.
Trust Status =
IF ( [Critical Exceptions] > 0,
     "BLOCKED - Critical exception open",
     IF ( [Reconciliation Rate %] = 100, "ALL KPIs RECONCILED",
          "PARTIAL - " & FORMAT ( [Reconciliation Rate %], "0.0" ) & "% reconciled" ) )
```

### Conditional formatting rules

- Certification tiles: green when `Certified = "Yes"`, amber when out of tolerance only, red
  when blocked by a Critical exception.
- Variance column: red when `Within_Tolerance = "No"`, grey when `"N/A"`.
- Severity: Critical dark red, High red, Medium amber, Low grey. Same palette on every page.

## Pages

### Page 1 — KPI Trust Overview

Purpose: the certification board. This is the page that replaces the argument.

- Banner card: `Trust Status`, full width, coloured by state.
- Six KPI tiles, one per catalog KPI: certified value, unit, and a certification chip
  (Certified / Not Certified). Uncertified tiles show the blocking reason underneath. The value
  is always shown — hiding it would just push people back to the old spreadsheets.
- Cards: `Reconciliation Rate %`, `KPIs Certified` out of `KPIs Total`, `Open Exceptions`,
  `Critical Exceptions`.
- Line chart: monthly certified volume and closed count from `reporting_layer`.
- Line chart: monthly `SLA Compliance %` and `Rework Rate %`, dual axis.
- Slicers: month, payer, team, appeal type.

### Page 2 — KPI Catalog

Purpose: end definitional arguments by making the definition visible next to the number.

- Table: KPI_ID, KPI_Name, Business_Definition, Formula, Owner, Authoritative_Source, Unit,
  Tolerance, Certified_Value, Certified, Blocking_Reason. Definition and formula columns set to
  wrap, not truncate.
- Card: count of KPIs with a named owner, out of total.
- Note visual stating the source-of-truth policy per field.

### Page 3 — Data Quality Scorecard

- Cards: records evaluated (6,000), records excluded (0), record-level quality score,
  `Reporting Layer Completeness %`.
- Bar chart: exceptions by severity, sorted Critical → Low.
- Bar chart: exceptions by rule, descending, with severity as the colour.
- Table: field-level completeness — Closed_Date, Reassignment_Count, Rework_Flag, SLA_Met.
- Matrix: extract freshness — source, extract timestamp, age in hours, pass/fail against the
  24-hour rule.
- Callout text box: the record-level score is 100% while the reconciliation rate is 38.5%. Both
  numbers are true and the second one is the one that matters.

### Page 4 — Exception Management

Purpose: a work queue, not a report.

- Cards: `Open Exceptions`, `Critical Exceptions`, `Unassigned Exceptions`,
  `Avg Days To Resolve` (blank in this build, and the blank is the point).
- Matrix: Owner on rows, Severity on columns, exception count in values.
- Table: Exception_ID, Rule_ID, Record_ID, Severity, Description, Owner, Status,
  Identified_Date, Resolution_Date. Sorted Critical first, then by rule.
- Table: appeals present in case management and missing from the workflow tracker (the DQ-02
  population, 65 rows).
- Table: status disagreements, showing both systems' values side by side (the DQ-03
  population, 90 rows).
- Slicers: severity, rule, owner, status.

### Page 5 — Reconciliation Analysis

Purpose: the page that explains the gap.

- Matrix: KPI on rows, Source on columns, Variance in values, conditionally formatted.
- Table: every out-of-tolerance row with Source_Value, Certified_Value, Variance, Tolerance,
  and the documented cause. The cause column is the widest column on the page.
- Bar chart: `Reconciliation Rate %` by source — leadership extract 25%, workflow tracker 40%,
  case management 50%.
- Waterfall or comparison bar: open backlog under all four competing definitions —
  423 certified, 611 case management, 509 tracker, 211 leadership extract — annotated with the
  definitional difference behind each step.
- Card: `Absolute Variance` as a single headline number for the trend over time.

## Refresh and distribution

Daily scheduled refresh at 06:00 local. The certification gate runs in the pipeline, not in
Power BI, so a failed refresh leaves the previous certified values visible with a stale-as-of
timestamp rather than showing blanks. Distribution is a Power BI app; the leadership workbook
is retired once all three legacy dashboards are migrated.

## Accessibility

Severity and certification are never encoded by colour alone — each carries a text label.
Tooltips give the full definition and cause text. Tab order follows reading order on every page.
