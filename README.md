# Mining Logistics & Fleet Analytics Pipeline

An end-to-end data analytics pipeline simulating a mining operation's haul truck fleet — built to mirror the skills and KPIs listed in real "Data Analyst — Warehousing & Logistics" roles (Power BI, data modelling, fleet utilization, delivery performance).

**Pipeline:** Python (simulation) → AWS RDS / PostgreSQL (cloud storage) → SQL (analysis) → Power BI (live dashboard)

All company, site, and personnel names are fictional.

---

## Tech stack

| Stage | Tool |
|---|---|
| Data generation | Python (pandas, numpy) |
| Cloud database | AWS RDS — PostgreSQL 16 |
| Analysis | SQL (window functions, CTEs, joins) |
| Visualization | Power BI Desktop (native PostgreSQL connector, DAX measures) |

---

## The story

A fictional iron-ore mining operation runs 10 haul trucks (7 short-haul pit trucks, 3 long-haul road trains) across 5 sites, 4 routes, and 18 drivers, over a 3-month period. The simulation generates realistic operational noise: delayed and cancelled trips, mechanical breakdowns, scheduled maintenance, and fuel consumption that varies by truck type.

That data is loaded into a live PostgreSQL database on AWS RDS, analyzed with SQL to produce the KPIs a fleet/logistics manager actually tracks, and visualized in a Power BI dashboard connected directly to the live database.

---

## KPIs covered

1. **Fleet utilization %** — hours spent on trips ÷ (available hours − downtime), per truck and fleet-wide
2. **On-time delivery rate** — % of deliveries arriving within 15 minutes of schedule, by route and by driver
3. **Downtime cost** — total and average cost by failure reason, by truck, and trend over time
4. *(Bonus)* Fuel efficiency — litres/km and cost/km by truck

---
## AI-generated executive summary

`scripts/ai_summary.py` pulls the live KPI numbers from RDS and uses the Google Gemini API
to generate a short, plain-English performance summary — the kind of narrative a manager
could read in 15 seconds instead of parsing raw numbers or charts.

Example output:
> "Over the past three months, the fleet achieved an 85.1% on-time delivery rate while
> incurring $486,010 AUD in total downtime costs. Mechanical failures were the primary
> financial drain, accounting for nearly 48% ($233,568 AUD) of these losses... Addressing
> the root causes of recurring mechanical breakdowns and investigating the low deployment
> of these bottom three units represent your highest-impact opportunities to recover
> capacity and reduce costs."

Requires a free Gemini API key (aistudio.google.com) set as `GEMINI_API_KEY`:
```bash
pip install google-genai
python scripts/ai_summary.py
```

## Project structure

```
mining-fleet-analytics/
├── data/                       # Generated CSVs (fixed random seed — reproducible)
│   ├── sites.csv
│   ├── routes.csv
│   ├── trucks.csv
│   ├── drivers.csv
│   ├── trips.csv
│   ├── downtime_events.csv
│   ├── fuel_logs.csv
│   └── deliveries.csv
├── scripts/
│   ├── generate_data.py        # Stage 1: simulates the fleet data
│   ├── schema.sql               # Stage 2: table definitions + foreign keys
│   ├── create_database.py       # Stage 2: one-time DB creation on RDS
│   ├── test_connection.py       # Stage 2: connectivity check
│   ├── load_to_rds.py           # Stage 2: bulk-loads CSVs into RDS via COPY
│   ├── kpi_queries.sql          # Stage 3: the 9 analytical queries
│   └── run_kpi_queries.py       # Stage 3: runs kpi_queries.sql, prints results
└── dashboard/
    └── fleet_analytics.pbix     # Stage 4: Power BI dashboard (live RDS connection)
```

---

## Reproducing this project

### 1. Generate the data
```bash
pip install pandas numpy
python scripts/generate_data.py
```
Produces ~9,700 trips, ~9,400 deliveries, ~80 downtime events, ~900 fuel logs in `data/`.

### 2. Set up AWS RDS
- Launch a PostgreSQL instance (free tier: `db.t4g.micro`, 20 GiB)
- Create a security group allowing inbound PostgreSQL (port 5432) from your IP only
- Create the `fleet_analytics` database:
```bash
pip install psycopg2-binary
python scripts/create_database.py
```

### 3. Load the data
```bash
# Set connection details as environment variables first
export PGHOST=<your-rds-endpoint>
export PGPORT=5432
export PGDATABASE=fleet_analytics
export PGUSER=postgres
export PGPASSWORD=<your-password>

python scripts/load_to_rds.py
```
Applies `schema.sql`, then bulk-loads all 8 tables in foreign-key-safe order via PostgreSQL's `COPY`.

### 4. Run the SQL analysis
```bash
python scripts/run_kpi_queries.py
```

### 5. Open the dashboard
Open `dashboard/fleet_analytics.pbix` in Power BI Desktop, or connect fresh via **Get Data → PostgreSQL database** using the same RDS credentials.

---

## Sample results

| Metric | Result |
|---|---|
| Overall on-time delivery rate | 85.1% |
| Fleet-wide utilization | ~27% (pit-haul trucks ~32%, line-haul ~13%) |
| Total downtime cost (3 months) | ~$486,000 AUD |
| Top downtime cost driver | Mechanical failure ($233K total, $13K avg/event — highest per-incident cost despite fewer events than scheduled maintenance) |

---

## Notes

- Data is synthetic, generated with a fixed random seed (`SEED = 42`) for reproducibility.
- The RDS instance used during development has been stopped/terminated to avoid ongoing AWS charges — the `.pbix` dashboard was built against a live connection and reflects the schema and KPIs described above.
- Credentials are never hardcoded; all scripts read connection details from environment variables.
