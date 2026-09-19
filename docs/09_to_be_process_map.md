# To-Be Reporting Process — KPI Trust Ledger

```mermaid
flowchart TD
    A[Case management system] --> D[Scheduled extract, timestamped]
    B[Workflow tracker with constrained status list]:::ctrl --> D
    D --> E[Freshness check, 24 hour rule]:::ctrl
    E -->|Stale| F[Critical exception raised, certification blocked]:::ctrl
    E -->|Current| G[Conform to reporting layer using the source-of-truth policy]:::ctrl
    G --> H[Run 15 data quality rules]:::ctrl
    H --> I{Critical record failure?}
    I -->|Yes| J[Exclude record, log exception, notify owner]:::ctrl
    I -->|No| K[Load certified reporting layer]
    J --> K
    K --> L[Recalculate every KPI from every capable source]:::ctrl
    L --> M[Compare to certified value against catalog tolerance]:::ctrl
    M --> N{Within tolerance and no Critical exception?}
    N -->|Yes| O[Certify KPI]:::ctrl
    N -->|No| P[Publish as Not Certified with documented cause]:::ctrl
    O --> Q[Single certified dashboard]
    P --> Q
    Q --> R[Leadership review reads certified values only]
    F --> S[Exception queue with owner and due date]:::ctrl
    J --> S
    P --> S
    S --> T[Owner resolves, records resolution date and cause]:::ctrl
    T --> U[Monthly governance review: catalog changes, tolerances, time to resolve]:::ctrl
    U --> A

    classDef ctrl fill:#e0ffe0,stroke:#009900,color:#000
```

## Controls introduced

| Control | Addresses | How it is enforced |
|---|---|---|
| Published KPI catalog | Breakdown 1 | No dashboard tile without a catalog entry |
| Source-of-truth policy per field | Breakdowns 1, 5 | Applied in conformance code, documented in the data dictionary |
| Constrained status value list | Breakdown 3 | Tracker input restricted; DQ-03 monitors residual drift |
| Automated freshness check | Breakdown 4 | DQ-15, Critical on an authoritative source |
| Deduplication policy for reopened cases | Breakdown 6 | DQ-01, first occurrence retained, duplicate logged |
| Fifteen automated rules | Breakdown 7 | Run on every refresh, before publication |
| Certification gate | Breakdowns 1, 4, 7 | Critical exception or out-of-tolerance variance sets Certified to No |
| Exception queue with named owner and due date | Breakdown 8 | Owner on every exception; unassigned exceptions reported |
| Single certified reporting layer | Breakdown 9 | Three dashboards consolidated onto one model |

## What this does not fix

Retiring the manual leadership extract is a decision, not a control. Until someone makes it,
the least reconcilable source continues to exist and the certification gate will keep
reporting it as Not Certified. That is the intended behaviour — the framework surfaces the
decision rather than working around it.

## Implementation sequence

1. Agree and publish the KPI catalog, including the Cancelled and Reopened treatment.
2. Stand up the conformed reporting layer and point one dashboard at it.
3. Turn on the fifteen rules and the exception queue with owners.
4. Add the certification gate and display certification state on every tile.
5. Migrate the remaining two dashboards, then retire the manual extract.
6. Begin reporting time to resolve, and review tolerances quarterly.
