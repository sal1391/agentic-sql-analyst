"""
MoM Comparison App Configuration
==================================
Supports: local | aws | sis
Set DEPLOY_MODE via environment variable or .streamlit/secrets.toml.
"""
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    # python-dotenv not available (e.g. Streamlit-in-Snowflake)
    pass


def _get_config(key: str, default: str = "") -> str:
    """Read a config value from env vars, falling back to st.secrets (SiS)."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

# ============================================================
# DEPLOYMENT MODE
# ============================================================
DEPLOY_MODE = _get_config("DEPLOY_MODE", "demo")  # "demo" | "local" | "aws" | "sis"
IS_DEMO = DEPLOY_MODE == "demo"

# ============================================================
# LLM PROVIDER CONFIG
# ============================================================
LLM_PROVIDER = _get_config("LLM_PROVIDER", "cortex")  # "cortex" | "azure"
CORTEX_MODEL = _get_config("CORTEX_MODEL", "claude-sonnet-4-5")

# Azure AI Foundry — fill in when ready
AZURE_ENDPOINT = _get_config("AZURE_ENDPOINT")
AZURE_API_KEY = _get_config("AZURE_API_KEY")
AZURE_MODEL = _get_config("AZURE_MODEL")

# ============================================================
# DEMO MODE — OpenAI-backed analyst (provider hidden from users)
# ============================================================
OPENAI_API_KEY = _get_config("OPENAI_API_KEY")
OPENAI_MODEL = _get_config("OPENAI_MODEL", "gpt-4o-mini")
GUARDRAIL_MODEL = "gpt-4o-mini"  # topic classifier — always the cheap model

# ============================================================
# LOCAL MODE — Reads credentials from environment variables
# ============================================================
SNOWFLAKE_DATABASE = _get_config("SNOWFLAKE_DATABASE", "SANDBOX")
SNOWFLAKE_SCHEMA = _get_config("SNOWFLAKE_SCHEMA", "ANALYTICS")
SNOWFLAKE_TABLE = _get_config("SNOWFLAKE_TABLE", "SALES_ACTUALS_V")

_LOCAL_SNOWFLAKE_CONNECTION = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT", ""),
    "user": os.getenv("SNOWFLAKE_USER", ""),
    "password": os.getenv("SNOWFLAKE_PASSWORD", ""),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", ""),
    "database": SNOWFLAKE_DATABASE,
    "schema": SNOWFLAKE_SCHEMA,
    "role": os.getenv("SNOWFLAKE_ROLE", ""),
}

FULLY_QUALIFIED_TABLE = f"{SNOWFLAKE_DATABASE}.{SNOWFLAKE_SCHEMA}.{SNOWFLAKE_TABLE}"


# ============================================================
# AWS MODE — Retrieves secrets from AWS Secrets Manager
# ============================================================
def _get_secret(secret_name):
    """Fetch a secret from AWS Secrets Manager and return as dict."""
    import boto3
    region_name = os.getenv("AWS_REGION", "us-east-1")
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)
    resp = client.get_secret_value(SecretId=secret_name)
    secret = resp["SecretString"]
    return json.loads(secret)


# ============================================================
# RESOLVED CONFIG — Used by the rest of the app
# ============================================================
if DEPLOY_MODE == "demo":
    # Demo mode: DuckDB + built-in data, no Snowflake at all
    SNOWFLAKE_CONNECTION = None
elif DEPLOY_MODE == "local":
    SNOWFLAKE_CONNECTION = _LOCAL_SNOWFLAKE_CONNECTION
elif DEPLOY_MODE == "sis":
    # Streamlit-in-Snowflake: session comes from st.connection("snowflake")
    SNOWFLAKE_CONNECTION = None
else:
    SNOWFLAKE_CONNECTION = _get_secret("mom_comparison_secret_json")
