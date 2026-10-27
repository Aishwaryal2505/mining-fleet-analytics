"""
Mining Logistics & Fleet Analytics Pipeline
Loads generated CSVs (../data/) into the AWS RDS PostgreSQL instance.

Credentials are read from environment variables -- never hardcoded here.
Set these before running (example for bash):

    export PGHOST="project7-fleet-db.xxxxxxxxxx.ap-southeast-2.rds.amazonaws.com"
    export PGPORT="5432"
    export PGDATABASE="fleet_analytics"
    export PGUSER="postgres"
    export PGPASSWORD="your-password-here"

Then run:
    python3 scripts/load_to_rds.py
"""

import io
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

# Load order matters: reference tables first, then facts, respecting FKs.
LOAD_ORDER = [
    ("sites", "sites.csv"),
    ("routes", "routes.csv"),
    ("trucks", "trucks.csv"),
    ("drivers", "drivers.csv"),
    ("trips", "trips.csv"),
    ("deliveries", "deliveries.csv"),
    ("downtime_events", "downtime_events.csv"),
    ("fuel_logs", "fuel_logs.csv"),
]

REQUIRED_ENV = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]


def get_connection():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        print("Set them before running this script (see the docstring at the top of this file).")
        sys.exit(1)

    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        connect_timeout=10,
    )


def apply_schema(conn):
    print("Applying schema...")
    with open(SCHEMA_FILE, "r") as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print("Schema applied.")


def load_table(conn, table_name, csv_file):
    path = DATA_DIR / csv_file
    if not path.exists():
        print(f"  SKIP {table_name}: {csv_file} not found in {DATA_DIR}")
        return

    df = pd.read_csv(path)
    buffer = io.StringIO()
    # Write without header, using \N-free NaN handling: pandas writes empty
    # string for NaN by default, which COPY interprets as NULL when we set
    # NULL '' below.
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    columns = ",".join(df.columns)
    copy_sql = f"COPY {table_name} ({columns}) FROM STDIN WITH (FORMAT csv, NULL '')"

    with conn.cursor() as cur:
        cur.copy_expert(copy_sql, buffer)
    conn.commit()
    print(f"  Loaded {len(df):,} rows into {table_name}")


def main():
    conn = get_connection()
    try:
        apply_schema(conn)
        print("Loading data...")
        for table_name, csv_file in LOAD_ORDER:
            load_table(conn, table_name, csv_file)
        print("Done. All tables loaded into RDS.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
