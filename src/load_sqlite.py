"""Loads the reporting layer, reconciliation output, and source extracts into SQLite."""

import os
import sqlite3

import pandas as pd

DB = os.path.join("data", "kpi_trust.db")
TABLES = {
    "reporting_layer": ("data", "clean", "reporting_layer.csv"),
    "kpi_reconciliation": ("data", "clean", "kpi_reconciliation.csv"),
    "kpi_certification": ("data", "clean", "kpi_certification.csv"),
    "dq_exceptions": ("data", "clean", "dq_exceptions.csv"),
    "kpi_catalog": ("data", "raw", "kpi_catalog.csv"),
    "case_management_export": ("data", "raw", "case_management_export.csv"),
    "workflow_tracker_export": ("data", "raw", "workflow_tracker_export.csv"),
    "leadership_reporting_extract": ("data", "raw", "leadership_reporting_extract.csv"),
    "dim_team": ("data", "raw", "dim_team.csv"),
    "dim_payer": ("data", "raw", "dim_payer.csv"),
    "dim_date": ("data", "raw", "dim_date.csv"),
}


def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    for name, parts in TABLES.items():
        df = pd.read_csv(os.path.join(*parts))
        df.to_sql(name, con, if_exists="replace", index=False)
        print(f"{name:<30} {len(df):>6} rows")
    con.commit()
    con.close()
    print(f"\nwrote {DB}")


if __name__ == "__main__":
    main()
