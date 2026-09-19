"""
Builds three deliberately inconsistent source extracts for Lone Star Care
Operations (fictional org).

The whole point of this project is that the three systems disagree. A single
"true" appeals population is generated first, then each extract is derived
from it with its own definitional quirks, refresh lag, and sloppiness:

  case_management_export      - the operational system, closest to truth
  workflow_tracker_export     - team-maintained tracker, different status
                                labels and its own idea of "intake date"
  leadership_reporting_extract- stale monthly pull that excludes cancelled
                                cases and carries manual edits

None of the three is right. The reconciliation step figures out why.

Run:  python src/generate_sources.py
"""

import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 77
N = 6000
START = date(2026, 1, 1)
END = date(2026, 6, 30)
REPORT_DATE = date(2026, 6, 30)
LEADERSHIP_AS_OF = date(2026, 6, 26)  # four days stale, on purpose

RAW = os.path.join("data", "raw")

TEAMS = [f"TM-{i:02d}" for i in range(1, 8)]
PAYERS = ["PAY-01", "PAY-02", "PAY-03", "PAY-04", "PAY-05"]
TYPES = ["Clinical", "Administrative", "Authorization", "Pharmacy"]

KPI_CATALOG = [
    ("KPI-01", "Appeal Volume", "Count of appeals received in the reporting period",
     "COUNT(Appeal_ID) WHERE Received_Date BETWEEN period start AND end",
     "Appeals Ops Manager", "Appeals case system", "Count", "0 variance"),
    ("KPI-02", "Open Backlog", "Count of appeals not closed as of the reporting date",
     "COUNT(Appeal_ID) WHERE Status <> 'Closed' AS OF reporting date",
     "Appeals Ops Manager", "Appeals case system", "Count", "0 variance"),
    ("KPI-03", "Median Turnaround", "Median calendar days from receipt to closure for closed appeals",
     "MEDIAN(Closed_Date - Received_Date) WHERE Status = 'Closed'",
     "Reporting Analyst", "Appeals case system", "Days", "under 0.25 days"),
    ("KPI-04", "SLA Compliance", "Closed appeals meeting the SLA target divided by closed appeals",
     "COUNT(SLA_Met = 'Yes') / COUNT(Status = 'Closed')",
     "Quality Lead", "Appeals case system", "Percent", "under 1 percentage point"),
    ("KPI-05", "First-Pass Routing Accuracy", "Appeals resolved without reassignment divided by all appeals",
     "COUNT(Reassignment_Count = 0) / COUNT(Appeal_ID)",
     "Appeals Ops Manager", "Workflow tracker", "Percent", "under 1 percentage point"),
    ("KPI-06", "Rework Rate", "Appeals requiring rework divided by all appeals",
     "COUNT(Rework_Flag = 'Yes') / COUNT(Appeal_ID)",
     "Quality Lead", "Workflow tracker", "Percent", "under 1 percentage point"),
]


def build_truth():
    rows = []
    span = (END - START).days
    for i in range(1, N + 1):
        received = START + timedelta(days=random.randint(0, span))
        # the operational system logs receipt; intake happens a day or two later
        intake = received + timedelta(days=random.choices([0, 1, 2, 3], weights=[.4, .35, .18, .07])[0])
        appeal_type = random.choice(TYPES)
        sla = {"Clinical": 14, "Administrative": 30, "Authorization": 7, "Pharmacy": 7}[appeal_type]
        reassign = random.choices([0, 1, 2, 3], weights=[.74, .18, .06, .02])[0]
        rework = random.random() < 0.14
        tat = max(1, int(np.random.gamma(2.2, 4.0)) + 2 * reassign + (4 if rework else 0))
        closed = received + timedelta(days=tat)

        if closed > END:
            status = "Open"
            closed_date = None
        elif random.random() < 0.025:
            status = "Cancelled"          # the category that breaks backlog counts
            closed_date = closed
        elif random.random() < 0.02:
            status = "Reopened"           # the category that breaks volume counts
            closed_date = None
        else:
            status = "Closed"
            closed_date = closed

        rows.append({
            "Appeal_ID": f"APL-2026-{i:06d}",
            "Received_Date": received,
            "Intake_Date": intake,
            "Closed_Date": closed_date,
            "Status": status,
            "Appeal_Type": appeal_type,
            "Payer_ID": random.choice(PAYERS),
            "Team_ID": random.choice(TEAMS),
            "SLA_Target_Days": sla,
            "Reassignment_Count": reassign,
            "Rework_Flag": "Yes" if rework else "No",
        })
    return pd.DataFrame(rows)


