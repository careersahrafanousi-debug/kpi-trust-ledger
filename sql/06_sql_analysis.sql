-- KPI Trust Ledger - analysis and governance queries
-- Lone Star Care Operations (fictional org, fully synthetic data)
-- SQLite dialect.

--------------------------------------------------------------------
-- 1. The certification board. This is the page leadership sees first.
--------------------------------------------------------------------
SELECT c.KPI_ID,
       c.KPI_Name,
       c.Certified_Value,
       c.Unit,
       c.Sources_Tested,
       c.Sources_Within_Tolerance,
       c.Certified,
       c.Blocking_Reason
FROM kpi_certification c
ORDER BY c.KPI_ID;


--------------------------------------------------------------------
-- 2. Reconciliation rate overall and by source
--------------------------------------------------------------------
SELECT Source,
       COUNT(*)                                                         AS pairs_tested,
       SUM(CASE WHEN Within_Tolerance = 'Yes' THEN 1 ELSE 0 END)        AS within_tolerance,
       ROUND(100.0 * SUM(CASE WHEN Within_Tolerance = 'Yes' THEN 1 ELSE 0 END)
             / COUNT(*), 1)                                             AS reconciliation_rate_pct
FROM kpi_reconciliation
WHERE Within_Tolerance <> 'N/A'
GROUP BY Source
ORDER BY reconciliation_rate_pct;


--------------------------------------------------------------------
-- 3. Every variance with its documented cause
--------------------------------------------------------------------
SELECT KPI_ID, KPI_Name, Source, Source_Value, Certified_Value,
       Variance, Unit, Tolerance, Note
FROM kpi_reconciliation
WHERE Within_Tolerance = 'No'
ORDER BY KPI_ID, ABS(Variance) DESC;


--------------------------------------------------------------------
-- 4. Backlog: the same question answered four different ways
-- This single result set is the reason the project exists.
--------------------------------------------------------------------
SELECT 'Certified reporting layer' AS definition,
       COUNT(*) AS open_backlog
FROM reporting_layer
WHERE Status NOT IN ('Closed', 'Cancelled')
UNION ALL
SELECT 'Case management: anything not Closed',
       COUNT(*)
FROM case_management_export
WHERE LOWER(Status) <> 'closed'
UNION ALL
SELECT 'Workflow tracker: not complete',
       COUNT(*)
FROM workflow_tracker_export
WHERE LOWER(Case_State) NOT IN ('complete', 'completed', 'withdrawn')
UNION ALL
SELECT 'Leadership extract: not Closed, cancelled already dropped',
       COUNT(*)
FROM leadership_reporting_extract
WHERE Status <> 'Closed';


--------------------------------------------------------------------
-- 5. Data quality exceptions by severity
--------------------------------------------------------------------
SELECT Severity,
       COUNT(*)                                                  AS exceptions,
       COUNT(DISTINCT Rule_ID)                                   AS rules_triggered,
       SUM(CASE WHEN Status = 'Open' THEN 1 ELSE 0 END)          AS still_open
FROM dq_exceptions
GROUP BY Severity
ORDER BY CASE Severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                       WHEN 'Medium' THEN 3 ELSE 4 END;


--------------------------------------------------------------------
-- 6. Exceptions by rule, with the owner who has to clear them
--------------------------------------------------------------------
SELECT Rule_ID, Severity, Owner, COUNT(*) AS exceptions
FROM dq_exceptions
GROUP BY Rule_ID, Severity, Owner
ORDER BY exceptions DESC;


