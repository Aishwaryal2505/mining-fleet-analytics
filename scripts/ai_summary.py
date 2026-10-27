"""
Generates a short, plain-English executive summary of fleet performance,
using the Google Gemini API, based on the real KPI numbers pulled live from RDS.

Requires:
    pip install google-genai psycopg2-binary

Requires these environment variables to be set first:
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD   (same as the other scripts)
    GEMINI_API_KEY                                    (from aistudio.google.com)

Run:
    python ai_summary.py
"""

import os
import sys
import psycopg2
from google import genai


def get_connection():
    required = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)
    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ["PGPORT"],
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
    )


def fetch_kpi_numbers(conn):
    """Pulls the same headline numbers we already verified in kpi_queries.sql."""
    cur = conn.cursor()

    # Overall on-time delivery rate
    cur.execute("""
        SELECT ROUND(100.0 * SUM(CASE WHEN on_time THEN 1 ELSE 0 END) / COUNT(*), 1)
        FROM deliveries;
    """)
    overall_on_time_pct = cur.fetchone()[0]

    # Downtime cost by reason
    cur.execute("""
        SELECT reason, SUM(estimated_cost_aud)
        FROM downtime_events
        GROUP BY reason
        ORDER BY SUM(estimated_cost_aud) DESC;
    """)
    downtime_by_reason = cur.fetchall()

    # Total downtime cost
    cur.execute("SELECT ROUND(SUM(estimated_cost_aud)::numeric, 2) FROM downtime_events;")
    total_downtime_cost = cur.fetchone()[0]

    # Fleet utilization by truck (simplified overall average)
    cur.execute("""
        WITH trip_hours AS (
            SELECT truck_id, trip_date,
                SUM(EXTRACT(EPOCH FROM (actual_end_ts - actual_start_ts)) / 3600.0) AS hours_on_trips
            FROM trips
            WHERE status IN ('completed', 'delayed') AND actual_start_ts IS NOT NULL AND actual_end_ts IS NOT NULL
            GROUP BY truck_id, trip_date
        ),
        daily_downtime AS (
            SELECT truck_id, event_date AS trip_date, SUM(downtime_hours) AS downtime_hours
            FROM downtime_events GROUP BY truck_id, event_date
        ),
        active_days AS (SELECT DISTINCT truck_id, trip_date FROM trips),
        daily AS (
            SELECT ad.truck_id, ad.trip_date,
                COALESCE(th.hours_on_trips, 0) AS hours_on_trips,
                COALESCE(dd.downtime_hours, 0) AS downtime_hours
            FROM active_days ad
            LEFT JOIN trip_hours th ON th.truck_id = ad.truck_id AND th.trip_date = ad.trip_date
            LEFT JOIN daily_downtime dd ON dd.truck_id = ad.truck_id AND dd.trip_date = ad.trip_date
        )
        SELECT t.truck_code,
            ROUND(100.0 * SUM(d.hours_on_trips) / NULLIF(SUM(24 - d.downtime_hours), 0), 1) AS avg_utilization_pct
        FROM daily d JOIN trucks t ON t.truck_id = d.truck_id
        GROUP BY t.truck_code
        ORDER BY avg_utilization_pct DESC;
    """)
    utilization_by_truck = cur.fetchall()

    cur.close()
    return {
        "overall_on_time_pct": overall_on_time_pct,
        "downtime_by_reason": downtime_by_reason,
        "total_downtime_cost": total_downtime_cost,
        "utilization_by_truck": utilization_by_truck,
    }


def build_prompt(kpis):
    """Turns the raw numbers into a text prompt for the AI to summarize."""
    downtime_lines = "\n".join(
        f"  - {reason}: ${cost:,.2f}" for reason, cost in kpis["downtime_by_reason"]
    )
    utilization_lines = "\n".join(
        f"  - {truck}: {pct}%" for truck, pct in kpis["utilization_by_truck"]
    )

    prompt = f"""You are a logistics analyst writing a brief executive summary for a mining company's fleet manager.

Here is the real data from the last 3 months of fleet operations:

Overall on-time delivery rate: {kpis['overall_on_time_pct']}%

Total downtime cost: ${kpis['total_downtime_cost']:,.2f} AUD

Downtime cost by reason:
{downtime_lines}

Fleet utilization by truck:
{utilization_lines}

Write a concise, 3-4 sentence executive summary of fleet performance based on this data.
Highlight the most important pattern or insight (e.g. a cost driver worth investigating,
a gap between truck types, or a performance strength). Write in plain business English,
no bullet points, no headers - just a short paragraph a manager could read in 15 seconds."""
    return prompt


def main():
    conn = get_connection()
    try:
        kpis = fetch_kpi_numbers(conn)
    finally:
        conn.close()

    prompt = build_prompt(kpis)

    client = genai.Client()  # reads GEMINI_API_KEY from environment automatically
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
    )

    summary_text = response.text

    print("=" * 60)
    print("AI-GENERATED FLEET PERFORMANCE SUMMARY")
    print("=" * 60)
    print(summary_text)
    print("=" * 60)


if __name__ == "__main__":
    main()
