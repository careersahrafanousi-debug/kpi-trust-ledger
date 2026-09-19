# Executive Summary — KPI Trust Ledger

**Organization:** Lone Star Care Operations (fictional)
**Period analyzed:** 2026-01-01 to 2026-06-30
**Population:** 6,000 appeals across three source systems
**Data:** Fully synthetic

## The question

Three dashboards report three different open-backlog figures. Leadership asked which one is
right. The answer is that all three are arithmetically correct and none is defensible, because
nobody had written down what "open" means or which system owns the answer.

## What we found

**Open backlog, four ways, same population, same day:**

| Definition | Count |
|---|---|
| Certified reporting layer, excludes Cancelled | 423 |
| Case management, anything not Closed | 611 |
| Workflow tracker, anything not Complete | 509 |
| Leadership extract, Cancelled already dropped | 211 |

**Only 2 of 6 KPIs can be certified.** Reconciliation rate across 13 testable KPI/source
pairs is 38.5%.

| KPI | Certified value | Certified |
|---|---|---|
| Appeal Volume | 6,000 | No — all three sources disagree |
| Open Backlog | 423 | No — all three sources disagree |
| Median Turnaround | 8 days | No |
| SLA Compliance | 68.7% | No |
| First-Pass Routing Accuracy | 73.73% | Yes |
| Rework Rate | 14.38% | Yes |

**The source leadership reads is the least reliable one.** The manual leadership extract
reconciles on 25% of its KPIs, is four days stale, silently drops cancelled cases, and carries
40 turnaround dates that were edited by hand in the workbook.

**The data is not broken; the governance is.** Zero records fail a Critical record-level
quality rule. The record-level quality score is 100%. Every variance in the ledger traces to a
definition, a refresh schedule, or a manual edit — not to corrupt data. That is why the problem
survived this long: it does not look like anything is wrong.

**The biggest single gap is one unmade decision.** The 212-case backlog difference between the
leadership extract and the certified layer is entirely about whether Cancelled and Reopened
cases count as open. No amount of engineering fixes it. Someone has to decide, in writing.

**Nothing is owned.** All 273 exceptions are open with no resolution date, because no owner has
ever been assigned one. Time to resolve cannot currently be measured at all.

## Recommendations

1. **Publish the KPI catalog and require a catalog entry before any tile goes on a leadership
   dashboard.** Six definitions, six named owners.
2. **Decide the Cancelled and Reopened treatment and write it down.** Single highest-value
   action in this report.
3. **Adopt the source-of-truth policy per field.** Case management owns dates and status; the
   tracker owns routing and rework; the leadership workbook owns nothing.
4. **Constrain status entry in the tracker to an approved value list.** Removes the cause of
   90 disagreements.
5. **Certify or label.** Publish uncertified KPIs marked uncertified with the blocking reason,
   rather than quietly publishing them as fact.
6. **Assign every exception an owner and a due date,** then start reporting time to resolve.
7. **Retire the manual leadership extract** once the three dashboards read the certified layer.

## Expected impact

Framed as modeled opportunity, subject to validation with the operational owners:

- Reconciliation rate moves from 38.5% toward full agreement as definitions are settled;
  the volume and backlog KPIs are the two that would resolve first and fastest, since their
  variances are definitional rather than technical.
- Time currently spent in leadership meetings reconciling numbers instead of discussing
  operations is recoverable, but this project does not attempt to quantify it. Any figure
  would be invented.
- No cost savings are claimed. The deliverable here is defensibility, and the honest measure
  of success is the certification rate, not a dollar amount.

## Limitations

Synthetic data with inconsistencies introduced deliberately. Tolerances were set by the analyst
rather than negotiated with data owners. Exception resolution workflow is specified but not
implemented, so time-to-resolve is unmeasurable in this build — documented as defect D-01
rather than hidden. Two of the six KPIs are produced by only one source, so their certification
is weaker than it appears; see defect D-03.
