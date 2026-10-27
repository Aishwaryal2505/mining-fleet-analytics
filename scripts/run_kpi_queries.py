"""
Runs each query in kpi_queries.sql against the RDS database and prints
the results as simple tables. Use this instead of psql, which isn't
installed on Windows by default.

Requires the same PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD
environment variables used by load_to_rds.py.

Run:
    python run_kpi_queries.py
"""

import os
import sys
from pathlib import Path

import psycopg2

SQL_FILE = Path(__file__).resolve().parent / "kpi_queries.sql"
REQUIRED_ENV = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]


def get_connection():
    missing = [v for v in REQUIRED_ENV if not os.environ.get(v)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
        connect_timeout=10,
    )


def split_statements(sql_text):
    """Split on semicolons that end a statement, ignoring semicolons inside
    comments. Good enough for this file since there are no semicolons inside
    string literals."""
    statements = []
    current = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def print_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    def fmt_row(vals):
        return " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(vals))
    print(fmt_row(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt_row(row))
    print(f"({len(rows)} rows)\n")


def main():
    sql_text = SQL_FILE.read_text()
    statements = split_statements(sql_text)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for i, stmt in enumerate(statements, 1):
                first_line = next((l for l in stmt.splitlines() if l.strip()), "")
                print(f"=== Query {i}: {first_line.strip()[:80]} ===")
                cur.execute(stmt)
                if cur.description:
                    headers = [d[0] for d in cur.description]
                    rows = cur.fetchall()
                    print_table(headers, rows)
                else:
                    print("(no rows returned)\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()