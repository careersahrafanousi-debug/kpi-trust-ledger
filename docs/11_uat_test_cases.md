# UAT Test Cases — KPI Trust Ledger

Tested against the seed-77 dataset. Reproduce by running the three scripts in order.

| ID | Story | Test | Steps | Expected | Result |
|---|---|---|---|---|---|
| UAT-01 | US-01 | Certification state shown per KPI | Open query 1 | 6 rows; KPI-05 and KPI-06 Certified = Yes; the other four No with a blocking reason | Pass |
| UAT-02 | US-02 | KPI catalog complete | Open query 14 | 6 KPIs, each with definition, formula, owner, authoritative source, tolerance, and certification state | Pass |
| UAT-03 | US-03 | Every variance has a cause | Open query 3 | 8 out-of-tolerance rows, every Note non-empty | Pass |
| UAT-04 | US-04 | Exception queue by rule and owner | Open query 6 | DQ-03 90, DQ-02 65, DQ-13 59, DQ-01 58, DQ-15 1; each with an owner | Pass |
| UAT-05 | US-05 | Backlog under competing definitions | Open query 4 | 423 certified, 611 case management, 509 tracker, 211 leadership | Pass |
| UAT-06 | US-06 | Critical exception blocks certification | Open query 5, then query 1 | 1 open Critical exception on the leadership extract; no KPI whose authoritative source is affected is certified | Pass |
| UAT-07 | US-07 | Freshness monitored per source | Open query 12 | Case management 2026-06-30 23:50, tracker 2026-06-30 18:15, leadership 2026-06-26 07:00 | Pass |
| UAT-08 | US-08 | Field completeness reported | Open query 7 | Closed_Date 92.95%, Reassignment_Count 98.92%, Rework_Flag 98.92%, SLA_Met 100% | Pass |
| UAT-09 | US-09 | Critical failures excluded and logged | Compare run output to query 5 | 6,000 rows in the reporting layer, 0 records excluded, 1 Critical exception at source level only | Pass |
| UAT-10 | US-10 | Certified KPIs trend monthly | Open query 9 | 6 months; June volume 1,022 with only 669 closed, consistent with cases still in flight at period end | Pass |
| UAT-11 | US-11 | Integration gap listed | Open query 10 | Appeals present in case management and absent from the tracker; matches the 65 DQ-02 exceptions | Pass |
| UAT-12 | US-12 | Status disagreements listed | Open query 11 | Mapped comparison returns the 90 DQ-03 cases | Pass |

## Reconciliation of the pipeline output

| Check | Expected | Actual |
|---|---|---|
| Ground truth rows | 6,000 | 6,000 |
| Case management export rows | 6,000 + 58 duplicated reopened | 6,058 |
| Workflow tracker rows | 6,000 − 65 missing | 5,935 |
| Leadership extract rows | Stale cut-off plus cancelled excluded | 5,743 |
| Reporting layer rows | 6,058 − 58 duplicates − 0 excluded | 6,000 |
| Exceptions | Sum of rule counts | 273 |
| KPI/source pairs tested | 18 possible − 5 unavailable | 13 |
| Pairs within tolerance | 13 − 8 failures | 5 |
| Reconciliation rate | 5 ÷ 13 | 38.5% |

The reporting layer landing exactly on 6,000 is the check that matters: the deduplication
policy removed precisely the rows the generator duplicated, and nothing else.

## Defects raised

**D-01 — Time to resolve is structurally unmeasurable.** Query 13 returns a null
`avg_days_to_resolve` for every severity because no exception has ever been assigned or
resolved. The measure and the field exist; the process does not. Logged as a process gap
rather than a code defect, and called out in the README and the dashboard spec so nobody
mistakes the blank for a rendering bug.

**D-02 — Record-level quality score is misleadingly clean.** The score reads 100% because no
record fails a Critical rule, while only 38.5% of KPI/source pairs reconcile. A single
"data quality score" headline would have hidden the actual problem. Resolved by reporting both
figures side by side with an explanatory note on the scorecard page.

**D-03 — KPI-05 and KPI-06 certify against a single source.** Both are only produced by the
workflow tracker, so "all sources within tolerance" is a weak statement for them — there is
nothing to disagree with. The certification table exposes `Sources_Tested = 1` so the weakness
is visible, but single-source KPIs should arguably carry a distinct certification tier. Open,
deferred.
