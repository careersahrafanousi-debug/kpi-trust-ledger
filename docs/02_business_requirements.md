# Business Requirements — KPI Trust Ledger

## User stories

**US-01** As an operations leader, I want each KPI shown with its certification state so that
I know which numbers I can quote externally.
*Acceptance:* every KPI tile displays Certified or Not Certified plus the blocking reason;
uncertified KPIs are visually distinct; the value is still shown rather than hidden.

**US-02** As a reporting analyst, I want a published KPI catalog with definition, formula,
owner, source, and tolerance so that I build to an agreed definition.
*Acceptance:* all six KPIs present; formula stated in terms of actual field names; owner is a
role, not a person's initials.

**US-03** As a business analyst, I want every variance to carry a documented cause so that
discussions move from "the numbers don't match" to a decision.
*Acceptance:* every row where `Within_Tolerance = 'No'` has a non-empty cause; undocumented
variances read "assigned for investigation" rather than being left blank.

**US-04** As a data steward, I want an exception queue with severity and owner so that issues
can be worked and closed.
*Acceptance:* exceptions grouped by rule, severity, and owner; open count visible;
unassigned exceptions are highlighted.

**US-05** As an operations leader, I want to see backlog calculated under each competing
definition side by side so that the discrepancy is explained once and settled.
*Acceptance:* four definitions displayed with their counts and the definitional difference
stated in words.

**US-06** As a compliance lead, I want certification blocked when a Critical exception is open
so that unvalidated figures cannot reach leadership.
*Acceptance:* a Critical exception on a KPI's authoritative source sets Certified to No
regardless of variance; the blocking reason names the exception.

**US-07** As IT, I want extract freshness monitored against a 24-hour rule so that stale data
is caught before it is reported.
*Acceptance:* extract timestamp per source; age in hours; a Critical exception raised beyond
24 hours.

**US-08** As a quality lead, I want completeness measured field by field on the reporting layer
so that I know which KPIs rest on sparse data.
*Acceptance:* populated percentage per key field; closed-only fields use the closed
denominator.

**US-09** As an analyst, I want records failing Critical record-level rules excluded from the
reporting layer and logged so that KPIs are not computed on impossible data.
*Acceptance:* excluded count reconciles to rows in minus rows reported; each exclusion has an
exception row.

**US-10** As an operations leader, I want certified KPIs trended monthly so that I can review
direction, not just a point value.
*Acceptance:* monthly grain on received date; only reporting-layer values used.

**US-11** As a data steward, I want a list of appeals present in one system and absent from the
other so that integration gaps are visible.
*Acceptance:* anti-join result exposed as a table with received date and status.

**US-12** As a quality lead, I want status disagreements between the two operational systems
listed case by case so that the vocabulary problem is quantified rather than debated.
*Acceptance:* mapped comparison, not raw string comparison; 90 rows expected on the current
dataset.

## Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | KPI catalog stored as data and joined to reporting output | Must |
| FR-02 | Source-of-truth policy applied per field during conformance | Must |
| FR-03 | Fifteen quality rules executed on every run with severity and owner | Must |
| FR-04 | Critical record-level failures excluded from the reporting layer and logged | Must |
| FR-05 | Each KPI recalculated independently from every source that can produce it | Must |
| FR-06 | Variance compared against a per-unit tolerance from the catalog | Must |
| FR-07 | Certification withheld on Critical exceptions or out-of-tolerance variance | Must |
| FR-08 | Documented cause attached to every out-of-tolerance variance | Must |
| FR-09 | Extract freshness evaluated per source against a 24-hour rule | Must |
| FR-10 | Exception records support owner, status, and resolution date | Should |
| FR-11 | Time to resolve reported by severity | Should (blocked until FR-10 is used) |
| FR-12 | Tolerances configurable in the catalog without code change | Should |

## Non-functional requirements

- Pipeline runs end to end in under 60 seconds.
- No silent data correction anywhere; every change is either policy-driven conformance or a
  logged exception.
- The ground-truth file is never read by the pipeline.
- Fixed seed for reproducibility.

## Traceability

| Story | Requirements | SQL query | Dashboard page | UAT |
|---|---|---|---|---|
| US-01 | FR-07 | 1 | KPI Trust Overview | UAT-01 |
| US-02 | FR-01 | 14 | KPI Catalog | UAT-02 |
| US-03 | FR-08 | 3 | Reconciliation Analysis | UAT-03 |
| US-04 | FR-03, FR-10 | 6 | Exception Management | UAT-04 |
| US-05 | FR-02 | 4 | Reconciliation Analysis | UAT-05 |
| US-06 | FR-07, FR-09 | 1, 12 | KPI Trust Overview | UAT-06 |
| US-07 | FR-09 | 12 | Data Quality Scorecard | UAT-07 |
| US-08 | FR-03 | 7 | Data Quality Scorecard | UAT-08 |
| US-09 | FR-04 | 5 | Data Quality Scorecard | UAT-09 |
| US-10 | FR-01 | 9 | KPI Trust Overview | UAT-10 |
| US-11 | FR-02 | 10 | Exception Management | UAT-11 |
| US-12 | FR-03 | 11 | Exception Management | UAT-12 |
