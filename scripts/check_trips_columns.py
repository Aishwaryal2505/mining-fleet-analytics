"""
Checks the actual column list for the 'trips' table on RDS,
straight from PostgreSQL's system catalog - bypasses Power BI entirely.

Run:
    python check_trips_columns.py
"""

import os
import psycopg2

conn = psycopg2.connect(
    host=os.environ["PGHOST"],
    port=os.environ["PGPORT"],
    dbname=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
)
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_name = 'trips' ORDER BY ordinal_position;"
)
print("Columns in 'trips' table on RDS:")
for row in cur.fetchall():
    print(" -", row[0])
cur.close()
conn.close()