def case_management_export(truth):
    """Closest to truth. Status vocabulary: Closed / Open / Cancelled / Reopened.
    Uses Received_Date as the volume date. Adds a few duplicate reopened rows,
    which is the real-world artifact of a case being reopened as a new row."""
    df = truth.copy()
    df = df[["Appeal_ID", "Received_Date", "Closed_Date", "Status", "Appeal_Type",
             "Payer_ID", "Team_ID", "SLA_Target_Days"]]
    reopened = df[df["Status"] == "Reopened"].sample(frac=0.6, random_state=1)
    df = pd.concat([df, reopened], ignore_index=True)
    df["Source_System"] = "case_management"
    df["Extract_Timestamp"] = f"{REPORT_DATE} 23:50:00"
    return df.sample(frac=1, random_state=4).reset_index(drop=True)


def workflow_tracker_export(truth):
    """Team-maintained. Uses Intake_Date as its date field and calls it
    Received_Date, which shifts volume between months. Status labels are free
    text. Holds the routing and rework fields nothing else has."""
    df = truth.copy()
    label = {"Closed": "COMPLETE", "Open": "In Progress", "Cancelled": "Withdrawn",
             "Reopened": "Re-Opened"}
    out = pd.DataFrame({
        "Case_Ref": df["Appeal_ID"],
        "Received_Date": df["Intake_Date"],          # different definition, same column name
        "Completion_Date": df["Closed_Date"],
        "Case_State": df["Status"].map(label),
        "Type": df["Appeal_Type"].str.upper(),
        "Team": df["Team_ID"],
        "Reassignment_Count": df["Reassignment_Count"],
        "Rework_Flag": df["Rework_Flag"],
    })
    # free-text drift: a slice of rows typed differently
    idx = out.sample(120, random_state=2).index
    out.loc[idx, "Case_State"] = out.loc[idx, "Case_State"].replace(
        {"COMPLETE": "Completed", "In Progress": "in progress", "Withdrawn": "withdrawn"})
    # the tracker is maintained by hand, so some rows were never updated
    stale = out[out["Case_State"].isin(["COMPLETE", "Completed"])].sample(90, random_state=3).index
    out.loc[stale, "Case_State"] = "In Progress"
    out.loc[stale, "Completion_Date"] = None
    # and some rows are simply missing
    out = out.drop(out.sample(65, random_state=5).index)
    out["Source_System"] = "workflow_tracker"
    out["Extract_Timestamp"] = f"{REPORT_DATE} 18:15:00"
    return out.reset_index(drop=True)