--------------------------------------------------------------------
-- 7. Completeness of the reporting layer, field by field
--------------------------------------------------------------------
SELECT 'Closed_Date'        AS field,
       ROUND(100.0 * SUM(CASE WHEN Closed_Date IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 2) AS populated_pct
FROM reporting_layer
UNION ALL
SELECT 'Reassignment_Count',
       ROUND(100.0 * SUM(CASE WHEN Reassignment_Count IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 2)
FROM reporting_layer
UNION ALL
SELECT 'Rework_Flag',
       ROUND(100.0 * SUM(CASE WHEN Rework_Flag IS NOT NULL THEN 1 ELSE 0 END)
             / COUNT(*), 2)
FROM reporting_layer
UNION ALL
SELECT 'SLA_Met (closed only)',
       ROUND(100.0 * SUM(CASE WHEN SLA_Met IS NOT NULL THEN 1 ELSE 0 END)
             / SUM(CASE WHEN Status = 'Closed' THEN 1 ELSE 0 END), 2)
FROM reporting_layer;


--------------------------------------------------------------------
-- 8. Status distribution across the three sources side by side
--------------------------------------------------------------------
SELECT 'case_management' AS source, LOWER(Status) AS state, COUNT(*) AS n
FROM case_management_export GROUP BY 2
UNION ALL
SELECT 'workflow_tracker', LOWER(Case_State), COUNT(*)
FROM workflow_tracker_export GROUP BY 2
UNION ALL
SELECT 'leadership_extract', LOWER(Status), COUNT(*)
FROM leadership_reporting_extract GROUP BY 2
ORDER BY source, n DESC;


--------------------------------------------------------------------
-- 9. Certified KPI values by month, from the reporting layer only
--------------------------------------------------------------------
SELECT strftime('%Y-%m', Received_Date)                                AS month,
       COUNT(*)                                                        AS volume,
       SUM(CASE WHEN Status = 'Closed' THEN 1 ELSE 0 END)              AS closed,
       ROUND(100.0 * SUM(CASE WHEN SLA_Met = 'Yes' THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN Status = 'Closed' THEN 1 ELSE 0 END), 0), 1)
                                                                       AS sla_compliance_pct,
       ROUND(100.0 * SUM(CASE WHEN Rework_Flag = 'Yes' THEN 1 ELSE 0 END)
             / COUNT(*), 1)                                            AS rework_rate_pct
FROM reporting_layer
GROUP BY month
ORDER BY month;


--------------------------------------------------------------------
-- 10. Appeals in case management but absent from the workflow tracker
-- These are the records that silently break any tracker-sourced KPI.
--------------------------------------------------------------------
SELECT c.Appeal_ID, c.Received_Date, c.Status, c.Appeal_Type, c.Team_ID
FROM case_management_export c
LEFT JOIN workflow_tracker_export w ON w.Case_Ref = c.Appeal_ID
WHERE w.Case_Ref IS NULL
ORDER BY c.Received_Date
LIMIT 50;


--------------------------------------------------------------------
-- 11. Status disagreements between the two operational systems
--------------------------------------------------------------------
SELECT c.Appeal_ID,
       c.Status       AS case_management_status,
       w.Case_State   AS tracker_status,
       c.Closed_Date,
       w.Completion_Date
FROM case_management_export c
JOIN workflow_tracker_export w ON w.Case_Ref = c.Appeal_ID
WHERE LOWER(c.Status) <> LOWER(
          CASE WHEN LOWER(w.Case_State) IN ('complete', 'completed') THEN 'closed'
               WHEN LOWER(w.Case_State) IN ('in progress', 'in-progress') THEN 'open'
               WHEN LOWER(w.Case_State) IN ('withdrawn') THEN 'cancelled'
               WHEN LOWER(w.Case_State) IN ('re-opened') THEN 'reopened'
               ELSE LOWER(w.Case_State) END)
ORDER BY c.Appeal_ID
LIMIT 50;


--------------------------------------------------------------------
-- 12. Extract freshness check
--------------------------------------------------------------------
SELECT 'case_management' AS source, MAX(Extract_Timestamp) AS extract_time
FROM case_management_export
UNION ALL
SELECT 'workflow_tracker', MAX(Extract_Timestamp) FROM workflow_tracker_export
UNION ALL
SELECT 'leadership_extract', MAX(Extract_Timestamp) FROM leadership_reporting_extract;


--------------------------------------------------------------------
-- 13. Time to resolve exceptions (empty on first run by design -
-- every exception starts Open, which is itself the finding)
--------------------------------------------------------------------
SELECT Severity,
       COUNT(*)                                                     AS exceptions,
       SUM(CASE WHEN Resolution_Date IS NULL THEN 1 ELSE 0 END)     AS unresolved,
       ROUND(AVG(CASE WHEN Resolution_Date IS NOT NULL
                      THEN julianday(Resolution_Date) - julianday(Identified_Date) END), 1)
                                                                    AS avg_days_to_resolve
FROM dq_exceptions
GROUP BY Severity;


--------------------------------------------------------------------
-- 14. KPI catalog, joined to its certification state - the ledger itself
--------------------------------------------------------------------
SELECT k.KPI_ID, k.KPI_Name, k.Business_Definition, k.Formula,
       k.Owner, k.Authoritative_Source, k.Tolerance,
       c.Certified_Value, c.Certified, c.Blocking_Reason
FROM kpi_catalog k
JOIN kpi_certification c ON c.KPI_ID = k.KPI_ID
ORDER BY k.KPI_ID;
