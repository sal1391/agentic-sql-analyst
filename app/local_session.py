"""In-process DuckDB session that quacks like the Snowpark Session the agent uses.

The agent and snowflake_client helpers only ever call `session.sql(q).to_pandas()`
(or `.collect()` for DDL they try/except). DuckDB runs the agent's Snowflake-dialect
SQL verbatim, and an attached database named SANDBOX with schema ANALYTICS makes the
fully qualified table name resolve unchanged.
"""
from __future__ import annotations

import duckdb

try:
    from app.local_data import build_demo_frame
except ImportError:
    from local_data import build_demo_frame


class _Result:
    def __init__(self, df):
        self._df = df

    def to_pandas(self):
        return self._df

    def collect(self):
        return []


class LocalSession:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        self._con = con

    def sql(self, query: str) -> _Result:
        # cursor() gives a per-call connection: safe across Streamlit sessions/threads
        cur = self._con.cursor()
        try:
            return _Result(cur.execute(query).df())
        finally:
            cur.close()


def get_local_session() -> LocalSession:
    con = duckdb.connect(":memory:")
    con.execute("ATTACH ':memory:' AS SANDBOX")
    con.execute("CREATE SCHEMA SANDBOX.ANALYTICS")
    df = build_demo_frame()
    con.register("demo_df", df)
    con.execute("CREATE TABLE SANDBOX.ANALYTICS.SALES_ACTUALS_V AS SELECT * FROM demo_df")
    con.unregister("demo_df")
    return LocalSession(con)
