"""Fake demo data: schema, determinism, metric integrity, planted storylines."""
import pandas as pd
import pytest

from app.local_data import (
    CHURNED_CUSTOMER,
    COMPRESSED_REGION,
    NEW_CUSTOMER,
    SPIKE_PORT,
    build_demo_frame,
)

EXPECTED_COLUMNS = [
    "LIFT_ID", "WON_FLAG", "INQUIRY_FLAG", "DELIVERY_DATE", "GROSS_PROFIT",
    "VOLUME_TONS", "CUSTOMER_NAME", "SUPPLIER_NAME", "PORT_NAME",
    "SUPPLY_REGION", "SUPPLY_BROKER", "SUPPLY_TEAM_OFFICE",
    "SUPPLY_TEAM_REGION", "ACCOUNT_BROKER", "ACCOUNT_BROKER_OFFICE",
    "ACCOUNT_BROKER_REGION", "CUSTOMER_BROKER", "CUSTOMER_BROKER_OFFICE",
    "CUSTOMER_BROKER_REGION", "DEAL_TYPE", "VESSEL_SHIP_TYPE",
    "CUSTOMER_SHIP_TYPE",
]


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return build_demo_frame()


def test_exact_schema(df):
    assert list(df.columns) == EXPECTED_COLUMNS


def test_row_count_and_date_span(df):
    assert 8_000 <= len(df) <= 16_000
    dates = pd.to_datetime(df["DELIVERY_DATE"])
    assert dates.min() >= pd.Timestamp("2025-01-01")
    assert dates.max() <= pd.Timestamp("2026-06-30")
    assert dates.dt.to_period("M").nunique() == 18


def test_deterministic(df):
    again = build_demo_frame()
    pd.testing.assert_frame_equal(df, again)


def test_metric_integrity(df):
    assert (df["INQUIRY_FLAG"] == 1.0).all()
    assert set(df["WON_FLAG"].unique()) == {0.0, 1.0}
    lost = df[df["WON_FLAG"] == 0.0]
    assert (lost["VOLUME_TONS"] == 0.0).all()
    assert (lost["GROSS_PROFIT"] == 0.0).all()
    won = df[df["WON_FLAG"] == 1.0]
    assert (won["VOLUME_TONS"] > 0).all()
    assert (won["GROSS_PROFIT"] > 0).all()
    win_rate = df["WON_FLAG"].mean()
    assert 0.45 <= win_rate <= 0.75
    assert df["LIFT_ID"].is_unique


def test_storyline_churned_customer(df):
    rows = df[df["CUSTOMER_NAME"] == CHURNED_CUSTOMER]
    assert not rows.empty
    row_dates = pd.to_datetime(rows["DELIVERY_DATE"])
    assert (row_dates <= pd.Timestamp("2026-03-31")).all()
    # was active in its final month
    assert (row_dates.dt.to_period("M") == pd.Period("2026-03")).any()


def test_storyline_new_customer(df):
    rows = df[df["CUSTOMER_NAME"] == NEW_CUSTOMER]
    assert not rows.empty
    row_dates = pd.to_datetime(rows["DELIVERY_DATE"])
    assert (row_dates >= pd.Timestamp("2026-01-01")).all()


def test_storyline_port_spike(df):
    port = df[df["PORT_NAME"] == SPIKE_PORT]
    port_periods = pd.to_datetime(port["DELIVERY_DATE"]).dt.to_period("M")
    before = port[port_periods == pd.Period("2026-01")]["VOLUME_TONS"].sum()
    after = port[port_periods == pd.Period("2026-03")]["VOLUME_TONS"].sum()
    assert after > before * 1.5


def test_storyline_margin_compression(df):
    won = df[(df["WON_FLAG"] == 1.0) & (df["SUPPLY_REGION"] == COMPRESSED_REGION)].copy()
    won["MONTH"] = pd.to_datetime(won["DELIVERY_DATE"]).dt.to_period("M")
    margin = lambda sub: sub["GROSS_PROFIT"].sum() / sub["VOLUME_TONS"].sum()  # noqa: E731
    pre = margin(won[won["MONTH"] == pd.Period("2025-11")])
    post = margin(won[won["MONTH"] == pd.Period("2026-02")])
    assert post < pre * 0.9
