"""
Creates the fleet_analytics database on project7-fleet-db.
Run this once, from your own machine:

    python create_database.py

It connects to the default 'postgres' maintenance database (which always
exists on a fresh RDS instance) and creates 'fleet_analytics' inside it.
"""

import getpass
import psycopg2

HOST = "project7-fleet-db.cl8okuquybnu.ap-southeast-2.rds.amazonaws.com"
PORT = 5432
USER = "postgres"

password = getpass.getpass("Master password: ")

try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname="postgres",   # connect to the default maintenance DB, not fleet_analytics
        user=USER,
        password=password,
        sslmode="require",
        connect_timeout=10,
    )
    conn.autocommit = True  # CREATE DATABASE can't run inside a transaction block
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'fleet_analytics';")
    if cur.fetchone():
        print("Database 'fleet_analytics' already exists. Nothing to do.")
    else:
        cur.execute("CREATE DATABASE fleet_analytics;")
        print("Database 'fleet_analytics' created successfully.")

    cur.close()
    conn.close()
except Exception as e:
    print("FAILED.")
    print(f"Error: {e}")
