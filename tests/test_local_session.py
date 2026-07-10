"""LocalSession: agent-style Snowflake SQL must run verbatim on DuckDB."""
import pandas as pd  # noqa: F401
import pytest

from app.local_session import get_local_session
from app.snowflake_client import execute_query, get_available_months, get_table_columns

TABLE = "SANDBOX.ANALYTICS.SALES_ACTUALS_V"

COMPARISON_SQL = f"""
SELECT
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER_NAME,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM {TABLE}
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-03-01'
GROUP BY CUSTOMER_NAME
ORDER BY GP DESC
"""

QUOTED_FLAGS_SQL = f"""
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT_NAME,
    SUM("WON_FLAG") AS WON,
    SUM("INQUIRY_FLAG") AS INQUIRIES
FROM {TABLE}
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY PORT_NAME
"""

DIAGNOSTIC_SQL = f"""
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE
FROM {TABLE}
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND PORT_NAME IN ('Singapore', 'Rotterdam', 'Fujairah')
GROUP BY DEAL_TYPE
HAVING SUM(INQUIRY_FLAG) >= 5
ORDER BY WIN_RATE ASC
"""


@pytest.fixture(scope="module")
def session():
    return get_local_session()


def test_comparison_query_runs_verbatim(session):
    df = session.sql(COMPARISON_SQL).to_pandas()
    assert list(df.columns) == ["CUSTOMER_NAME", "VOLUME", "GP", "MARGIN", "WON", "INQUIRIES", "LOST"]
    assert len(df) > 5
    assert (df["INQUIRIES"] >= df["WON"]).all()


def test_quoted_flag_columns(session):
    df = session.sql(QUOTED_FLAGS_SQL).to_pandas()
    assert not df.empty


def test_diagnostic_where_in_having(session):
    df = session.sql(DIAGNOSTIC_SQL).to_pandas()
    assert set(df["DEAL_CLASS"]).issubset({"TRADED", "INVENTORY", "BROKERED", "Unknown"})
    assert (df["WIN_RATE"].dropna() <= 1.0).all()


def test_snowflake_client_helpers_work_on_local_session(session):
    months = get_available_months(session)
    assert months[0] == "2026-06-01"   # most recent first
    assert months[-1] == "2025-01-01"
    assert len(months) == 18

    cols = get_table_columns(session)
    assert "CUSTOMER_NAME" in cols and "WON_FLAG" in cols and len(cols) == 22

    df = execute_query(session, f"SELECT COUNT(*) AS N FROM {TABLE}")
    assert df["N"][0] > 8000


def test_execute_query_still_blocks_ddl(session):
    with pytest.raises(ValueError):
        execute_query(session, f"DROP TABLE {TABLE}")


def test_collect_parity(session):
    assert session.sql(f"SELECT 1 AS X FROM {TABLE} LIMIT 1").collect() == []