def leadership_reporting_extract(truth):
    """A monthly pull that is four days stale, excludes cancelled cases from
    every count, and carries manual overrides someone typed into the workbook."""
    df = truth.copy()
    df = df[df["Received_Date"] <= LEADERSHIP_AS_OF]
    df = df[df["Status"] != "Cancelled"]             # silently excluded
    out = pd.DataFrame({
        "AppealID": df["Appeal_ID"],
        "ReceivedDate": df["Received_Date"],
        "ClosedDate": df["Closed_Date"],
        "Status": df["Status"].replace({"Reopened": "Closed"}),  # reopened rolled into closed
        "AppealType": df["Appeal_Type"],
        "Payer": df["Payer_ID"],
        "SLATarget": df["SLA_Target_Days"],
    })
    # manual edits: 40 turnaround values adjusted by hand in the workbook
    idx = out.dropna(subset=["ClosedDate"]).sample(40, random_state=6).index
    out.loc[idx, "ClosedDate"] = pd.to_datetime(out.loc[idx, "ClosedDate"]) - pd.to_timedelta(
        np.random.randint(1, 4, size=len(idx)), unit="D")
    # payer name spelling drift
    idx = out.sample(55, random_state=7).index
    out.loc[idx, "Payer"] = out.loc[idx, "Payer"].str.replace("PAY-", "Pay ", regex=False)
    out["Source_System"] = "leadership_extract"
    out["Extract_Timestamp"] = f"{LEADERSHIP_AS_OF} 07:00:00"
    return out.reset_index(drop=True)


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    os.makedirs(RAW, exist_ok=True)

    truth = build_truth()
    cms = case_management_export(truth)
    wft = workflow_tracker_export(truth)
    lre = leadership_reporting_extract(truth)

    catalog = pd.DataFrame(KPI_CATALOG, columns=[
        "KPI_ID", "KPI_Name", "Business_Definition", "Formula", "Owner",
        "Authoritative_Source", "Unit", "Tolerance"])

    dim_team = pd.DataFrame({"Team_ID": TEAMS,
                             "Team_Name": [f"Appeals Team {chr(64+i)}" for i in range(1, 8)]})
    dim_payer = pd.DataFrame({"Payer_ID": PAYERS,
                              "Payer_Name": ["Trinity Health Plan", "Brazos Valley Benefits",
                                             "Statewide Medicaid MCO", "Silver Ridge Advantage",
                                             "Cottonwood Mutual"]})

    dates = pd.date_range(START, END, freq="D")
    dim_date = pd.DataFrame({
        "Date": dates.strftime("%Y-%m-%d"),
        "Year": dates.year,
        "Month": dates.month,
        "Month_Name": dates.strftime("%B"),
        "Quarter": dates.quarter,
        "Week_Of_Year": dates.isocalendar().week.values,
        "Day_Name": dates.strftime("%A"),
        "Is_Weekend": np.where(dates.dayofweek >= 5, "Yes", "No"),
    })
    dim_date.to_csv(os.path.join(RAW, "dim_date.csv"), index=False)

    truth.to_csv(os.path.join(RAW, "_ground_truth.csv"), index=False)
    cms.to_csv(os.path.join(RAW, "case_management_export.csv"), index=False)
    wft.to_csv(os.path.join(RAW, "workflow_tracker_export.csv"), index=False)
    lre.to_csv(os.path.join(RAW, "leadership_reporting_extract.csv"), index=False)
    catalog.to_csv(os.path.join(RAW, "kpi_catalog.csv"), index=False)
    dim_team.to_csv(os.path.join(RAW, "dim_team.csv"), index=False)
    dim_payer.to_csv(os.path.join(RAW, "dim_payer.csv"), index=False)

    with pd.ExcelWriter(os.path.join(RAW, "04_synthetic_raw_data.xlsx")) as xl:
        cms.to_excel(xl, sheet_name="case_management_export", index=False)
        wft.to_excel(xl, sheet_name="workflow_tracker_export", index=False)
        lre.to_excel(xl, sheet_name="leadership_extract", index=False)
        catalog.to_excel(xl, sheet_name="kpi_catalog", index=False)

    print(f"ground truth rows:        {len(truth)}")
    print(f"case management export:   {len(cms)} rows (includes duplicated reopened cases)")
    print(f"workflow tracker export:  {len(wft)} rows (65 missing, 90 never updated)")
    print(f"leadership extract:       {len(lre)} rows (stale to {LEADERSHIP_AS_OF}, cancelled excluded)")
    print("\n_ground_truth.csv exists only to prove the reconciliation logic. In a real")
    print("engagement there is no ground truth file, which is exactly why this is hard.")


if __name__ == "__main__":
    main()
