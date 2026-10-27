"""
Mining Logistics & Fleet Analytics Pipeline
Simulated data generator.

Generates ~3 months of realistic haul-truck fleet data for a fictional
iron-ore operation: 10 trucks, 5 sites, 4 routes, ~18 drivers.

Output: CSV files in ../data/ ready to be loaded into PostgreSQL (RDS)
via scripts/load_to_rds.py.

All company/site names are fictional. Run with a fixed random seed for
reproducibility.
"""

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = date(2026, 4, 1)
NUM_DAYS = 92  # ~3 months
END_DATE = START_DATE + timedelta(days=NUM_DAYS - 1)

# ---------------------------------------------------------------------------
# Reference data: sites, routes, trucks, drivers
# ---------------------------------------------------------------------------

SITES = pd.DataFrame([
    {"site_id": 1, "site_code": "PITA", "site_name": "Warrigal Pit A", "site_type": "mine_pit",
     "latitude": -22.5231, "longitude": 119.7351},
    {"site_id": 2, "site_code": "PITB", "site_name": "Warrigal Pit B", "site_type": "mine_pit",
     "latitude": -22.5389, "longitude": 119.7602},
    {"site_id": 3, "site_code": "PLNT", "site_name": "Warrigal Processing Plant", "site_type": "processing_plant",
     "latitude": -22.5105, "longitude": 119.7488},
    {"site_id": 4, "site_code": "PORT", "site_name": "Boola Port Stockpile", "site_type": "port",
     "latitude": -20.3103, "longitude": 118.5967},
    {"site_id": 5, "site_code": "DEPO", "site_name": "Ridgeback Fuel Depot", "site_type": "depot",
     "latitude": -22.5177, "longitude": 119.7420},
])

ROUTES = pd.DataFrame([
    {"route_id": 1, "route_name": "Pit A - Plant", "origin_site_id": 1, "destination_site_id": 3,
     "distance_km": 15.4, "typical_duration_min": 25, "route_class": "pit_haul"},
    {"route_id": 2, "route_name": "Pit B - Plant", "origin_site_id": 2, "destination_site_id": 3,
     "distance_km": 22.1, "typical_duration_min": 35, "route_class": "pit_haul"},
    {"route_id": 3, "route_name": "Plant - Port", "origin_site_id": 3, "destination_site_id": 4,
     "distance_km": 181.6, "typical_duration_min": 140, "route_class": "line_haul"},
    {"route_id": 4, "route_name": "Pit A - Port Direct", "origin_site_id": 1, "destination_site_id": 4,
     "distance_km": 192.3, "typical_duration_min": 150, "route_class": "line_haul"},
])

TRUCK_MODELS = ["Cat 793F", "Komatsu 930E", "Liebherr T 284"]

# 7 pit-haul trucks (short cycle, many trips/day) + 3 line-haul road trains (long cycle, few trips/day)
truck_rows = []
for i in range(1, 11):
    truck_type = "line_haul" if i > 7 else "pit_haul"
    truck_rows.append({
        "truck_id": i,
        "truck_code": f"HT-{i:03d}",
        "model": random.choice(TRUCK_MODELS),
        "capacity_tonnes": 240 if truck_type == "pit_haul" else 180,
        "year_commissioned": random.randint(2016, 2024),
        "status": "active",
        "truck_type": truck_type,  # convenience column for the generator; not loaded into RDS schema
    })
TRUCKS = pd.DataFrame(truck_rows)

DRIVER_NAMES = [
    "Jack Thompson", "Amelia Nguyen", "Liam Carter", "Chloe Anderson", "Noah Williams",
    "Isla Martin", "Oliver Brown", "Ava Robinson", "Ethan Clarke", "Mia Walker",
    "Lucas Bennett", "Grace Mitchell", "Henry Cooper", "Zoe Richardson", "James Turner",
    "Ruby Edwards", "Samuel Hughes", "Ella Morgan",
]
DRIVERS = pd.DataFrame([
    {
        "driver_id": i + 1,
        "driver_code": f"DRV-{i + 1:02d}",
        "driver_name": name,
        "shift": "day" if i % 2 == 0 else "night",
    }
    for i, name in enumerate(DRIVER_NAMES)
])

# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

DOWNTIME_REASONS = [
    ("mechanical_failure", 0.35, (2, 18), (3000, 25000)),
    ("scheduled_maintenance", 0.30, (4, 10), (1500, 6000)),
    ("tyre_change", 0.15, (1, 4), (2000, 9000)),
    ("weather", 0.10, (2, 12), (500, 4000)),
    ("fuel_delay", 0.10, (0.5, 2), (200, 1200)),
]


def sample_downtime_reason():
    reasons, weights = zip(*[(r[0], r[1]) for r in DOWNTIME_REASONS])
    reason = random.choices(reasons, weights=weights, k=1)[0]
    spec = next(r for r in DOWNTIME_REASONS if r[0] == reason)
    hours = round(random.uniform(*spec[2]), 1)
    cost = round(random.uniform(*spec[3]), 2)
    return reason, hours, cost


def drivers_for_shift(shift):
    return DRIVERS[DRIVERS["shift"] == shift]["driver_id"].tolist()


# ---------------------------------------------------------------------------
# Main simulation loop
# ---------------------------------------------------------------------------

trips = []
downtime_events = []
fuel_logs = []
deliveries = []

trip_id_seq = 1
event_id_seq = 1
fuel_id_seq = 1
delivery_id_seq = 1

DIESEL_PRICE_PER_L = 1.95  # AUD, off-road/site diesel approx

