"""
Snowflake client — session management, query execution, and Cortex LLM calls.
"""
import streamlit as st
import pandas as pd
from snowflake.snowpark import Session
try:
    from app.config import SNOWFLAKE_CONNECTION, CORTEX_MODEL, FULLY_QUALIFIED_TABLE, DEPLOY_MODE
except ImportError:
    from config import SNOWFLAKE_CONNECTION, CORTEX_MODEL, FULLY_QUALIFIED_TABLE, DEPLOY_MODE


def get_session() -> Session:
    """Create and return a Snowpark Session from config.

    In SiS mode, uses st.connection('snowflake') instead of manual config.
    """
    if DEPLOY_MODE == "sis":
        return st.connection("snowflake").session()
    return Session.builder.configs(SNOWFLAKE_CONNECTION).create()


@st.cache_data(ttl=600, show_spinner=False)
def get_available_months(_session: Session) -> list[str]:
    """Return distinct months from the data, most recent first."""
    sql = f"""
        SELECT DISTINCT DATE_TRUNC('MONTH', DELIVERY_DATE) AS MONTH
        FROM {FULLY_QUALIFIED_TABLE}
        WHERE DELIVERY_DATE IS NOT NULL
        ORDER BY MONTH DESC
    """
    try:
        df = _session.sql(sql).to_pandas()
    except Exception as exc:
        message = str(exc)
        if "does not exist or not authorized" in message:
            raise RuntimeError(
                "Snowflake table not found or access denied for "
                f"{FULLY_QUALIFIED_TABLE}. Update SNOWFLAKE_DATABASE, "
                "SNOWFLAKE_SCHEMA, and SNOWFLAKE_TABLE in .env, or verify "
                "your role has access."
            ) from exc
        raise
    # Normalize the MONTH column regardless of whether Snowflake returns
    # a date, datetime, or string type
    months = pd.to_datetime(df["MONTH"], errors="coerce").dropna()
    return months.dt.strftime("%Y-%m-%d").tolist()


@st.cache_data(ttl=3600, show_spinner=False)
def get_table_columns(_session: Session) -> list[str]:
    """Return the actual column names from the Snowflake table/view."""
    sql = f"SELECT * FROM {FULLY_QUALIFIED_TABLE} LIMIT 0"
    df = _session.sql(sql).to_pandas()
    return list(df.columns)


def execute_query(session: Session, sql: str) -> pd.DataFrame:
    """Execute a SQL query and return results as a pandas DataFrame.

    Only SELECT statements are allowed — any DDL/DML is rejected.
    """
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        raise ValueError("Only SELECT/WITH queries are allowed.")

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                 "TRUNCATE", "MERGE", "GRANT", "REVOKE"]
    for keyword in forbidden:
        # Check for the keyword as a standalone word (not inside a string literal)
        if f" {keyword} " in f" {stripped} ":
            raise ValueError(f"Forbidden SQL keyword detected: {keyword}")

    return session.sql(sql).to_pandas()


def call_cortex_complete(session: Session, prompt: str, model: str = None) -> str:
    """Call Snowflake Cortex LLM completion."""
    model = model or CORTEX_MODEL
    safe_prompt = prompt.replace("'", "''")
    query = f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', '{safe_prompt}') AS CONTENT"
    result = session.sql(query).to_pandas()["CONTENT"][0]
    return result


def log_analysis_error(session: Session, user_question: str,
                       context_json: dict, error_summary: str) -> None:
    """Log an unanswerable question to ANALYSIS_ERROR_SUMMARY.

    Creates the table if it doesn't exist, then inserts a row.
    Uses session.sql() directly (bypasses the SELECT-only execute_query guard).
    """
    table = f"{FULLY_QUALIFIED_TABLE.rsplit('.', 1)[0]}.ANALYSIS_ERROR_SUMMARY"

    create_ddl = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            ID NUMBER AUTOINCREMENT,
            CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
            USER_QUESTION VARCHAR(4000),
            CONTEXT_JSON VARIANT,
            ERROR_SUMMARY VARCHAR(4000)
        )
    """
    try:
        session.sql(create_ddl).collect()
    except Exception:
        pass  # table may already exist or role lacks CREATE — try insert anyway

    import json as _json
    safe_question = user_question.replace("'", "''")
    safe_context = _json.dumps(context_json).replace("'", "''")
    safe_summary = error_summary.replace("'", "''")

    insert_sql = f"""
        INSERT INTO {table} (USER_QUESTION, CONTEXT_JSON, ERROR_SUMMARY)
        SELECT
            '{safe_question}',
            PARSE_JSON('{safe_context}'),
            '{safe_summary}'
    """
    session.sql(insert_sql).collect()
