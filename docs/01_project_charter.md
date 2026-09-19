# Project Charter — KPI Trust Ledger

**Project name:** KPI Trust Ledger
**Organization:** Lone Star Care Operations (fictional)
**Prepared by:** Business analyst / reporting analyst
**Date:** 2026-03-09
**Status:** Prototype, portfolio build

## Problem statement

Three dashboards report three different open-backlog figures and two different turnaround
values for the same population. Leadership has stopped trusting all of them. There is no
written KPI definition, no stated source of truth, no automated quality checking, and no
record of which extract is current. Reporting credibility, not data volume, is the constraint.

## Goal

Build a governed reporting framework that documents KPI logic, detects data issues,
reconciles source values against a certified reporting layer, and withholds certification
from any number that cannot be defended.

## Objectives

1. Publish a KPI catalog with definition, formula, owner, source, unit, and tolerance.
2. Conform three inconsistent extracts into one reporting layer under a written
   source-of-truth policy.
3. Automate fifteen data-quality rules with severity and ownership.
4. Reconcile every KPI against every source and document the cause of each variance.
5. Gate certification on Critical exceptions and extract freshness.

## Users

| User | Primary use |
|---|---|
| Operations leaders | Certified KPI values, and clear notice when a KPI is not certified |
| Reporting analysts | Definitions and formulas to build against |
| Business analysts | Traceability from KPI to field to rule |
| Data owners and stewards | Exception queue with severity and ownership |
| Compliance | Evidence of validation before distribution |
| IT / data engineering | Refresh monitoring and freshness alerting |

## Success measures

| Measure | Baseline (modeled) | Target direction |
|---|---|---|
| KPI reconciliation rate | 38.5% | Increase toward 100% |
| KPIs certified | 2 of 6 | Increase |
| Open Critical exceptions | 1 | Zero before distribution |
| Reporting-layer completeness | 92.95% on Closed_Date, 98.92% on tracker fields | Increase |
| Refresh success and freshness | Leadership extract 4 days stale | Under 24 hours |
| Time to resolve exceptions | Not measurable, nothing is assigned | Establish, then reduce |

## Scope

**In scope:** six appeals KPIs; the three named source extracts; conformance, data-quality
rules, reconciliation, certification; the period 2026-01-01 to 2026-06-30.

**Out of scope:** orchestration tooling selection, master data management programme, access
control and security, anything downstream of the certified layer, staffing analysis.

## Assumptions

- Case management is authoritative for dates, status, payer, appeal type, and SLA target.
- The workflow tracker is authoritative for reassignment count and rework flag, because no
  other system captures them.
- The leadership extract is a consumer, not a source.
- Tolerances: counts exact, percentages within 1 percentage point, time within 0.25 days.
- No production data is used.

## Constraints

- Cannot change the source systems; conformance must happen in the reporting layer.
- Definitions must be agreed by the named owner before a KPI can be certified.
- Everything must run without a server database.

## Risks

| Risk | Mitigation |
|---|---|
| Uncertified KPIs published anyway because leadership wants a number | Certification state shown on the same visual as the value; blocking reason displayed |
| Tolerances set so loose that reconciliation always passes | Tolerances documented in the catalog and reviewed with the data owner |
| Exception log becomes a dumping ground | Every exception carries a named owner; unassigned exceptions are themselves reported |
| Conformance logic becomes a second source of truth nobody understands | Source-of-truth policy documented per field; conformance code is a single readable module |

## Deliverables

Charter, business requirements, KPI catalog, data dictionary, three synthetic source extracts,
conformance and reconciliation pipeline, fifteen documented quality rules, exception log,
reconciliation output with documented causes, certification table, governance process maps,
dashboard specification, UAT test cases, executive summary.
