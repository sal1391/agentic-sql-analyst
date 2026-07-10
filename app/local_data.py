"""Deterministic fake marine-fuel transaction data for demo mode.

Generates ~12k inquiry rows (Jan 2025 - Jun 2026) with the exact schema of
skills/references/data-model.md, plus planted storylines so the AI narrative
has real movements to find:
  - CHURNED_CUSTOMER: a top customer with no activity after 2026-03
  - NEW_CUSTOMER: appears 2026-01 and ramps up
  - SPIKE_PORT: volume roughly doubles from 2026-02 (new contract)
  - COMPRESSED_REGION: EMEA margins compressed ~25% from 2026-01
Fixed RNG seed => identical data on every boot; demo numbers never shift.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

SEED = 42
MONTHS = pd.date_range("2025-01-01", "2026-06-01", freq="MS")

CHURNED_CUSTOMER = "Meridian Bulk Carriers"
NEW_CUSTOMER = "Aurora Container Line"
SPIKE_PORT = "Fujairah"
COMPRESSED_REGION = "EMEA"

SHIP_TYPES = ["Tanker", "Bulker", "Container", "Cruise"]

CUSTOMERS = [
    ("Meridian Bulk Carriers", "Bulker"), ("Aurora Container Line", "Container"),
    ("Pacific Star Lines", "Container"), ("Nordwind Tankers", "Tanker"),
    ("Blue Horizon Shipping", "Bulker"), ("Golden Wake Cruises", "Cruise"),
    ("Ironclad Maritime", "Bulker"), ("Sable Point Tankers", "Tanker"),
    ("Corsair Container Co", "Container"), ("Trident Bay Lines", "Container"),
    ("Halcyon Voyages", "Cruise"), ("Kestrel Marine Group", "Tanker"),
    ("Windward Freight", "Bulker"), ("Deepwater Carriers", "Tanker"),
    ("Starboard Logistics", "Container"), ("Albatross Lines", "Bulker"),
    ("Neptune Crest Shipping", "Tanker"), ("Coral Route Cruises", "Cruise"),
    ("Ostend Maritime", "Container"), ("Vela Ocean Transport", "Bulker"),
    ("Harborlight Shipping", "Container"), ("Polaris Tanker Group", "Tanker"),
    ("Mistral Navigation", "Bulker"), ("Seaborne Atlas", "Container"),
    ("Crescent Wave Lines", "Cruise"), ("Bastion Marine", "Tanker"),
    ("Longitude Carriers", "Bulker"), ("Amber Coast Shipping", "Container"),
    ("Silverfin Maritime", "Tanker"), ("Boreal Star Lines", "Container"),
    ("Cobalt Seas Group", "Bulker"), ("Marlin Cross Shipping", "Tanker"),
    ("Zephyr Ocean Lines", "Container"), ("Quayside Carriers", "Bulker"),
    ("Lodestar Marine", "Tanker"), ("Verdant Wave Co", "Container"),
    ("Cape Meridian Lines", "Bulker"), ("Solstice Cruises", "Cruise"),
    ("Argent Tide Shipping", "Tanker"), ("Falcon Reach Maritime", "Container"),
]

SUPPLIERS = [
    "Nordfuel Energy", "Harbor Energy", "Petromar Bunkering", "Gulf Anchor Fuels",
    "Atlas Marine Oil", "Beacon Bunkers", "Cordova Petroleum", "Delta Wave Energy",
    "Evergreen Bunkering", "Foreshore Fuels", "Gannet Oil Trading", "Helios Marine Energy",
    "Ironside Petroleum", "Jetty Line Fuels", "Kraken Energy Co",
]

# port -> supply region
PORTS = {
    "Singapore": "APAC", "Hong Kong": "APAC", "Busan": "APAC", "Shanghai": "APAC",
    "Tokyo Bay": "APAC", "Port Klang": "APAC", "Colombo": "APAC",
    "Rotterdam": "EMEA", "Antwerp": "EMEA", "Gibraltar": "EMEA", "Piraeus": "EMEA",
    "Fujairah": "EMEA", "Malta": "EMEA", "Algeciras": "EMEA", "Istanbul": "EMEA",
    "Durban": "EMEA", "Suez": "EMEA",
    "Houston": "Americas", "New Orleans": "Americas", "Miami": "Americas",
    "New York": "Americas", "Los Angeles": "Americas", "Santos": "Americas",
    "Panama City": "Americas", "Vancouver": "Americas",
}

# office -> region
OFFICES = {
    "Houston": "Americas", "Miami": "Americas",
    "Rotterdam": "EMEA", "Athens": "EMEA",
    "Singapore": "APAC",
}

# broker -> office
BROKERS = {
    "J. Calloway": "Houston", "M. Reyes": "Houston", "T. Whitfield": "Houston",
    "D. Okafor": "Houston", "S. Lindqvist": "Miami", "R. Beaumont": "Miami",
    "A. Castellanos": "Miami", "P. Vandermeer": "Rotterdam", "H. Bakker": "Rotterdam",
    "L. Janssen": "Rotterdam", "F. de Vries": "Rotterdam", "K. Papadopoulos": "Athens",
    "N. Stavros": "Athens", "E. Makris": "Athens", "C. Tan": "Singapore",
    "W. Lim": "Singapore", "Y. Nakamura": "Singapore", "G. Fernandez": "Singapore",
    "B. Halvorsen": "Rotterdam", "V. Moreau": "Athens",
}

DEAL_TYPES = ["TRADED", "INVENTORY", "BROKERED"]
DEAL_WEIGHTS = [0.60, 0.25, 0.15]

# mean delivered tons per won lift, by vessel ship type
VOLUME_MEAN = {"Tanker": 900.0, "Bulker": 700.0, "Container": 500.0, "Cruise": 1200.0}


def build_demo_frame() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    broker_names = list(BROKERS.keys())

    # Per-customer stable characteristics
    profiles = []
    for name, ship_type in CUSTOMERS:
        n_ports = int(rng.integers(3, 7))
        profiles.append({
            "name": name,
            "ship_type": ship_type,
            "ports": list(rng.choice(list(PORTS.keys()), size=n_ports, replace=False)),
            "base_lam": 30.0 if name == CHURNED_CUSTOMER else float(rng.uniform(10, 24)),
            "win_rate": float(rng.uniform(0.45, 0.75)),
            "account_broker": str(rng.choice(broker_names)),
        })

    rows = []
    lift_seq = 0
    for month_idx, month_start in enumerate(MONTHS):
        month_start_date = month_start.date()
        days_in_month = (month_start + pd.offsets.MonthEnd(0)).day
        seasonality = 1.0 + 0.15 * np.sin(2 * np.pi * (month_start.month - 1) / 12.0)

        for prof in profiles:
            name = prof["name"]
            # Storyline: churn — no activity after March 2026
            if name == CHURNED_CUSTOMER and month_start_date > dt.date(2026, 3, 1):
                continue
            # Storyline: new customer — appears Jan 2026 and ramps
            if name == NEW_CUSTOMER:
                if month_start_date < dt.date(2026, 1, 1):
                    continue
                ramp_idx = (month_start.year - 2026) * 12 + month_start.month - 1
                lam = 6.0 + 5.0 * ramp_idx
            else:
                lam = prof["base_lam"] * seasonality

            n_inquiries = int(rng.poisson(lam))
            for _ in range(n_inquiries):
                port = str(rng.choice(prof["ports"]))
                # Storyline: port spike — extra Fujairah share from Feb 2026
                if (month_start_date >= dt.date(2026, 2, 1)
                        and port != SPIKE_PORT and rng.random() < 0.08):
                    port = SPIKE_PORT
                lift_seq += 1
                rows.append(_make_row(rng, prof, port, month_start, days_in_month,
                                      lift_seq))

    df = pd.DataFrame(rows)
    return df.reset_index(drop=True)


def _make_row(rng, prof, port, month_start, days_in_month, seq) -> dict:
    supply_region = PORTS[port]
    won = rng.random() < prof["win_rate"]

    if won:
        vessel_type = prof["ship_type"] if rng.random() < 0.85 else str(rng.choice(SHIP_TYPES))
        mean_vol = VOLUME_MEAN[vessel_type]
        volume = float(np.round(rng.gamma(shape=4.0, scale=mean_vol / 4.0), 2))
        margin = float(np.clip(rng.normal(28.0, 8.0), 8.0, 60.0))
        # Storyline: EMEA margin compression from Jan 2026
        if supply_region == COMPRESSED_REGION and month_start.date() >= dt.date(2026, 1, 1):
            margin *= 0.75
        gp = float(np.round(volume * margin, 2))
    else:
        vessel_type = prof["ship_type"]
        volume, gp = 0.0, 0.0

    day = int(rng.integers(1, days_in_month + 1))
    delivery = dt.date(month_start.year, month_start.month, day)

    # Brokers: account broker is stable per customer; customer broker usually the same
    account_broker = prof["account_broker"]
    customer_broker = account_broker if rng.random() < 0.8 else str(rng.choice(list(BROKERS.keys())))
    # Supply broker sits in an office within the port's supply region
    region_offices = [o for o, r in OFFICES.items() if r == supply_region]
    supply_office = str(rng.choice(region_offices))
    supply_brokers = [b for b, o in BROKERS.items() if o == supply_office]
    supply_broker = str(rng.choice(supply_brokers))

    return {
        "LIFT_ID": f"LIFT-{seq:06d}",
        "WON_FLAG": 1.0 if won else 0.0,
        "INQUIRY_FLAG": 1.0,
        "DELIVERY_DATE": delivery,
        "GROSS_PROFIT": gp,
        "VOLUME_TONS": volume,
        "CUSTOMER_NAME": prof["name"],
        "SUPPLIER_NAME": str(rng.choice(SUPPLIERS)),
        "PORT_NAME": port,
        "SUPPLY_REGION": supply_region,
        "SUPPLY_BROKER": supply_broker,
        "SUPPLY_TEAM_OFFICE": supply_office,
        "SUPPLY_TEAM_REGION": supply_region,
        "ACCOUNT_BROKER": account_broker,
        "ACCOUNT_BROKER_OFFICE": BROKERS[account_broker],
        "ACCOUNT_BROKER_REGION": OFFICES[BROKERS[account_broker]],
        "CUSTOMER_BROKER": customer_broker,
        "CUSTOMER_BROKER_OFFICE": BROKERS[customer_broker],
        "CUSTOMER_BROKER_REGION": OFFICES[BROKERS[customer_broker]],
        "DEAL_TYPE": str(rng.choice(DEAL_TYPES, p=DEAL_WEIGHTS)),
        "VESSEL_SHIP_TYPE": vessel_type,
        "CUSTOMER_SHIP_TYPE": prof["ship_type"],
    }