for day_offset in range(NUM_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)
    is_weekend = current_date.weekday() >= 5

    for _, truck in TRUCKS.iterrows():
        truck_id = truck["truck_id"]
        truck_type = truck["truck_type"]

        # --- Downtime: small daily chance of an event; ~monthly scheduled maintenance ---
        downtime_hours_today = 0.0
        # scheduled maintenance roughly every 45 days per truck, offset by truck_id
        if (day_offset + truck_id * 5) % 45 == 0:
            reason, hours, cost = "scheduled_maintenance", round(random.uniform(6, 12), 1), round(random.uniform(2000, 6000), 2)
            start_ts = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=6)
            end_ts = start_ts + timedelta(hours=hours)
            downtime_events.append({
                "event_id": event_id_seq, "truck_id": truck_id, "event_date": current_date,
                "start_ts": start_ts, "end_ts": end_ts, "downtime_hours": hours,
                "reason": reason, "estimated_cost_aud": cost,
            })
            event_id_seq += 1
            downtime_hours_today += hours
        elif random.random() < 0.06:  # ~6% chance of an unplanned event on any given day
            reason, hours, cost = sample_downtime_reason()
            start_hour = random.uniform(0, 24 - hours) if hours < 24 else 0
            start_ts = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=start_hour)
            end_ts = start_ts + timedelta(hours=hours)
            downtime_events.append({
                "event_id": event_id_seq, "truck_id": truck_id, "event_date": current_date,
                "start_ts": start_ts, "end_ts": end_ts, "downtime_hours": hours,
                "reason": reason, "estimated_cost_aud": cost,
            })
            event_id_seq += 1
            downtime_hours_today += hours

        available_hours = max(0.0, 20.0 - downtime_hours_today)  # two ~10h shifts, minus downtime
        if is_weekend:
            available_hours *= 0.85  # lighter weekend roster

        if available_hours <= 0.5:
            # Truck effectively out of action today
            continue

        # --- Trips for the day ---
        if truck_type == "pit_haul":
            route_id = 1 if truck_id % 2 == 1 else 2
            route = ROUTES.loc[ROUTES.route_id == route_id].iloc[0]
            cycle_min = route["typical_duration_min"] * 2 + 12  # round trip + load/dump
            max_trips = int((available_hours * 60) / cycle_min)
            num_trips = max(0, max_trips - random.randint(0, 2))
        else:  # line_haul
            route_id = 3 if truck_id % 2 == 0 else 4
            route = ROUTES.loc[ROUTES.route_id == route_id].iloc[0]
            cycle_min = route["typical_duration_min"] * 2 + 30
            max_trips = max(1, int((available_hours * 60) / cycle_min))
            num_trips = max(0, min(max_trips, random.choice([1, 1, 2])))

        shift = "day" if not is_weekend or random.random() < 0.6 else "night"
        shift_start_hour = 6 if shift == "day" else 18

        cursor_min = 0
        km_today = 0.0

        for trip_num in range(num_trips):
            driver_pool = drivers_for_shift(shift) or DRIVERS["driver_id"].tolist()
            driver_id = random.choice(driver_pool)

            sched_start = datetime.combine(current_date, datetime.min.time()) + \
                timedelta(hours=shift_start_hour, minutes=int(cursor_min))
            sched_end = sched_start + timedelta(minutes=int(route["typical_duration_min"]))

            # Actual timing: most trips on/near schedule, some delayed, rare cancellation
            roll = random.random()
            if roll < 0.03:
                status = "cancelled"
                actual_start = None
                actual_end = None
            else:
                delay_min = max(0, np.random.normal(loc=4 if roll > 0.15 else 25, scale=6))
                actual_start = sched_start + timedelta(minutes=random.uniform(0, 8))
                actual_end = sched_end + timedelta(minutes=delay_min)
                status = "delayed" if delay_min > 15 else "completed"

            load_tonnes = round(random.uniform(0.85, 1.0) * truck["capacity_tonnes"], 2)

            trips.append({
                "trip_id": trip_id_seq, "truck_id": truck_id, "route_id": int(route_id),
                "driver_id": driver_id, "trip_date": current_date,
                "scheduled_start_ts": sched_start, "actual_start_ts": actual_start,
                "scheduled_end_ts": sched_end, "actual_end_ts": actual_end,
                "load_tonnes": load_tonnes, "status": status,
            })

            if status != "cancelled":
                on_time = (actual_end - sched_end) <= timedelta(minutes=15)
                deliveries.append({
                    "delivery_id": delivery_id_seq, "trip_id": trip_id_seq,
                    "scheduled_delivery_ts": sched_end, "actual_delivery_ts": actual_end,
                    "tonnes_delivered": load_tonnes, "on_time": bool(on_time),
                })
                delivery_id_seq += 1
                km_today += float(route["distance_km"])

            trip_id_seq += 1
            cursor_min += route["typical_duration_min"] + random.randint(8, 20)

        # --- Fuel log for the day (only if the truck moved) ---
        if km_today > 0:
            # Loaded haul trucks burn heavily: ~2.2-3.0 L/km depending on model/load
            l_per_km = random.uniform(2.2, 3.0) if truck_type == "pit_haul" else random.uniform(1.5, 2.0)
            litres = round(km_today * l_per_km * random.uniform(0.95, 1.08), 2)
            fuel_logs.append({
                "log_id": fuel_id_seq, "truck_id": truck_id, "log_date": current_date,
                "litres_consumed": litres, "km_travelled": round(km_today, 2),
                "cost_aud": round(litres * DIESEL_PRICE_PER_L, 2),
            })
            fuel_id_seq += 1

# ---------------------------------------------------------------------------
# Write CSVs
# ---------------------------------------------------------------------------

SITES.to_csv(OUT_DIR / "sites.csv", index=False)
ROUTES.drop(columns=["route_class"]).to_csv(OUT_DIR / "routes.csv", index=False)
TRUCKS.drop(columns=["truck_type"]).to_csv(OUT_DIR / "trucks.csv", index=False)
DRIVERS.to_csv(OUT_DIR / "drivers.csv", index=False)
pd.DataFrame(trips).to_csv(OUT_DIR / "trips.csv", index=False)
pd.DataFrame(downtime_events).to_csv(OUT_DIR / "downtime_events.csv", index=False)
pd.DataFrame(fuel_logs).to_csv(OUT_DIR / "fuel_logs.csv", index=False)
pd.DataFrame(deliveries).to_csv(OUT_DIR / "deliveries.csv", index=False)

print(f"Simulated {START_DATE} to {END_DATE} ({NUM_DAYS} days) for {len(TRUCKS)} trucks.")
print(f"  trips:            {len(trips):,}")
print(f"  deliveries:       {len(deliveries):,}")
print(f"  downtime_events:  {len(downtime_events):,}")
print(f"  fuel_logs:        {len(fuel_logs):,}")
print(f"Output written to {OUT_DIR}")