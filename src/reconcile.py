"""
The core of the KPI Trust Ledger.

1. Harmonizes the three extracts into one conformed reporting layer using the
   documented definitions (source-of-truth policy).
2. Runs 15 data-quality rules and writes dq_exceptions.csv.
3. Calculates each of the six KPIs from every source, compares them against the
   certified reporting-layer value, and decides pass/fail against tolerance.
4. Refuses to certify any KPI with an open Critical exception.

Run after generate_sources.py:  python src/reconcile.py
"""

import os
from datetime import date

import numpy as np
import pandas as pd

RAW = os.path.join("data", "raw")
CLEAN = os.path.join("data", "clean")
REPORT_DATE = pd.Timestamp("2026-06-30")

# source-of-truth policy: which system owns which field
SOURCE_OF_TRUTH = {
    "Received_Date": "case_management",
    "Closed_Date": "case_management",
    "Status": "case_management",
    "Appeal_Type": "case_management",
    "Payer_ID": "case_management",
    "SLA_Target_Days": "case_management",
    "Reassignment_Count": "workflow_tracker",
    "Rework_Flag": "workflow_tracker",
}

STATUS_MAP = {
    "closed": "Closed", "complete": "Closed", "completed": "Closed",
    "open": "Open", "in progress": "Open", "in-progress": "Open",
    "cancelled": "Cancelled", "canceled": "Cancelled", "withdrawn": "Cancelled",
    "reopened": "Reopened", "re-opened": "Reopened",
}

TOLERANCE = {"Count": 0.0, "Percent": 1.0, "Days": 0.25}

exceptions = []


def log(rule, record, severity, desc, owner):
    exceptions.append({"Exception_ID": f"EX-{len(exceptions)+1:05d}", "Rule_ID": rule,
                       "Record_ID": record, "Severity": severity, "Description": desc,
                       "Owner": owner, "Status": "Open",
                       "Identified_Date": str(REPORT_DATE.date()), "Resolution_Date": None})


