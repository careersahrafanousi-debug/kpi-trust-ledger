# As-Is Reporting Process — Lone Star Care Operations

How a KPI reaches leadership today.

```mermaid
flowchart TD
    A[Case management system] --> B[Analyst exports CSV manually]
    C[Team workflow tracker in a spreadsheet] --> D[Analyst exports a second CSV]
    B --> E[Analyst joins the two files in a workbook]
    D --> E
    E --> F{Do the counts match last month?}
    F -->|No| G[Analyst adjusts figures by hand]:::pain
    F -->|Yes| H[Paste into the leadership workbook]
    G --> H
    H --> I[Monthly leadership extract emailed]:::pain
    I --> J[Three separate dashboards read three different files]:::pain
    J --> K[Leadership sees conflicting backlog numbers]:::pain
    K --> L{Which number is right?}
    L --> M[Meeting spent debating the number, not the operation]:::pain
    M --> N[Decision deferred]:::pain

    classDef pain fill:#ffe0e0,stroke:#cc0000,color:#000
```

## Where it breaks

| # | Breakdown | Evidence in the data |
|---|---|---|
| 1 | No written definition of "open" | Backlog ranges from 211 to 611 depending on the source |
| 2 | Manual hand-adjustment of figures | 40 turnaround dates in the leadership extract were reduced by 1-3 days |
| 3 | Free-text status in the tracker | Seven spellings for four real states; 90 disagreements with case management |
| 4 | No refresh monitoring | Leadership extract was 4 days stale and nobody knew |
| 5 | Unmanaged integration gap | 65 appeals exist in case management and not in the tracker |
| 6 | Reopened cases written as new rows | 58 duplicate appeal IDs inflate volume |
| 7 | No quality checking before distribution | Zero rules ran before this project |
| 8 | No owner for a disagreement | 273 exceptions, none assigned, none resolved |
| 9 | Three dashboards, three source files | No certified layer for any of them to read |

## Consequence

The reconciliation rate across the three sources is 38.5%. Four of six KPIs cannot be
certified. The operational data itself is not corrupt — zero records fail a Critical
record-level rule — which is why the problem has survived so long. It looks like a data
problem and it is a governance problem.
