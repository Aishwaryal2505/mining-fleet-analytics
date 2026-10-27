"""
Quick connection test for project7-fleet-db.
Run this on YOUR machine (not in any sandbox) after installing psycopg2:

    pip install psycopg2-binary

Then run:

    python test_connection.py

It will prompt for your master password (not stored anywhere).
"""

import getpass
import psycopg2

HOST = "project7-fleet-db.cl8okuquybnu.ap-southeast-2.rds.amazonaws.com"
PORT = 5432
DBNAME = "fleet_analytics"
USER = "postgres"

password = getpass.getpass("Master password: ")

try:
    conn = psycopg2.connect(
        host=HOST,
        port=PORT,
        dbname=DBNAME,
        user=USER,
        password=password,
        sslmode="require",
        connect_timeout=10,
    )
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print("Connected successfully!")
    print(cur.fetchone()[0])
    cur.close()
    conn.close()
except Exception as e:
    print("Connection FAILED.")
    print(f"Error: {e}")
    print("\nCommon causes:")
    print("  - Your current public IP doesn't match the security group's allowed IP")
    print("    (ISPs change IPs periodically -> go update the inbound rule)")
    print("  - Wrong password")
    print("  - Instance not fully 'Available' yet")