# ----------------------------------------------------------------------
# build the conformed reporting layer
# ----------------------------------------------------------------------
def build_reporting_layer():
    cms = pd.read_csv(os.path.join(RAW, "case_management_export.csv"))
    wft = pd.read_csv(os.path.join(RAW, "workflow_tracker_export.csv"))

    # DQ-01 appeal ID must be unique in the reporting layer
    dupes = cms[cms.duplicated("Appeal_ID", keep="first")]["Appeal_ID"]
    for aid in dupes:
        log("DQ-01", aid, "High",
            "Duplicate Appeal_ID in case management export, typically a reopened case "
            "written as a new row. First occurrence retained.", "Data Steward")
    cms = cms.drop_duplicates("Appeal_ID", keep="first")

    cms["Status"] = cms["Status"].astype(str).str.strip().str.lower().map(STATUS_MAP)
    for c in ["Received_Date", "Closed_Date"]:
        cms[c] = pd.to_datetime(cms[c], errors="coerce")

    wft["Case_State"] = wft["Case_State"].astype(str).str.strip().str.lower().map(STATUS_MAP)
    wft["Completion_Date"] = pd.to_datetime(wft["Completion_Date"], errors="coerce")

    df = cms.merge(
        wft[["Case_Ref", "Reassignment_Count", "Rework_Flag", "Case_State", "Completion_Date"]],
        left_on="Appeal_ID", right_on="Case_Ref", how="left")

    # DQ-02 every reporting-layer record must exist in the workflow tracker
    for aid in df.loc[df["Case_Ref"].isna(), "Appeal_ID"]:
        log("DQ-02", aid, "High",
            "Appeal present in case management but missing from workflow tracker; "
            "routing and rework fields cannot be populated.", "Data Steward")

    # DQ-03 status must agree between systems
    mismatch = df[df["Case_State"].notna() & (df["Case_State"] != df["Status"])]
    for aid in mismatch["Appeal_ID"]:
        log("DQ-03", aid, "High",
            "Status disagrees between case management and workflow tracker. Case "
            "management is authoritative per the source-of-truth policy.", "Appeals Ops Manager")

    # DQ-04 closed appeals must have a closed date
    for aid in df[(df["Status"] == "Closed") & (df["Closed_Date"].isna())]["Appeal_ID"]:
        log("DQ-04", aid, "Critical", "Status is Closed but Closed_Date is missing.",
            "Appeals Ops Manager")

    # DQ-05 open appeals must not have a closed date
    for aid in df[(df["Status"] == "Open") & (df["Closed_Date"].notna())]["Appeal_ID"]:
        log("DQ-05", aid, "High", "Status is Open but Closed_Date is populated.",
            "Appeals Ops Manager")

    # DQ-06 received date on or before closed date
    for aid in df[df["Closed_Date"].notna() & (df["Closed_Date"] < df["Received_Date"])]["Appeal_ID"]:
        log("DQ-06", aid, "Critical", "Closed_Date precedes Received_Date.", "Data Steward")

    # DQ-07 SLA target populated and valid
    for aid in df[~df["SLA_Target_Days"].isin([7, 14, 30])]["Appeal_ID"]:
        log("DQ-07", aid, "Medium", "SLA_Target_Days is not one of the approved values.",
            "Quality Lead")

    # DQ-08 payer reference integrity
    payers = set(pd.read_csv(os.path.join(RAW, "dim_payer.csv"))["Payer_ID"])
    for aid in df[~df["Payer_ID"].isin(payers)]["Appeal_ID"]:
        log("DQ-08", aid, "High", "Payer_ID not found in payer reference data.", "Data Steward")

    # DQ-09 team reference integrity
    teams = set(pd.read_csv(os.path.join(RAW, "dim_team.csv"))["Team_ID"])
    for aid in df[~df["Team_ID"].isin(teams)]["Appeal_ID"]:
        log("DQ-09", aid, "High", "Team_ID not found in team reference data.", "Data Steward")

    # DQ-10 status must map to an approved value
    for aid in df[df["Status"].isna()]["Appeal_ID"]:
        log("DQ-10", aid, "Critical", "Status value could not be mapped to the approved list.",
            "Appeals Ops Manager")

    # DQ-11 appeal type must be an approved value
    valid_types = {"Clinical", "Administrative", "Authorization", "Pharmacy"}
    for aid in df[~df["Appeal_Type"].isin(valid_types)]["Appeal_ID"]:
        log("DQ-11", aid, "Medium", "Appeal_Type not in the approved list.", "Appeals Ops Manager")

    # DQ-12 reassignment count within range
    bad = df[df["Reassignment_Count"].notna() &
             ((df["Reassignment_Count"] < 0) | (df["Reassignment_Count"] > 6))]
    for aid in bad["Appeal_ID"]:
        log("DQ-12", aid, "Low", "Reassignment_Count outside the expected range 0-6.",
            "Appeals Ops Manager")

    # DQ-13 rework flag populated for closed appeals
    bad = df[(df["Status"] == "Closed") & (df["Rework_Flag"].isna())]
    for aid in bad["Appeal_ID"]:
        log("DQ-13", aid, "Medium", "Rework_Flag missing for a closed appeal.", "Quality Lead")

    # DQ-14 turnaround must not be negative
    tat = (df["Closed_Date"] - df["Received_Date"]).dt.days
    for aid in df.loc[tat < 0, "Appeal_ID"]:
        log("DQ-14", aid, "Critical", "Negative turnaround time.", "Data Steward")

    # DQ-15 extract freshness, one record-level check per source
    for name, ts in [("case_management", cms["Extract_Timestamp"].iloc[0]),
                     ("workflow_tracker", wft["Extract_Timestamp"].iloc[0])]:
        age_h = (REPORT_DATE + pd.Timedelta(hours=23, minutes=59) - pd.Timestamp(ts)).total_seconds() / 3600
        if age_h > 24:
            log("DQ-15", name, "High",
                f"Extract is {age_h:.1f} hours old, exceeding the 24 hour freshness rule.",
                "IT / Data Engineering")

    lre = pd.read_csv(os.path.join(RAW, "leadership_reporting_extract.csv"))
    age_h = (REPORT_DATE + pd.Timedelta(hours=23, minutes=59)
             - pd.Timestamp(lre["Extract_Timestamp"].iloc[0])).total_seconds() / 3600
    if age_h > 24:
        log("DQ-15", "leadership_extract", "Critical",
            f"Leadership extract is {age_h:.0f} hours old ({age_h/24:.1f} days). Any KPI "
            "sourced from it cannot be certified.", "IT / Data Engineering")

    # remove records failing Critical record-level rules
    critical_records = {e["Record_ID"] for e in exceptions
                        if e["Severity"] == "Critical" and str(e["Record_ID"]).startswith("APL-")}
    reporting = df[~df["Appeal_ID"].isin(critical_records)].copy()

    reporting["Turnaround_Days"] = (reporting["Closed_Date"] - reporting["Received_Date"]).dt.days
    closed = reporting["Status"] == "Closed"
    reporting["SLA_Met"] = None
    reporting.loc[closed, "SLA_Met"] = np.where(
        reporting.loc[closed, "Turnaround_Days"] <= reporting.loc[closed, "SLA_Target_Days"],
        "Yes", "No")

    return reporting, critical_records


