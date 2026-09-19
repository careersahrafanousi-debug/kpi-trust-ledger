# Data Dictionary — KPI Trust Ledger

All data synthetic. Seed 77. Period 2026-01-01 to 2026-06-30. Reporting date 2026-06-30.

## kpi_catalog (6 rows)

| Field | Type | Description |
|---|---|---|
| KPI_ID | text | KPI-01 … KPI-06 |
| KPI_Name | text | Display name used on every dashboard page |
| Business_Definition | text | Plain-language definition agreed with the owner |
| Formula | text | Calculation stated in field names |
| Owner | text | Accountable role |
| Authoritative_Source | text | System that owns the inputs |
| Unit | text | Count, Percent, Days — drives tolerance selection |
| Tolerance | text | Human-readable tolerance statement |

## case_management_export (6,058 rows)

Operational system extract. Closest to truth but not clean.

| Field | Type | Description | Known issue |
|---|---|---|---|
| Appeal_ID | text | `APL-2026-NNNNNN` | Not unique — reopened cases appear twice (58 duplicates) |
| Received_Date | date | Date the appeal was received | Authoritative |
| Closed_Date | date | Closure date, null when open | Authoritative |
| Status | text | Closed / Open / Cancelled / Reopened | Authoritative vocabulary |
| Appeal_Type | text | Clinical, Administrative, Authorization, Pharmacy | |
| Payer_ID | text | FK to dim_payer | |
| Team_ID | text | FK to dim_team | |
| SLA_Target_Days | int | 7, 14, or 30 by appeal type | |
| Source_System | text | Constant `case_management` | |
| Extract_Timestamp | datetime | 2026-06-30 23:50:00 | Within freshness rule |

## workflow_tracker_export (5,935 rows)

Team-maintained tracker. Only source for routing and rework.

| Field | Type | Description | Known issue |
|---|---|---|---|
| Case_Ref | text | Appeal identifier | 65 appeals absent entirely |
| Received_Date | date | **Actually the intake date**, despite the name | Shifts volume between periods; understates turnaround |
| Completion_Date | date | Completion date | Null on 90 rows that were finished but never updated |
| Case_State | text | Free text | `COMPLETE`, `Completed`, `In Progress`, `in progress`, `Withdrawn`, `withdrawn`, `Re-Opened` |
| Type | text | Appeal type, uppercased | Case drift |
| Team | text | FK to dim_team | |
| Reassignment_Count | int | Times reassigned, 0-6 | Authoritative |
| Rework_Flag | text | Yes / No | Authoritative |
| Source_System | text | Constant `workflow_tracker` | |
| Extract_Timestamp | datetime | 2026-06-30 18:15:00 | Within freshness rule |

## leadership_reporting_extract (5,743 rows)

Monthly manual pull. Authoritative for nothing.

| Field | Type | Description | Known issue |
|---|---|---|---|
| AppealID | text | Appeal identifier | Different naming convention |
| ReceivedDate | date | Receipt date | Cut off at 2026-06-26 |
| ClosedDate | date | Closure date | 40 values reduced by 1-3 days by manual workbook edits |
| Status | text | Closed / Open | Reopened collapsed into Closed; Cancelled rows dropped entirely |
| AppealType | text | Appeal type | |
| Payer | text | Payer code | 55 rows respelled `Pay 02` instead of `PAY-02` |
| SLATarget | int | SLA days | |
| Source_System | text | Constant `leadership_extract` | |
| Extract_Timestamp | datetime | 2026-06-26 07:00:00 | 4 days stale — raises a Critical exception |

## reporting_layer (6,000 rows) — certified output

Case management conformed and deduplicated, enriched with tracker routing fields under the
source-of-truth policy.

| Field | Type | Description |
|---|---|---|
| Appeal_ID | text | Unique after dedupe |
| Received_Date | date | From case management |
| Closed_Date | date | From case management |
| Status | text | Mapped to Closed / Open / Cancelled / Reopened |
| Appeal_Type, Payer_ID, Team_ID, SLA_Target_Days | | From case management |
| Reassignment_Count | int | From workflow tracker; null where the appeal is missing there |
| Rework_Flag | text | From workflow tracker; null where missing |
| Case_State, Completion_Date | | Tracker values retained for audit of DQ-03 disagreements |
| Turnaround_Days | int | `Closed_Date - Received_Date` |
| SLA_Met | text | Yes / No, closed appeals only |

Completeness on the current run: Closed_Date 92.95%, Reassignment_Count 98.92%,
Rework_Flag 98.92%, SLA_Met 100% of closed appeals.

## dq_exceptions (273 rows)

| Field | Type | Description |
|---|---|---|
| Exception_ID | text | `EX-NNNNN` |
| Rule_ID | text | DQ-01 … DQ-15 |
| Record_ID | text | Appeal ID, or a source name for source-level rules |
| Severity | text | Critical, High, Medium, Low |
| Description | text | What failed and what the pipeline did about it |
| Owner | text | Accountable role |
| Status | text | Open / Resolved |
| Identified_Date | date | Run date |
| Resolution_Date | date | Null on every row in this build — see README finding 6 |

## kpi_reconciliation (18 rows: 6 KPIs x 3 sources)

| Field | Type | Description |
|---|---|---|
| KPI_ID, KPI_Name | text | From the catalog |
| Source | text | Which extract produced the value |
| Source_Value | float | KPI recalculated from that source alone; null if unavailable |
| Certified_Value | float | Same KPI from the reporting layer |
| Variance | float | `Source_Value - Certified_Value` |
| Unit, Tolerance | | From the catalog |
| Within_Tolerance | text | Yes / No / N/A |
| Note | text | Documented cause of the variance |

Thirteen of the eighteen pairs are testable; five are N/A because the source cannot produce
that KPI at all.

## kpi_certification (6 rows)

| Field | Type | Description |
|---|---|---|
| KPI_ID, KPI_Name, Certified_Value, Unit | | |
| Sources_Tested | int | Sources able to produce this KPI |
| Sources_Within_Tolerance | int | How many agreed |
| Certified | text | Yes / No |
| Blocking_Reason | text | Why not, when No |

## Reference tables

`dim_payer` — PAY-01 Trinity Health Plan, PAY-02 Brazos Valley Benefits, PAY-03 Statewide
Medicaid MCO, PAY-04 Silver Ridge Advantage, PAY-05 Cottonwood Mutual.

`dim_team` — TM-01 through TM-07, Appeals Team A through G.
