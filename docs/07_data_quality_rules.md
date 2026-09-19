# Data Quality Rules — KPI Trust Ledger

Fifteen rules, implemented in `src/reconcile.py`. Critical failures either exclude a record
from the reporting layer or block certification. Nothing is silently corrected.

Severity meaning:

| Severity | Effect |
|---|---|
| Critical | Record excluded from the reporting layer, or certification blocked |
| High | Record retained, conformance policy applied, exception logged for the owner |
| Medium | Record retained, flagged for review |
| Low | Logged for monitoring only |

## Rules

| ID | Rule | Severity | Action | Owner | Count this run |
|---|---|---|---|---|---|
| DQ-01 | Appeal_ID must be unique in the reporting layer | High | First occurrence retained, duplicate logged | Data Steward | 58 |
| DQ-02 | Every reporting-layer appeal must exist in the workflow tracker | High | Routing and rework left null, logged | Data Steward | 65 |
| DQ-03 | Status must agree between case management and the tracker | High | Case management wins per policy, logged | Appeals Ops Manager | 90 |
| DQ-04 | Closed appeals must have a Closed_Date | Critical | Record excluded | Appeals Ops Manager | 0 |
| DQ-05 | Open appeals must not have a Closed_Date | High | Logged | Appeals Ops Manager | 0 |
| DQ-06 | Closed_Date must be on or after Received_Date | Critical | Record excluded | Data Steward | 0 |
| DQ-07 | SLA_Target_Days must be 7, 14, or 30 | Medium | Logged | Quality Lead | 0 |
| DQ-08 | Payer_ID must exist in dim_payer | High | Logged | Data Steward | 0 |
| DQ-09 | Team_ID must exist in dim_team | High | Logged | Data Steward | 0 |
| DQ-10 | Status must map to an approved value | Critical | Record excluded | Appeals Ops Manager | 0 |
| DQ-11 | Appeal_Type must be in the approved list | Medium | Logged | Appeals Ops Manager | 0 |
| DQ-12 | Reassignment_Count must be between 0 and 6 | Low | Logged | Appeals Ops Manager | 0 |
| DQ-13 | Rework_Flag must be populated for closed appeals | Medium | Logged | Quality Lead | 59 |
| DQ-14 | Turnaround must not be negative | Critical | Record excluded | Data Steward | 0 |
| DQ-15 | Each extract must be less than 24 hours old | High, Critical on a KPI's authoritative source | Certification blocked | IT / Data Engineering | 1 |

**Total: 273 exceptions — 1 Critical, 213 High, 59 Medium, 0 Low. 0 records excluded.**

## Reading the zero counts

Several rules returned zero on this run. That is the correct result, not dead code: DQ-04,
DQ-06, DQ-10, and DQ-14 are the rules that would catch a source change or a broken extract,
and their value is that they run every time. A rule you only write after the incident is not a
control.

The rules that did fire are all definitional or integration problems, which matches the
project's premise: the data is not corrupt, the governance is missing.

## Data Quality Score

```
Data Quality Score = (Records passing all rules / Records evaluated) x 100
```

Because 0 records were excluded and 6,000 reached the reporting layer, the record-level score
is 100%. That number on its own is misleading, so this project reports the reconciliation rate
alongside it:

| Measure | Value |
|---|---|
| Records evaluated | 6,000 |
| Records excluded | 0 |
| Record-level Data Quality Score | 100% |
| Record-level exceptions logged | 272, affecting 212 distinct appeals |
| **KPI Reconciliation Rate** | **38.5%** |
| KPIs certified | 2 of 6 |

A clean record-level score with a 38.5% reconciliation rate is exactly the situation that makes
leadership distrust reporting: the data is fine, the definitions are not.

## Rules deliberately not implemented

- Statistical outlier detection on turnaround. Tempting, but an outlier is not an error, and
  flagging one as an exception would teach owners to ignore the queue.
- Automatic correction of the 40 manually edited leadership dates. The pipeline cannot know the
  original value. Retiring the manual extract is the fix, not imputation.
- Payer spelling normalization in the leadership extract. Fixing it in the reporting layer would
  hide the fact that a governed source is being hand-edited.