# ----------------------------------------------------------------------
# KPI calculations
# ----------------------------------------------------------------------
def kpis_from_reporting(df):
    closed = df[df["Status"] == "Closed"]
    return {
        "KPI-01": float(len(df)),
        "KPI-02": float((~df["Status"].isin(["Closed", "Cancelled"])).sum()),
        "KPI-03": float(closed["Turnaround_Days"].median()),
        "KPI-04": round(100.0 * (closed["SLA_Met"] == "Yes").mean(), 2),
        "KPI-05": round(100.0 * (df["Reassignment_Count"] == 0).mean(), 2),
        "KPI-06": round(100.0 * (df["Rework_Flag"] == "Yes").mean(), 2),
    }


def kpis_from_case_management():
    df = pd.read_csv(os.path.join(RAW, "case_management_export.csv"))
    df["Status"] = df["Status"].str.lower().map(STATUS_MAP)
    for c in ["Received_Date", "Closed_Date"]:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    closed = df[df["Status"] == "Closed"]
    tat = (closed["Closed_Date"] - closed["Received_Date"]).dt.days
    sla = (tat <= closed["SLA_Target_Days"]).mean() * 100
    return {
        # no dedupe, no cancelled handling - this is the raw system count
        "KPI-01": float(len(df)),
        "KPI-02": float((df["Status"] != "Closed").sum()),
        "KPI-03": float(tat.median()),
        "KPI-04": round(sla, 2),
        "KPI-05": None,
        "KPI-06": None,
    }


def kpis_from_workflow_tracker():
    df = pd.read_csv(os.path.join(RAW, "workflow_tracker_export.csv"))
    df["Case_State"] = df["Case_State"].str.lower().map(STATUS_MAP)
    df["Received_Date"] = pd.to_datetime(df["Received_Date"], errors="coerce")
    df["Completion_Date"] = pd.to_datetime(df["Completion_Date"], errors="coerce")
    closed = df[df["Case_State"] == "Closed"]
    tat = (closed["Completion_Date"] - closed["Received_Date"]).dt.days
    return {
        "KPI-01": float(len(df)),
        "KPI-02": float((~df["Case_State"].isin(["Closed", "Cancelled"])).sum()),
        "KPI-03": float(tat.median()),
        "KPI-04": None,
        "KPI-05": round(100.0 * (df["Reassignment_Count"] == 0).mean(), 2),
        "KPI-06": round(100.0 * (df["Rework_Flag"] == "Yes").mean(), 2),
    }


def kpis_from_leadership():
    df = pd.read_csv(os.path.join(RAW, "leadership_reporting_extract.csv"))
    df["ReceivedDate"] = pd.to_datetime(df["ReceivedDate"], errors="coerce")
    df["ClosedDate"] = pd.to_datetime(df["ClosedDate"], errors="coerce")
    closed = df[df["Status"] == "Closed"]
    tat = (closed["ClosedDate"] - closed["ReceivedDate"]).dt.days
    sla = (tat <= closed["SLATarget"]).mean() * 100
    return {
        "KPI-01": float(len(df)),
        "KPI-02": float((df["Status"] != "Closed").sum()),
        "KPI-03": float(tat.median()),
        "KPI-04": round(sla, 2),
        "KPI-05": None,
        "KPI-06": None,
    }


def reconcile(reporting):
    catalog = pd.read_csv(os.path.join(RAW, "kpi_catalog.csv"))
    certified = kpis_from_reporting(reporting)
    sources = {
        "case_management": kpis_from_case_management(),
        "workflow_tracker": kpis_from_workflow_tracker(),
        "leadership_extract": kpis_from_leadership(),
    }

    critical_sources = {e["Record_ID"] for e in exceptions if e["Severity"] == "Critical"}

    rows = []
    for _, k in catalog.iterrows():
        kid, unit = k["KPI_ID"], k["Unit"]
        tol = TOLERANCE[unit]
        for src, vals in sources.items():
            sv = vals.get(kid)
            if sv is None:
                rows.append({"KPI_ID": kid, "KPI_Name": k["KPI_Name"], "Source": src,
                             "Source_Value": None, "Certified_Value": certified[kid],
                             "Variance": None, "Unit": unit, "Tolerance": tol,
                             "Within_Tolerance": "N/A",
                             "Note": "KPI not available from this source"})
                continue
            var = round(sv - certified[kid], 2)
            ok = abs(var) <= tol
            note = ""
            if not ok:
                note = explain(kid, src, var)
            rows.append({"KPI_ID": kid, "KPI_Name": k["KPI_Name"], "Source": src,
                         "Source_Value": sv, "Certified_Value": certified[kid],
                         "Variance": var, "Unit": unit, "Tolerance": tol,
                         "Within_Tolerance": "Yes" if ok else "No", "Note": note})

    recon = pd.DataFrame(rows)

    # certification: a KPI is certified only if every available source is within
    # tolerance AND no Critical exception touches its authoritative source
    cert_rows = []
    for _, k in catalog.iterrows():
        kid = k["KPI_ID"]
        sub = recon[(recon["KPI_ID"] == kid) & (recon["Within_Tolerance"] != "N/A")]
        all_ok = (sub["Within_Tolerance"] == "Yes").all()
        blocked = k["Authoritative_Source"].lower().replace(" ", "_") in {
            s.lower() for s in critical_sources}
        has_critical = any(e["Severity"] == "Critical" for e in exceptions)
        cert_rows.append({
            "KPI_ID": kid,
            "KPI_Name": k["KPI_Name"],
            "Certified_Value": kpis_from_reporting(reporting)[kid],
            "Unit": k["Unit"],
            "Sources_Tested": len(sub),
            "Sources_Within_Tolerance": int((sub["Within_Tolerance"] == "Yes").sum()),
            "Certified": "Yes" if (all_ok and not blocked) else "No",
            "Blocking_Reason": "" if (all_ok and not blocked) else (
                "Critical exception on authoritative source" if blocked
                else "One or more sources outside tolerance"),
        })
    cert = pd.DataFrame(cert_rows)
    return recon, cert


def explain(kid, src, var):
    """Plain-language cause for each known variance. This column is the
    difference between a reconciliation report and a shrug."""
    if src == "leadership_extract":
        if kid == "KPI-01":
            return ("Extract is four days stale and excludes Cancelled appeals entirely, "
                    "so volume is understated.")
        if kid == "KPI-02":
            return ("Cancelled appeals excluded and Reopened rolled into Closed, so "
                    "backlog is understated.")
        if kid == "KPI-03":
            return "Manual date edits in the workbook shortened 40 turnaround values."
        if kid == "KPI-04":
            return ("Manual date edits inflate SLA compliance; the extract also excludes "
                    "Cancelled cases from the denominator.")
    if src == "workflow_tracker":
        if kid == "KPI-01":
            return ("Tracker is keyed on intake date rather than receipt date and is "
                    "missing 65 rows, so volume differs on both count and period.")
        if kid == "KPI-02":
            return ("90 completed cases were never updated in the tracker, so they are "
                    "still counted as in progress.")
        if kid == "KPI-03":
            return ("Turnaround measured from intake date rather than receipt date, "
                    "understating elapsed time.")
        if kid in ("KPI-05", "KPI-06"):
            return ("Denominator differs from the reporting layer because 65 rows are "
                    "missing from the tracker.")
    if src == "case_management":
        if kid == "KPI-01":
            return ("Raw system count includes duplicate rows created when a case is "
                    "reopened; the reporting layer deduplicates.")
        if kid == "KPI-02":
            return ("System backlog count treats Cancelled as open; the certified "
                    "definition excludes Cancelled.")
        if kid in ("KPI-03", "KPI-04"):
            return ("Duplicate reopened rows are included in the raw system calculation.")
    return "Variance cause not yet documented; assigned for investigation."


def main():
    os.makedirs(CLEAN, exist_ok=True)
    reporting, blocked = build_reporting_layer()
    recon, cert = reconcile(reporting)

    ex = pd.DataFrame(exceptions)
    reporting.to_csv(os.path.join(CLEAN, "reporting_layer.csv"), index=False)
    ex.to_csv(os.path.join(CLEAN, "dq_exceptions.csv"), index=False)
    recon.to_csv(os.path.join(CLEAN, "kpi_reconciliation.csv"), index=False)
    cert.to_csv(os.path.join(CLEAN, "kpi_certification.csv"), index=False)

    tested = recon[recon["Within_Tolerance"] != "N/A"]
    rate = 100.0 * (tested["Within_Tolerance"] == "Yes").sum() / len(tested)

    print(f"reporting layer rows:      {len(reporting)}")
    print(f"records blocked:           {len(blocked)}")
    print(f"exceptions logged:         {len(ex)}")
    print(f"  critical:                {(ex['Severity'] == 'Critical').sum()}")
    print(f"  high:                    {(ex['Severity'] == 'High').sum()}")
    print(f"KPI/source pairs tested:   {len(tested)}")
    print(f"Reconciliation Rate:       {rate:.1f}%")
    print(f"KPIs certified:            {(cert['Certified'] == 'Yes').sum()} of {len(cert)}")
    print()
    print(cert[["KPI_ID", "KPI_Name", "Certified_Value", "Unit", "Certified"]].to_string(index=False))
    print()
    print("Variances outside tolerance:")
    out = tested[tested["Within_Tolerance"] == "No"]
    print(out[["KPI_ID", "Source", "Source_Value", "Certified_Value", "Variance"]].to_string(index=False))


if __name__ == "__main__":
    main()
