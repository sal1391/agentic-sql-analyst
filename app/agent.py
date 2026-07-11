"""
Agent Orchestrator — the brain of the MoM comparison app.

Two-turn LLM flow:
  Turn 1: Generate SQL from skill context + user request
  Turn 2: Analyze query results and produce KPIs + narrative

Supports both Snowflake Cortex and Azure AI Foundry as LLM providers.
"""
import json
import logging
import re
import pandas as pd
try:
    from snowflake.snowpark import Session
except ImportError:  # demo installs without Snowpark — Session is only a type hint here
    Session = None

logger = logging.getLogger(__name__)

try:
    from app.skill_loader import load_skill_tree
    from app.snowflake_client import execute_query, call_cortex_complete, get_table_columns, get_available_months, log_analysis_error
    from app.azure_client import call_azure_complete
    from app.openai_client import call_openai_complete
    from app.config import FULLY_QUALIFIED_TABLE, IS_DEMO
    from app.demo_log import log_event
except ImportError:
    from skill_loader import load_skill_tree
    from snowflake_client import execute_query, call_cortex_complete, get_table_columns, get_available_months, log_analysis_error
    from azure_client import call_azure_complete
    from openai_client import call_openai_complete
    from config import FULLY_QUALIFIED_TABLE, IS_DEMO
    from demo_log import log_event


# ── Dimension mapping (column → friendly name) ──────────────────────────

DIMENSIONS = {
    "CUSTOMER_NAME": "Customer",
    "SUPPLIER_NAME": "Supplier",
    "PORT_NAME": "Port",
    "SUPPLY_REGION": "Supply Region",
    "SUPPLY_BROKER": "Supply Broker",
    "SUPPLY_TEAM_OFFICE": "Supply Team Office",
    "SUPPLY_TEAM_REGION": "Supply Team Region",
    "ACCOUNT_BROKER": "Primary Broker",
    "ACCOUNT_BROKER_OFFICE": "Primary Broker Office",
    "ACCOUNT_BROKER_REGION": "Primary Broker Region",
    "CUSTOMER_BROKER": "Customer Broker",
    "CUSTOMER_BROKER_OFFICE": "Customer Broker Office",
    "CUSTOMER_BROKER_REGION": "Customer Broker Region",
    "DEAL_TYPE": "Deal Class",
}

METRICS = ["VOLUME", "GP", "MARGIN", "WON", "INQUIRIES", "LOST"]


# ── Deterministic KPI computation ────────────────────────────────────────

def _compute_kpis(df_a: pd.DataFrame, df_b: pd.DataFrame) -> dict:
    """Compute summary KPIs from the full dataframes (not truncated).

    This avoids the LLM computing different totals when dimensions change,
    since the totals are the same regardless of grouping.
    """
    def _safe_sum(df, col):
        if col in df.columns:
            return float(df[col].sum())
        return 0.0

    def _kpi(label, val_a, val_b):
        change = val_b - val_a
        pct = (change / val_a * 100) if val_a else 0.0
        return {"month_a": val_a, "month_b": val_b, "change": change, "pct_change": pct}

    vol_a = _safe_sum(df_a, "VOLUME")
    vol_b = _safe_sum(df_b, "VOLUME")
    gp_a = _safe_sum(df_a, "GP")
    gp_b = _safe_sum(df_b, "GP")
    margin_a = (gp_a / vol_a) if vol_a else 0.0
    margin_b = (gp_b / vol_b) if vol_b else 0.0
    won_a = _safe_sum(df_a, "WON")
    won_b = _safe_sum(df_b, "WON")
    inq_a = _safe_sum(df_a, "INQUIRIES")
    inq_b = _safe_sum(df_b, "INQUIRIES")
    lost_a = _safe_sum(df_a, "LOST")
    lost_b = _safe_sum(df_b, "LOST")

    return {
        "volume": _kpi("volume", vol_a, vol_b),
        "gp": _kpi("gp", gp_a, gp_b),
        "margin": _kpi("margin", margin_a, margin_b),
        "won": _kpi("won", won_a, won_b),
        "inquiries": _kpi("inquiries", inq_a, inq_b),
        "lost": _kpi("lost", lost_a, lost_b),
    }


# ── Deterministic new/lost computation ─────────────────────────────────────

def _compute_new_lost(df_a: pd.DataFrame, df_b: pd.DataFrame,
                      dimensions: list[str]) -> dict:
    """Identify dimension groups that are new in Month B or lost from Month A.

    Returns:
        {"new": [...], "lost": [...]}
        Each entry: {"dimensions": {col: val, ...}, "gp": float, "volume": float, "margin": float}
        Lists sorted by GP descending (biggest impact first).
    """
    def _safe_sum(df, col):
        if col in df.columns:
            return float(df[col].sum())
        return 0.0

    def _build_key(row, dims):
        return tuple(str(row.get(d, "")) for d in dims)

    # Aggregate by dimension group
    agg_cols = {}
    for col in ["GP", "VOLUME", "MARGIN"]:
        if col == "MARGIN":
            continue  # compute from GP/VOLUME
        if col in df_a.columns or col in df_b.columns:
            agg_cols[col] = "sum"

    def _aggregate(df, dims):
        if df.empty:
            return {}
        present_dims = [d for d in dims if d in df.columns]
        if not present_dims:
            return {}
        grouped = df.groupby(present_dims, dropna=False).agg(
            {c: "sum" for c in agg_cols if c in df.columns}
        ).reset_index()
        result = {}
        for _, row in grouped.iterrows():
            key = tuple(str(row.get(d, "")) for d in present_dims)
            gp = float(row.get("GP", 0))
            vol = float(row.get("VOLUME", 0))
            margin = (gp / vol) if vol else 0.0
            result[key] = {
                "dimensions": {d: str(row.get(d, "")) for d in present_dims},
                "gp": round(gp, 2),
                "volume": round(vol, 2),
                "margin": round(margin, 2),
            }
        return result

    present_dims = [d for d in dimensions if d in df_a.columns or d in df_b.columns]
    agg_a = _aggregate(df_a, present_dims)
    agg_b = _aggregate(df_b, present_dims)

    keys_a = set(agg_a.keys())
    keys_b = set(agg_b.keys())

    new_keys = keys_b - keys_a
    lost_keys = keys_a - keys_b

    new_list = sorted([agg_b[k] for k in new_keys],
                      key=lambda x: abs(x["gp"]), reverse=True)
    lost_list = sorted([agg_a[k] for k in lost_keys],
                       key=lambda x: abs(x["gp"]), reverse=True)

    return {"new": new_list, "lost": lost_list}


# ── Deterministic top movers computation ──────────────────────────────────

def _compute_top_movers(df_a: pd.DataFrame, df_b: pd.DataFrame,
                        dimensions: list[str], n: int = 5) -> dict:
    """Compute top N increases and decreases by GP absolute change.

    Returns:
        {"increases": [...], "decreases": [...]}
        Each entry: {
            "dimensions": {col: val, ...},
            "gp":     {"a": float, "b": float, "change": float, "pct": float},
            "volume": {"a": float, "b": float, "change": float, "pct": float},
            "margin": {"a": float, "b": float, "change": float, "pct": float},
            "driver": "volume-driven" | "margin-driven" | "both"
        }
    """
    present_dims = [d for d in dimensions
                    if d in df_a.columns or d in df_b.columns]
    if not present_dims:
        return {"increases": [], "decreases": []}

    def _agg(df, suffix):
        if df.empty:
            return pd.DataFrame()
        cols_to_agg = {}
        for c in ["GP", "VOLUME"]:
            if c in df.columns:
                cols_to_agg[c] = "sum"
        if not cols_to_agg:
            return pd.DataFrame()
        grouped = df.groupby(present_dims, dropna=False).agg(cols_to_agg).reset_index()
        grouped = grouped.rename(columns={c: f"{c}_{suffix}" for c in cols_to_agg})
        return grouped

    agg_a = _agg(df_a, "a")
    agg_b = _agg(df_b, "b")

    if agg_a.empty and agg_b.empty:
        return {"increases": [], "decreases": []}

    merged = pd.merge(agg_a, agg_b, on=present_dims, how="outer").fillna(0)

    # Compute metrics
    merged["gp_change"] = merged.get("GP_b", 0) - merged.get("GP_a", 0)
    merged["vol_change"] = merged.get("VOLUME_b", 0) - merged.get("VOLUME_a", 0)
    merged["margin_a"] = merged.apply(
        lambda r: (r.get("GP_a", 0) / r.get("VOLUME_a", 0))
                  if r.get("VOLUME_a", 0) else 0.0, axis=1)
    merged["margin_b"] = merged.apply(
        lambda r: (r.get("GP_b", 0) / r.get("VOLUME_b", 0))
                  if r.get("VOLUME_b", 0) else 0.0, axis=1)
    merged["margin_change"] = merged["margin_b"] - merged["margin_a"]

    def _pct(change, base):
        return (change / abs(base) * 100) if base else 0.0

    def _classify_driver(row):
        """Determine whether GP change was volume-driven, margin-driven, or both."""
        vol_a = row.get("VOLUME_a", 0)
        vol_b = row.get("VOLUME_b", 0)
        margin_a_val = row["margin_a"]
        margin_b_val = row["margin_b"]
        # Volume effect: change in volume at old margin
        vol_effect = (vol_b - vol_a) * margin_a_val if margin_a_val else 0
        # Margin effect: change in margin at new volume
        margin_effect = (margin_b_val - margin_a_val) * vol_b if vol_b else 0
        abs_vol = abs(vol_effect)
        abs_margin = abs(margin_effect)
        if abs_vol == 0 and abs_margin == 0:
            return "unchanged"
        ratio = abs_vol / (abs_vol + abs_margin) if (abs_vol + abs_margin) else 0
        if ratio > 0.65:
            return "volume-driven"
        elif ratio < 0.35:
            return "margin-driven"
        else:
            return "both"

    rows = []
    for _, r in merged.iterrows():
        dims_dict = {d: str(r.get(d, "")) for d in present_dims}
        gp_a = float(r.get("GP_a", 0))
        gp_b = float(r.get("GP_b", 0))
        vol_a = float(r.get("VOLUME_a", 0))
        vol_b = float(r.get("VOLUME_b", 0))
        m_a = float(r["margin_a"])
        m_b = float(r["margin_b"])
        rows.append({
            "dimensions": dims_dict,
            "gp": {"a": round(gp_a, 2), "b": round(gp_b, 2),
                    "change": round(gp_b - gp_a, 2),
                    "pct": round(_pct(gp_b - gp_a, gp_a), 1)},
            "volume": {"a": round(vol_a, 2), "b": round(vol_b, 2),
                       "change": round(vol_b - vol_a, 2),
                       "pct": round(_pct(vol_b - vol_a, vol_a), 1)},
            "margin": {"a": round(m_a, 2), "b": round(m_b, 2),
                       "change": round(m_b - m_a, 2),
                       "pct": round(_pct(m_b - m_a, m_a), 1)},
            "driver": _classify_driver(r),
        })

    # Sort by GP absolute change
    sorted_rows = sorted(rows, key=lambda x: x["gp"]["change"], reverse=True)
    increases = [r for r in sorted_rows if r["gp"]["change"] > 0][:n]
    decreases = [r for r in sorted_rows if r["gp"]["change"] < 0]
    decreases = sorted(decreases, key=lambda x: x["gp"]["change"])[:n]

    return {"increases": increases, "decreases": decreases}


# ── LLM call dispatcher ─────────────────────────────────────────────────

def _call_llm(prompt: str, provider: str, session: Session = None,
              model: str = None) -> str:
    """Route the prompt to the selected LLM provider."""
    if provider == "cortex":
        if session is None:
            raise ValueError("Snowflake session required for Cortex provider.")
        return call_cortex_complete(session, prompt, model=model)
    elif provider == "azure":
        return call_azure_complete(prompt, model=model)
    elif provider == "openai":
        return call_openai_complete(prompt, model=model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# ── SQL extraction ───────────────────────────────────────────────────────

# Common LLM hallucinations → correct column name
_COLUMN_CORRECTIONS = {
    r"\bINQUIRY_ID\b": 'INQUIRY_FLAG',
    r"\bINQUIRY_COUNT\b": 'INQUIRY_FLAG',
    r"\bNUM_INQUIRIES\b": 'INQUIRY_FLAG',
    r"\bTRANSACTIONS_WON\b": 'WON_FLAG',
    r"\bFIXTURE_STATUS\b": 'WON_FLAG',
    r"\bFIXTURES\b": 'WON_FLAG',
    r"\bFIXTURE\b": 'WON_FLAG',
    r"\bIS_WON\b": 'WON_FLAG',
    r"\bGROSS_PROFIT_AMOUNT\b": "GROSS_PROFIT",
    r"\bGP_AMOUNT\b": "GROSS_PROFIT",
    r"\bTONS\b": "VOLUME_TONS",
    r"\bETA_DATE\b": "DELIVERY_DATE",
    r"\bCUSTOMER_NM\b": "CUSTOMER_NAME",
    r"\bPORT_NM\b": "PORT_NAME",
}

# Expression-level corrections (full expression replacements)
_EXPRESSION_CORRECTIONS = [
    # SUM(INQUIRIES) - SUM(FIXTURES) → SUM(INQUIRY_FLAG) - SUM(WON_FLAG)
    (r"SUM\s*\(\s*INQUIRIES\s*\)\s*-\s*SUM\s*\(\s*FIXTURES\s*\)",
     'SUM(INQUIRY_FLAG)-SUM(WON_FLAG)'),
    # SUM(INQUIRIES) anywhere → SUM(INQUIRY_FLAG)
    (r"SUM\s*\(\s*INQUIRIES\s*\)", 'SUM(INQUIRY_FLAG)'),
    # COUNT(*) AS INQUIRIES → SUM(INQUIRY_FLAG) AS INQUIRIES
    (r"COUNT\s*\(\s*\*\s*\)\s*AS\s+INQUIRIES", 'SUM(INQUIRY_FLAG) AS INQUIRIES'),
    # COUNT(*)-SUM(WON_FLAG) → SUM(INQUIRY_FLAG)-SUM(WON_FLAG)
    (r'COUNT\s*\(\s*\*\s*\)\s*-\s*SUM\s*\(\s*WON_FLAG\s*\)',
     'SUM(INQUIRY_FLAG)-SUM(WON_FLAG)'),
    # SUM(STATUS) → SUM(WON_FLAG)
    (r"SUM\s*\(\s*STATUS\s*\)", 'SUM(WON_FLAG)'),
    # WHERE STATUS = 1 → WHERE WON_FLAG = 1  (numeric filter)
    (r"\bSTATUS\s*=\s*1\b", 'WON_FLAG = 1'),
    # WHERE STATUS = 0 → WHERE WON_FLAG = 0
    (r"\bSTATUS\s*=\s*0\b", 'WON_FLAG = 0'),
    # WHERE STATUS = 'WON' or 'won' → WHERE WON_FLAG = 1
    (r"\bSTATUS\s*=\s*'(?:WON|won|Won)'\s*", 'WON_FLAG = 1 '),
    # WHERE STATUS = 'LOST' or 'lost' → WHERE WON_FLAG = 0
    (r"\bSTATUS\s*=\s*'(?:LOST|lost|Lost)'\s*", 'WON_FLAG = 0 '),
    # Unquoted INQUIRY_FLAG / WON_FLAG → add double quotes
    (r'SUM\s*\(\s*INQUIRY_FLAG\s*\)', 'SUM(INQUIRY_FLAG)'),
    (r'SUM\s*\(\s*WON_FLAG\s*\)', 'SUM(WON_FLAG)'),
]


def _correct_column_names(sql: str) -> str:
    """Replace hallucinated column names and expressions with correct ones."""
    # Expression corrections first (longer patterns before shorter)
    for pattern, replacement in _EXPRESSION_CORRECTIONS:
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
    # Column name corrections
    for pattern, replacement in _COLUMN_CORRECTIONS.items():
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
    return sql


def _strip_hash_comments(sql: str) -> str:
    """Remove Python-style # comment lines from SQL.

    Snowflake only supports -- and /* */ comments.
    Preserves # inside double-quoted identifiers (e.g. WON_FLAG).
    """
    cleaned = []
    for line in sql.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue  # drop full-line # comments
        # Remove trailing # comments that are NOT inside double quotes
        # Count unescaped double quotes to determine if # is inside a string
        in_quote = False
        result_chars = []
        for ch in line:
            if ch == '"':
                in_quote = not in_quote
            if ch == '#' and not in_quote:
                break  # truncate at inline # comment
            result_chars.append(ch)
        cleaned.append("".join(result_chars).rstrip())
    return "\n".join(cleaned)


def _extract_sql_blocks(llm_response: str) -> list[str]:
    """Extract SQL code blocks from the LLM response."""
    pattern = r"```sql\s*(.*?)```"
    blocks = re.findall(pattern, llm_response, re.DOTALL | re.IGNORECASE)
    if not blocks:
        # Fallback: split on SELECT boundaries (handles back-to-back queries
        # without code fences or semicolons).
        parts = re.split(r"(?=(?:^|\n)\s*SELECT\s)", llm_response,
                         flags=re.IGNORECASE)
        blocks = []
        for part in parts:
            m = re.search(r"(SELECT\s+.+)", part,
                          re.DOTALL | re.IGNORECASE)
            if m:
                blocks.append(m.group(1).rstrip(";").strip())
    results = []
    for i, b in enumerate(blocks):
        if not b.strip():
            continue
        raw = b.strip().rstrip(";")
        after_strip = _strip_hash_comments(raw)
        corrected = _correct_column_names(after_strip)
        logger.info("SQL block %d (raw):\n%s", i, raw)
        if after_strip != raw:
            logger.info("SQL block %d (after _strip_hash_comments):\n%s", i, after_strip)
        if corrected != after_strip:
            logger.info("SQL block %d (after _correct_column_names):\n%s", i, corrected)
        logger.info("SQL block %d (final):\n%s", i, corrected)
        results.append(corrected)
    return results


def _extract_new_dates(llm_response: str) -> dict | None:
    """Extract new comparison dates from LLM response.

    Looks for ===NEW_DATES=== {"month_a": "...", "month_b": "..."} ===END_NEW_DATES===
    Returns dict with month_a, month_b keys or None.
    """
    match = re.search(
        r"===NEW_DATES===\s*(.*?)\s*===END_NEW_DATES===",
        llm_response, re.DOTALL
    )
    if not match:
        return None
    try:
        dates = json.loads(match.group(1).strip())
        if "month_a" in dates and "month_b" in dates:
            return dates
    except json.JSONDecodeError:
        pass
    return None


def _extract_error_reason(llm_response: str) -> str | None:
    """Extract the error reason from an LLM response that says CANNOT_ANSWER.

    Looks for ===ERROR_REASON=== ... ===END_ERROR_REASON===
    Returns the 2-sentence explanation or None.
    """
    match = re.search(
        r"===ERROR_REASON===\s*(.*?)\s*===END_ERROR_REASON===",
        llm_response, re.DOTALL
    )
    if match:
        return match.group(1).strip()
    return None


def _parse_analysis(llm_response: str) -> dict:
    """Parse the structured analysis output from the LLM."""
    result = {"kpis": {}, "narrative": "", "top_movers": []}

    # Extract KPI JSON
    kpi_match = re.search(
        r"===KPI_JSON===\s*(.*?)\s*===END_KPI_JSON===",
        llm_response, re.DOTALL
    )
    if kpi_match:
        try:
            result["kpis"] = json.loads(kpi_match.group(1))
        except json.JSONDecodeError:
            result["kpis"] = {}

    # Extract narrative
    narr_match = re.search(
        r"===NARRATIVE===\s*(.*?)\s*===END_NARRATIVE===",
        llm_response, re.DOTALL
    )
    if narr_match:
        result["narrative"] = narr_match.group(1).strip()
    else:
        # Fallback for models that drop the closing marker (or all markers):
        # take everything after ===NARRATIVE=== if present, then strip any
        # structured blocks so raw ===MARKER=== text never reaches the UI.
        text = llm_response
        open_match = re.search(r"===NARRATIVE===\s*(.*)", text, re.DOTALL)
        if open_match:
            text = open_match.group(1)
        text = re.sub(r"===KPI_JSON===.*?(?:===END_KPI_JSON===|\Z)", "",
                      text, flags=re.DOTALL)
        text = re.sub(r"===TOP_MOVERS_JSON===.*?(?:===END_TOP_MOVERS_JSON===|\Z)", "",
                      text, flags=re.DOTALL)
        text = text.replace("===END_NARRATIVE===", "")
        result["narrative"] = text.strip()

    # Extract top movers JSON
    movers_match = re.search(
        r"===TOP_MOVERS_JSON===\s*(.*?)\s*===END_TOP_MOVERS_JSON===",
        llm_response, re.DOTALL
    )
    if movers_match:
        try:
            result["top_movers"] = json.loads(movers_match.group(1))
        except json.JSONDecodeError:
            result["top_movers"] = []

    return result


# ── Turn 1: SQL Generation ──────────────────────────────────────────────

def _build_sql_prompt(month_a: str, month_b: str,
                      dimensions: list[str], actual_columns: list[str]) -> str:
    """Build the prompt for SQL generation using real Snowflake column names."""
    dim_list = ", ".join(dimensions)
    cols_block = "\n".join(f"  {c}" for c in actual_columns)

    return f"""You are a Snowflake SQL expert. Generate TWO SELECT queries.

== TABLE ==
{FULLY_QUALIFIED_TABLE}

== ACTUAL COLUMNS IN THIS TABLE (copied directly from Snowflake — use ONLY these exact names) ==
{cols_block}

== METRIC FORMULAS (copy these exactly — do not rename or invent column names) ==
  SUM(VOLUME_TONS)                                          AS VOLUME
  SUM(GROSS_PROFIT)                                        AS GP
  SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0)              AS MARGIN
  SUM(WON_FLAG)                                        AS WON
  SUM(INQUIRY_FLAG)                                       AS INQUIRIES
  SUM(INQUIRY_FLAG)-SUM(WON_FLAG)                     AS LOST

NOTE: The columns WON_FLAG and INQUIRY_FLAG must be double-quoted because they contain special characters.
There is NO column called FIXTURES (without quotes), FIXTURE_STATUS, INQUIRY_ID, TRANSACTIONS_WON, or STATUS.
Use only the column names listed above — nothing else.

== DATE FILTER ==
  DATE_TRUNC('MONTH', DELIVERY_DATE) = '{{month_date}}'

== REQUEST ==
- Month A date: {month_a}
- Month B date: {month_b}
- GROUP BY: {dim_list} (wrap each in COALESCE(col, 'Unknown'))

== OUTPUT FORMAT ==
Return EXACTLY TWO ```sql``` code blocks. First = Month A. Second = Month B.
No explanations. No DDL. SELECT only."""


# ── Turn 2: Analysis ────────────────────────────────────────────────────

def _build_analysis_prompt(month_a: str, month_b: str,
                           df_a: pd.DataFrame, df_b: pd.DataFrame,
                           dimensions: list[str], playbook: str,
                           computed_kpis: dict = None,
                           computed_top_movers: dict = None,
                           computed_new_lost: dict = None) -> str:
    """Build the prompt for result analysis.

    When pre-computed data is provided, the LLM writes narrative around
    known facts rather than computing them from raw CSV.
    """
    friendly_dims = ", ".join(DIMENSIONS.get(d, d) for d in dimensions)

    # Truncate data to avoid exceeding token limits
    a_str = df_a.head(100).to_csv(index=False)
    b_str = df_b.head(100).to_csv(index=False)

    # Build pre-computed data blocks
    precomputed_block = ""
    if computed_kpis or computed_top_movers or computed_new_lost:
        precomputed_block = "\n== PRE-COMPUTED DATA (use these exact numbers — do NOT recompute) ==\n"

        if computed_kpis:
            precomputed_block += f"\nSUMMARY KPIs:\n{json.dumps(computed_kpis, indent=2)}\n"

        if computed_top_movers:
            precomputed_block += "\nTOP MOVERS BY GP:\n"
            for direction in ["increases", "decreases"]:
                items = computed_top_movers.get(direction, [])
                if items:
                    label = "Top Increases" if direction == "increases" else "Top Decreases"
                    precomputed_block += f"\n  {label}:\n"
                    for i, m in enumerate(items, 1):
                        dim_str = ", ".join(f"{k}={v}" for k, v in m["dimensions"].items())
                        precomputed_block += (
                            f"  {i}. {dim_str}\n"
                            f"     GP: {m['gp']['a']:,.0f} -> {m['gp']['b']:,.0f} "
                            f"(change: {m['gp']['change']:+,.0f}, {m['gp']['pct']:+.1f}%)\n"
                            f"     Volume: {m['volume']['a']:,.0f} -> {m['volume']['b']:,.0f} "
                            f"(change: {m['volume']['change']:+,.0f}, {m['volume']['pct']:+.1f}%)\n"
                            f"     Margin: {m['margin']['a']:.2f} -> {m['margin']['b']:.2f} "
                            f"(change: {m['margin']['change']:+.2f}/ton, {m['margin']['pct']:+.1f}%)\n"
                            f"     Driver: {m['driver']}\n"
                        )

        if computed_new_lost:
            for category in ["new", "lost"]:
                items = computed_new_lost.get(category, [])
                if items:
                    label = f"NEW in {month_b}" if category == "new" else f"LOST from {month_a}"
                    precomputed_block += f"\n  {label} ({len(items)} groups):\n"
                    for entry in items[:10]:  # cap at 10 for prompt size
                        dim_str = ", ".join(f"{k}={v}" for k, v in entry["dimensions"].items())
                        precomputed_block += (
                            f"  - {dim_str}: GP={entry['gp']:,.0f}, "
                            f"Volume={entry['volume']:,.0f}, "
                            f"Margin={entry['margin']:.2f}/ton\n"
                        )
                    if len(items) > 10:
                        precomputed_block += f"  ... and {len(items) - 10} more\n"

    instructions = ""
    if precomputed_block:
        instructions = """
INSTRUCTIONS:
The KPIs, top movers, and new/lost data above have been pre-computed from the FULL dataset.
Do NOT recompute these values. Your job is to:
1. Write a narrative summary that explains and contextualizes the pre-computed data
2. For each top mover, explain whether the change was volume-driven, margin-driven, or both (the driver is provided)
3. Reference the exact numbers provided — do not approximate or round differently
4. Follow the narrative patterns from the playbook"""
    else:
        instructions = """
Follow the analysis patterns from the playbook:
1. Compute changes (absolute and %) for each dimension group
2. Identify top 3 increases and top 3 decreases by GP
3. Note any new or lost dimension groups
4. Generate summary KPIs (totals across all groups)
5. Write a narrative summary"""

    return f"""You are a data analyst. Read the playbook below and analyze the month-over-month changes.

PLAYBOOK:
{playbook}

CONTEXT:
- Month A: {month_a}
- Month B: {month_b}
- Dimensions: {friendly_dims}
- Metrics: Volume (tons), GP ($), Margin ($/ton), Won (#), Inquiries (#), Lost (#)
{precomputed_block}
MONTH A DATA (sample — full data was used for pre-computed values above):
{a_str}

MONTH B DATA (sample — full data was used for pre-computed values above):
{b_str}
{instructions}

IMPORTANT FORMATTING RULE: Do NOT use bare $ signs anywhere in the narrative text.
The output is rendered in Streamlit which interprets $...$ as LaTeX math.
Write dollar amounts as plain numbers (e.g., "700" or "1,200") without a $ prefix.

Return your output in this EXACT format:
===KPI_JSON===
{{...}}
===END_KPI_JSON===

===NARRATIVE===
...markdown narrative...
===END_NARRATIVE==="""


# ── Follow-up question ──────────────────────────────────────────────────

def _extract_top_values(df_a: pd.DataFrame, df_b: pd.DataFrame,
                        n: int = 10) -> dict:
    """Deterministically extract top dimension values from drilldown data.

    Merges Month A and B on all non-metric columns, computes GP change,
    and returns the top N increases and decreases with their exact values.

    Returns:
        {
            "dimension_cols": [str, ...],
            "increases": [{"dims": {col: val}, "gp_change": float}, ...],
            "decreases": [{"dims": {col: val}, "gp_change": float}, ...],
        }
    """
    metric_cols = {"VOLUME", "GP", "MARGIN", "WON", "INQUIRIES", "LOST"}
    dim_cols_a = [c for c in df_a.columns if c not in metric_cols]
    dim_cols_b = [c for c in df_b.columns if c not in metric_cols]
    dim_cols = dim_cols_a if dim_cols_a else dim_cols_b
    if not dim_cols:
        return {"dimension_cols": [], "increases": [], "decreases": []}

    def _agg(df, suffix):
        if df.empty or "GP" not in df.columns:
            return pd.DataFrame()
        present = [c for c in dim_cols if c in df.columns]
        if not present:
            return pd.DataFrame()
        grouped = df.groupby(present, dropna=False).agg({"GP": "sum"}).reset_index()
        grouped = grouped.rename(columns={"GP": f"GP_{suffix}"})
        return grouped

    agg_a = _agg(df_a, "a")
    agg_b = _agg(df_b, "b")
    present = [c for c in dim_cols if c in agg_a.columns or c in agg_b.columns]
    if not present:
        return {"dimension_cols": dim_cols, "increases": [], "decreases": []}

    if agg_a.empty and agg_b.empty:
        return {"dimension_cols": dim_cols, "increases": [], "decreases": []}
    elif agg_a.empty:
        merged = agg_b.copy()
        merged["GP_a"] = 0
    elif agg_b.empty:
        merged = agg_a.copy()
        merged["GP_b"] = 0
    else:
        merged = pd.merge(agg_a, agg_b, on=present, how="outer").fillna(0)

    merged["gp_change"] = merged["GP_b"] - merged["GP_a"]
    sorted_up = merged.sort_values("gp_change", ascending=False)
    sorted_down = merged.sort_values("gp_change", ascending=True)

    def _to_list(df_sorted, limit):
        items = []
        for _, row in df_sorted.head(limit).iterrows():
            items.append({
                "dims": {c: str(row[c]) for c in present},
                "gp_change": round(float(row["gp_change"]), 2),
            })
        return items

    return {
        "dimension_cols": present,
        "increases": _to_list(sorted_up[sorted_up["gp_change"] > 0], n),
        "decreases": _to_list(sorted_down[sorted_down["gp_change"] < 0], n),
    }


def _build_followup_prompt(question: str, month_a: str, month_b: str,
                           df_a: pd.DataFrame, df_b: pd.DataFrame,
                           dimensions: list[str], actual_columns: list[str],
                           chat_history: list[dict] = None,
                           prev_drilldown: dict = None) -> str:
    """Build prompt for a follow-up question.

    The prompt supplies the full table schema, all available dimensions,
    chat history, and — when available — the previous drilldown DataFrames
    so the LLM can generate SQL for *any* dimension with deterministic
    context from prior follow-ups.
    """
    friendly_dims = ", ".join(DIMENSIONS.get(d, d) for d in dimensions)
    a_str = df_a.head(100).to_csv(index=False)
    b_str = df_b.head(100).to_csv(index=False)
    cols_block = "\n".join(f"  {c}" for c in actual_columns)
    all_dims_block = "\n".join(f"  {col} — {label}" for col, label in DIMENSIONS.items())

    history_block = ""
    if chat_history:
        history_block = "CONVERSATION HISTORY:\n"
        for msg in chat_history[-10:]:
            role = msg.get("role", "user").upper()
            history_block += f"{role}: {msg.get('content', '')}\n"
        history_block += "\n"

    # Build deterministic previous-drilldown context
    prev_drilldown_block = ""
    if prev_drilldown and prev_drilldown.get("df_a") is not None and prev_drilldown.get("df_b") is not None:
        prev_df_a = prev_drilldown["df_a"]
        prev_df_b = prev_drilldown["df_b"]
        top_vals = _extract_top_values(prev_df_a, prev_df_b)
        dim_names = top_vals["dimension_cols"]

        prev_drilldown_block = (
            f"\n== PREVIOUS DRILLDOWN RESULTS ==\n"
            f"(from the prior follow-up question: \"{prev_drilldown.get('question', '')}\")\n\n"
        )
        prev_drilldown_block += f"PREVIOUS DRILLDOWN — MONTH A DATA:\n{prev_df_a.head(50).to_csv(index=False)}\n\n"
        prev_drilldown_block += f"PREVIOUS DRILLDOWN — MONTH B DATA:\n{prev_df_b.head(50).to_csv(index=False)}\n\n"

        if top_vals["increases"] or top_vals["decreases"]:
            prev_drilldown_block += "== DETERMINISTIC TOP VALUES FROM PREVIOUS DRILLDOWN (sorted by GP change) ==\n"
            if top_vals["increases"]:
                prev_drilldown_block += f"\nTop {len(top_vals['increases'])} INCREASES by GP:\n"
                increase_values = []
                for i, item in enumerate(top_vals["increases"], 1):
                    dim_str = ", ".join(f"{k}={v}" for k, v in item["dims"].items())
                    prev_drilldown_block += f"  {i}. {dim_str} (GP change: {item['gp_change']:+,.0f})\n"
                    # Collect the primary dimension values for the WHERE IN hint
                    if dim_names:
                        increase_values.append(item["dims"].get(dim_names[0], ""))
                if dim_names and increase_values:
                    quoted_vals = ", ".join(f"'{v}'" for v in increase_values if v)
                    prev_drilldown_block += (
                        f"\n  ** USE THESE EXACT VALUES for contextual drilldown WHERE IN clauses: **\n"
                        f"  Column: {dim_names[0]}\n"
                        f"  Increase values: {quoted_vals}\n"
                    )
            if top_vals["decreases"]:
                prev_drilldown_block += f"\nTop {len(top_vals['decreases'])} DECREASES by GP:\n"
                decrease_values = []
                for i, item in enumerate(top_vals["decreases"], 1):
                    dim_str = ", ".join(f"{k}={v}" for k, v in item["dims"].items())
                    prev_drilldown_block += f"  {i}. {dim_str} (GP change: {item['gp_change']:+,.0f})\n"
                    if dim_names:
                        decrease_values.append(item["dims"].get(dim_names[0], ""))
                if dim_names and decrease_values:
                    quoted_vals = ", ".join(f"'{v}'" for v in decrease_values if v)
                    prev_drilldown_block += (
                        f"\n  ** USE THESE EXACT VALUES for contextual drilldown WHERE IN clauses: **\n"
                        f"  Column: {dim_names[0]}\n"
                        f"  Decrease values: {quoted_vals}\n"
                    )
            prev_drilldown_block += "\n"

    return f"""You are a Snowflake SQL expert AND data analyst. The user is looking at a month-over-month comparison and has a follow-up question.

== TABLE ==
{FULLY_QUALIFIED_TABLE}

== ACTUAL COLUMNS (use ONLY these exact names) ==
{cols_block}

== ALL AVAILABLE DIMENSIONS ==
{all_dims_block}

== METRIC FORMULAS ==
  SUM(VOLUME_TONS)                                          AS VOLUME
  SUM(GROSS_PROFIT)                                        AS GP
  SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0)              AS MARGIN
  SUM(WON_FLAG)                                        AS WON
  SUM(INQUIRY_FLAG)                                       AS INQUIRIES
  SUM(INQUIRY_FLAG)-SUM(WON_FLAG)                     AS LOST

== CURRENT COMPARISON ==
- Month A: {month_a}
- Month B: {month_b}
- Initial dimensions: {friendly_dims}

MONTH A DATA:
{a_str}

MONTH B DATA:
{b_str}

{history_block}{prev_drilldown_block}USER QUESTION: {question}

INSTRUCTIONS:
1. If you can answer from the data above, answer directly with specific numbers.
2. DIMENSION INHERITANCE: When generating drilldown SQL, DEFAULT to the same
   dimensions listed in "Initial dimensions" above UNLESS the user explicitly
   requests different ones. If the user asks for ADDITIONAL dimensions (e.g.,
   "also break by port", "add deal type"), ADD that dimension to the existing
   ones rather than replacing them. Only switch to entirely different dimensions
   if the user clearly asks for a different view (e.g., "show me by supplier
   instead").
3. If the user asks about a DIFFERENT dimension (e.g., "show me by supplier"), generate
   TWO sql code blocks (Month A and Month B) grouped by that dimension, using the
   same metric formulas and date filters above, then say NEEDS_DRILLDOWN on a separate line.
4. If the user asks "why" about a specific value, generate a drilldown query and say NEEDS_DRILLDOWN.
5. If the user asks about top movers AND what drove them (e.g., "which ports grew
   the most and which customers were responsible?"), generate TWO queries (Month A
   and Month B) with a multi-dimension GROUP BY that includes BOTH the mover
   dimension and the attribution dimension. Always query BOTH months so changes
   can be computed. Say NEEDS_DRILLDOWN on a separate line.
6. CONTEXTUAL DRILLDOWN: If the user references previous drilldown results (e.g.,
   "from the Top 10 ports, what customers?" or "break that down by deal type"),
   you MUST use the DETERMINISTIC TOP VALUES provided in the
   "PREVIOUS DRILLDOWN RESULTS" section above. Copy the exact values into a
   WHERE IN clause — do NOT re-derive them from chat history text.
   Generate TWO queries (Month A and B) with the WHERE IN filter and group by the
   new dimension (and optionally keep the old dimension for attribution).
   Say NEEDS_DRILLDOWN on a separate line.
7. Always use the exact column names from the ACTUAL COLUMNS list.
8. Do NOT invent column names. The columns WON_FLAG and INQUIRY_FLAG must be double-quoted.
9. There is NO column called FIXTURES (without quotes), STATUS, FIXTURE_STATUS, INQUIRY_ID, or TRANSACTIONS_WON.
10. DIAGNOSTIC QUESTIONS: If the user asks about a specific metric (lost activity,
   won activity, GP drop/increase, volume change, margin, win rate, conversion),
   generate queries that ORDER BY the relevant metric — NOT always GP DESC.
   Metric mapping:
   - "lost activity" / "where did I lose"       → ORDER BY LOST DESC  (most losses first)
   - "won activity" / "where did I win"          → ORDER BY WON DESC   (most wins first)
   - "GP dropped" / "worst GP" / "lost GP"       → ORDER BY GP ASC     (lowest GP first)
   - "GP increased" / "best GP"                  → ORDER BY GP DESC
   - "volume dropped" / "lost volume"            → ORDER BY VOLUME ASC
   - "volume increased" / "most volume"          → ORDER BY VOLUME DESC
   - "worst margin" / "margin dropped"           → ORDER BY MARGIN ASC
   - "lowest win rate" / "worst conversion"      → ORDER BY WIN_RATE ASC
   - "best win rate" / "highest conversion"      → ORDER BY WIN_RATE DESC
   Include WIN_RATE as: SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE
   For rate metrics (win rate, margin), add HAVING SUM(INQUIRY_FLAG) >= 5 to filter noise.
   If the user specifies a filter (e.g., a customer name), apply it as a WHERE clause
   and break down by a secondary dimension.
   Generate TWO queries (Month A and B) for MoM context unless the user asks about
   a single month specifically. Say NEEDS_DRILLDOWN on a separate line.

EXAMPLE DRILLDOWN QUERY 1 — single dimension:
SELECT
    COALESCE(CUSTOMER_BROKER_OFFICE, 'Unknown') AS CUSTOMER_BROKER_OFFICE,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM """ + FULLY_QUALIFIED_TABLE + """
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
GROUP BY CUSTOMER_BROKER_OFFICE
ORDER BY GP DESC

EXAMPLE DRILLDOWN QUERY 2 — chained multi-dimension (e.g. port + customer):
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT_NAME,
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER_NAME,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM """ + FULLY_QUALIFIED_TABLE + """
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
GROUP BY PORT_NAME, CUSTOMER_NAME
ORDER BY GP DESC

EXAMPLE DRILLDOWN QUERY 3 — Contextual Drilldown (applying previous chat result context):
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM """ + FULLY_QUALIFIED_TABLE + """
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
  AND PORT_NAME IN ('SINGAPORE', 'NEDERLAND', 'TAMPA')
GROUP BY DEAL_TYPE
ORDER BY GP DESC

EXAMPLE DRILLDOWN QUERY 4 — Diagnostic: lost activity for a customer by port:
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE
FROM """ + FULLY_QUALIFIED_TABLE + """
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
  AND CUSTOMER_NAME = '{customer_name}'
GROUP BY PORT_NAME
ORDER BY LOST DESC

EXAMPLE DRILLDOWN QUERY 5 — Diagnostic: lowest win rate by dimension:
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE
FROM """ + FULLY_QUALIFIED_TABLE + f"""
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{{month}}'
GROUP BY DEAL_TYPE
HAVING SUM(INQUIRY_FLAG) >= 5
ORDER BY WIN_RATE ASC

10. DATE CHANGE REQUEST: If the user asks to compare DIFFERENT months than the
   current comparison (e.g., "compare to March 2025", "what about vs last year",
   "show me 2025-03-01 instead"), you MUST:
   a. Determine the two new months to compare. If the user only specifies one
      month, keep the other month from the current comparison. For example:
      - Current: Feb 2026 vs Mar 2026. User says "compare to March 2025" →
        New: Mar 2025 vs Mar 2026 (keeping the current Month B, replacing Month A).
      - User says "compare Feb 2025 to Feb 2026" → New: Feb 2025 vs Feb 2026.
   b. Output the new dates in this format on separate lines:
      ===NEW_DATES===
      {{"month_a": "YYYY-MM-01", "month_b": "YYYY-MM-01"}}
      ===END_NEW_DATES===
   c. Generate TWO ```sql``` code blocks for the new date pair (Month A and Month B)
      using the SAME dimensions as the current comparison.
   d. Say NEEDS_DATE_CHANGE on a separate line.
   e. Do NOT say NEEDS_DRILLDOWN — use NEEDS_DATE_CHANGE instead.
11. COMBINED DATE + DIMENSION REQUEST: If the user asks for BOTH a different date
   range AND specific dimensions in one question (e.g., "show me top customers
   and deal types between 2025-03-01 and 2026-03-01"), you MUST:
   a. Determine the two months from the user's request.
   b. Output the new dates in the ===NEW_DATES=== format (same as rule 10b).
   c. Generate TWO ```sql``` code blocks for the new date pair, grouped by the
      requested dimensions (or the current "Initial dimensions" if unspecified).
   d. Say NEEDS_DATE_AND_DRILLDOWN on a separate line.
   e. Do NOT say NEEDS_DRILLDOWN or NEEDS_DATE_CHANGE — use NEEDS_DATE_AND_DRILLDOWN.
12. FOLLOW-UP DATE INHERITANCE: If the user's follow-up does NOT mention specific
   dates (e.g., "break this down by port as well", "can I also see deal type?"),
   you MUST use the CURRENT COMPARISON dates shown above (Month A: {month_a},
   Month B: {month_b}). These dates reflect the most recent comparison, including
   any prior date changes in this conversation. Do NOT revert to different dates.
13. AMBIGUOUS DIMENSION REQUEST: If you cannot determine which dimension(s) the
   user wants (e.g., "show me a different breakdown", "slice it another way"),
   do NOT guess. Instead, list the available dimensions from the ALL AVAILABLE
   DIMENSIONS section above and ask the user to pick. Format as a numbered list
   so the user can reply by number or name. Example response:
   "Which dimension(s) would you like to group by? Here are the available options:
   1. CUSTOMER_NAME — Customer
   2. PORT_NAME — Port
   3. DEAL_TYPE — Deal Type
   ... (list all)"
   Do NOT output NEEDS_DRILLDOWN, NEEDS_DATE_CHANGE, or any SQL in this case.
14. If you CANNOT answer the question from the available data, dimensions, or
   metric formulas — for example, the user asks about data not in this table,
   asks for a type of analysis not supported, or references columns/concepts
   that don't exist — respond with your best explanation of why you can't answer,
   then output on separate lines:
   CANNOT_ANSWER
   ===ERROR_REASON===
   {{Two sentences: (1) what the user asked for, (2) specifically why the agent
   could not fulfill it and what would need to change.}}
   ===END_ERROR_REASON===

Provide a detailed markdown answer with specific numbers."""


# ── Public API ───────────────────────────────────────────────────────────

def run_comparison(session: Session, month_a: str, month_b: str,
                   dimensions: list[str], provider: str,
                   model: str = None) -> dict:
    """Run the full two-turn MoM comparison.

    Returns:
        {
            "kpis": dict,
            "narrative": str,
            "top_movers": dict (increases/decreases with GP/Volume/Margin),
            "new_lost": dict (new/lost dimension groups with metrics),
            "df_a": DataFrame,
            "df_b": DataFrame,
            "sql_a": str,
            "sql_b": str,
        }
    """
    playbook = load_skill_tree()
    actual_columns = get_table_columns(session)

    # ── Turn 1: Generate SQL ──
    sql_prompt = _build_sql_prompt(month_a, month_b, dimensions, actual_columns)
    sql_response = _call_llm(sql_prompt, provider, session=session, model=model)
    sql_blocks = _extract_sql_blocks(sql_response)

    if len(sql_blocks) < 2:
        raise ValueError(
            f"LLM returned {len(sql_blocks)} SQL block(s), expected 2. "
            f"Response:\n{sql_response}"
        )

    sql_a, sql_b = sql_blocks[0], sql_blocks[1]
    _debug_sql = {"sql_a_raw": sql_a, "sql_b_raw": sql_b}

    # ── Execute queries ──
    try:
        df_a = execute_query(session, sql_a)
    except Exception as e:
        logger.error("SQL A failed: %s\nQuery:\n%s", e, sql_a)
        # One retry: send error back to LLM
        retry_prompt = (
            f"The SQL query failed with error: {e}\n\n"
            f"Original query:\n```sql\n{sql_a}\n```\n\n"
            f"Fix the query and return a corrected version in a ```sql``` block."
        )
        retry_response = _call_llm(retry_prompt, provider, session=session,
                                   model=model)
        retry_blocks = _extract_sql_blocks(retry_response)
        if retry_blocks:
            sql_a = retry_blocks[0]
            logger.info("SQL A retry:\n%s", sql_a)
            df_a = execute_query(session, sql_a)
        else:
            raise

    try:
        df_b = execute_query(session, sql_b)
    except Exception as e:
        logger.error("SQL B failed: %s\nQuery:\n%s", e, sql_b)
        retry_prompt = (
            f"The SQL query failed with error: {e}\n\n"
            f"Original query:\n```sql\n{sql_b}\n```\n\n"
            f"Fix the query and return a corrected version in a ```sql``` block."
        )
        retry_response = _call_llm(retry_prompt, provider, session=session,
                                   model=model)
        retry_blocks = _extract_sql_blocks(retry_response)
        if retry_blocks:
            sql_b = retry_blocks[0]
            logger.info("SQL B retry:\n%s", sql_b)
            df_b = execute_query(session, sql_b)
        else:
            raise

    _debug_sql["sql_a_final"] = sql_a
    _debug_sql["sql_b_final"] = sql_b

    # ── Deterministic computations (from full data, not truncated) ──
    computed_kpis = _compute_kpis(df_a, df_b)
    computed_new_lost = _compute_new_lost(df_a, df_b, dimensions)
    computed_top_movers = _compute_top_movers(df_a, df_b, dimensions)

    # ── Turn 2: Analyze results (LLM writes narrative around pre-computed data) ──
    analysis_prompt = _build_analysis_prompt(
        month_a, month_b, df_a, df_b, dimensions, playbook,
        computed_kpis=computed_kpis,
        computed_top_movers=computed_top_movers,
        computed_new_lost=computed_new_lost,
    )
    analysis_response = _call_llm(analysis_prompt, provider, session=session,
                                  model=model)
    parsed = _parse_analysis(analysis_response)

    return {
        "kpis": computed_kpis,
        "narrative": parsed["narrative"],
        "top_movers": computed_top_movers,
        "new_lost": computed_new_lost,
        "df_a": df_a,
        "df_b": df_b,
        "sql_a": sql_a,
        "sql_b": sql_b,
        "_debug_sql": _debug_sql,
    }


def run_followup(session: Session, question: str, month_a: str, month_b: str,
                 df_a: pd.DataFrame, df_b: pd.DataFrame,
                 dimensions: list[str], provider: str,
                 model: str = None,
                 chat_history: list[dict] = None,
                 prev_drilldown: dict = None) -> dict:
    """Handle a follow-up question from the user.

    The LLM can query ANY dimension (not just the initial ones) because the
    prompt includes the full column list and all available dimensions.

    Args:
        prev_drilldown: dict with keys df_a, df_b, sql, question from the
            last drilldown follow-up.  Used for deterministic context.

    Returns:
        {
            "answer": str,           # markdown text
            "drilldown_sql": str,    # if a drilldown was needed
            "drilldown_df": DataFrame,  # drilldown results (concatenated)
            "drilldown_df_a": DataFrame,  # month A drilldown results
            "drilldown_df_b": DataFrame,  # month B drilldown results
            "date_change": bool,     # True if a date re-comparison was performed
            "new_month_a": str,      # new month A (if date_change)
            "new_month_b": str,      # new month B (if date_change)
            "new_kpis": dict,        # KPIs for new comparison (if date_change)
            "new_top_movers": dict,  # top movers for new comparison (if date_change)
            "new_new_lost": dict,    # new/lost for new comparison (if date_change)
            "logged_error": bool,    # True if the question was logged as unanswerable
        }
    """
    actual_columns = get_table_columns(session)

    prompt = _build_followup_prompt(
        question, month_a, month_b, df_a, df_b, dimensions,
        actual_columns, chat_history=chat_history,
        prev_drilldown=prev_drilldown,
    )
    response = _call_llm(prompt, provider, session=session, model=model)

    result = {"answer": response, "drilldown_sql": None, "drilldown_df": None,
              "drilldown_df_a": None, "drilldown_df_b": None,
              "date_change": False, "new_month_a": None, "new_month_b": None,
              "new_kpis": None, "new_top_movers": None, "new_new_lost": None,
              "logged_error": False}

    # ── Branch 0: Combined date change + drilldown ─────────────────
    if "NEEDS_DATE_AND_DRILLDOWN" in response:
        new_dates = _extract_new_dates(response)
        sql_blocks = _extract_sql_blocks(response)

        if new_dates and sql_blocks:
            new_month_a = new_dates["month_a"]
            new_month_b = new_dates["month_b"]

            # Validate months
            available = get_available_months(session)
            missing = []
            if new_month_a not in available:
                missing.append(new_month_a)
            if new_month_b not in available:
                missing.append(new_month_b)
            if missing:
                result["answer"] = (
                    f"The requested month(s) **{', '.join(missing)}** are not available "
                    f"in the data. Available months range from {available[-1]} to {available[0]}."
                )
                return result

            # Build schema context for retry prompts
            cols_block = "\n".join(f"  {c}" for c in actual_columns)
            schema_context = (
                f"== TABLE ==\n{FULLY_QUALIFIED_TABLE}\n\n"
                f"== ACTUAL COLUMNS (use ONLY these exact names) ==\n"
                f"{cols_block}\n\n"
                f"== METRIC FORMULAS ==\n"
                f"  SUM(VOLUME_TONS)                                          AS VOLUME\n"
                f"  SUM(GROSS_PROFIT)                                        AS GP\n"
                f"  SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0)              AS MARGIN\n"
                f'  SUM(WON_FLAG)                                        AS WON\n'
                f'  SUM(INQUIRY_FLAG)                                       AS INQUIRIES\n'
                f'  SUM(INQUIRY_FLAG)-SUM(WON_FLAG)                     AS LOST\n\n'
                f"NOTE: The columns \"WON_FLAG\" and \"INQUIRY_FLAG\" must be double-quoted.\n"
                f"There is NO column called FIXTURES (without quotes), STATUS, FIXTURE_STATUS, "
                f"INQUIRY_ID, or TRANSACTIONS_WON.\n"
                f"Use only the column names listed above."
            )

            # Execute the SQL blocks for the new date pair
            dfs = []
            for sql in sql_blocks[:2]:
                try:
                    dfs.append(execute_query(session, sql))
                except Exception as e:
                    retry_prompt = (
                        f"The SQL query failed with error: {e}\n\n"
                        f"Original query:\n```sql\n{sql}\n```\n\n"
                        f"{schema_context}\n\n"
                        f"Fix the query using ONLY the columns listed above "
                        f"and return a corrected version in a ```sql``` block."
                    )
                    retry_resp = _call_llm(retry_prompt, provider,
                                           session=session, model=model)
                    retry_blocks = _extract_sql_blocks(retry_resp)
                    if retry_blocks:
                        dfs.append(execute_query(session, retry_blocks[0]))
                    else:
                        raise

            if len(dfs) == 2:
                new_df_a, new_df_b = dfs[0], dfs[1]

                # Deterministic computations on the new data
                new_kpis = _compute_kpis(new_df_a, new_df_b)
                new_top_movers = _compute_top_movers(new_df_a, new_df_b, dimensions)
                new_new_lost = _compute_new_lost(new_df_a, new_df_b, dimensions)

                # Build analysis narrative for the drilldown results
                history_context = ""
                if chat_history:
                    history_context = "CONVERSATION CONTEXT:\n"
                    for msg in chat_history[-5:]:
                        role = msg.get("role", "user").upper()
                        history_context += f"{role}: {msg.get('content', '')}\n"
                    history_context += "\n"

                data_block = (
                    f"MONTH A DATA ({new_month_a}):\n{new_df_a.head(100).to_csv(index=False)}\n\n"
                    f"MONTH B DATA ({new_month_b}):\n{new_df_b.head(100).to_csv(index=False)}"
                )
                followup_prompt = (
                    f"{history_context}"
                    f"The user asked: '{question}'\n\n"
                    f"{data_block}\n\n"
                    f"INSTRUCTIONS:\n"
                    f"1. If there are two datasets (Month A and Month B), compute the change "
                    f"for each group between months.\n"
                    f"2. Identify the top movers (biggest increases and decreases).\n"
                    f"3. If data contains multiple dimensions, first summarize at the higher "
                    f"level, then break down what drove each top mover.\n"
                    f"4. Cite specific numbers. Never use bare $ signs.\n"
                    f"5. Answer the user's SPECIFIC question — focus on what they asked for.\n"
                    f"Provide a concise markdown analysis answering the user's question."
                )
                final_response = _call_llm(followup_prompt, provider,
                                           session=session, model=model)

                result["answer"] = final_response
                result["date_change"] = True
                result["new_month_a"] = new_month_a
                result["new_month_b"] = new_month_b
                result["new_kpis"] = new_kpis
                result["new_top_movers"] = new_top_movers
                result["new_new_lost"] = new_new_lost
                result["drilldown_df_a"] = new_df_a
                result["drilldown_df_b"] = new_df_b
                result["drilldown_df"] = pd.concat([new_df_a, new_df_b], ignore_index=True)
                result["drilldown_sql"] = "\n---\n".join(sql_blocks[:2])
            else:
                result["answer"] = (
                    "I could not generate both queries for the new date comparison. "
                    "Please try rephrasing your request."
                )
        else:
            result["answer"] = (
                "I understood you want a different date comparison with specific dimensions "
                "but couldn't parse the dates. Please specify like: "
                "'show me top customers between March 2025 and March 2026'."
            )
        return result

    # ── Branch 1: Date change request ────────────────────────────────
    if "NEEDS_DATE_CHANGE" in response:
        new_dates = _extract_new_dates(response)
        sql_blocks = _extract_sql_blocks(response)

        if new_dates and sql_blocks:
            new_month_a = new_dates["month_a"]
            new_month_b = new_dates["month_b"]

            # Validate that the requested months exist in the data
            available = get_available_months(session)
            missing = []
            if new_month_a not in available:
                missing.append(new_month_a)
            if new_month_b not in available:
                missing.append(new_month_b)
            if missing:
                result["answer"] = (
                    f"The requested month(s) **{', '.join(missing)}** are not available "
                    f"in the data. Available months range from {available[-1]} to {available[0]}."
                )
                return result

            # Build schema context for retry prompts
            cols_block = "\n".join(f"  {c}" for c in actual_columns)
            schema_context = (
                f"== TABLE ==\n{FULLY_QUALIFIED_TABLE}\n\n"
                f"== ACTUAL COLUMNS (use ONLY these exact names) ==\n"
                f"{cols_block}\n\n"
                f"== METRIC FORMULAS ==\n"
                f"  SUM(VOLUME_TONS)                                          AS VOLUME\n"
                f"  SUM(GROSS_PROFIT)                                        AS GP\n"
                f"  SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0)              AS MARGIN\n"
                f'  SUM(WON_FLAG)                                        AS WON\n'
                f'  SUM(INQUIRY_FLAG)                                       AS INQUIRIES\n'
                f'  SUM(INQUIRY_FLAG)-SUM(WON_FLAG)                     AS LOST\n\n'
                f"NOTE: The columns \"WON_FLAG\" and \"INQUIRY_FLAG\" must be double-quoted.\n"
                f"There is NO column called FIXTURES (without quotes), STATUS, FIXTURE_STATUS, "
                f"INQUIRY_ID, or TRANSACTIONS_WON.\n"
                f"Use only the column names listed above."
            )

            # Execute the two SQL blocks for the new date pair
            dfs = []
            for sql in sql_blocks[:2]:
                try:
                    dfs.append(execute_query(session, sql))
                except Exception as e:
                    retry_prompt = (
                        f"The SQL query failed with error: {e}\n\n"
                        f"Original query:\n```sql\n{sql}\n```\n\n"
                        f"{schema_context}\n\n"
                        f"Fix the query using ONLY the columns listed above "
                        f"and return a corrected version in a ```sql``` block."
                    )
                    retry_resp = _call_llm(retry_prompt, provider,
                                           session=session, model=model)
                    retry_blocks = _extract_sql_blocks(retry_resp)
                    if retry_blocks:
                        dfs.append(execute_query(session, retry_blocks[0]))
                    else:
                        raise

            if len(dfs) == 2:
                new_df_a, new_df_b = dfs[0], dfs[1]

                # Deterministic computations on the new data
                new_kpis = _compute_kpis(new_df_a, new_df_b)
                new_top_movers = _compute_top_movers(new_df_a, new_df_b, dimensions)
                new_new_lost = _compute_new_lost(new_df_a, new_df_b, dimensions)

                # Build analysis narrative for the new comparison
                playbook = load_skill_tree()
                analysis_prompt = _build_analysis_prompt(
                    new_month_a, new_month_b, new_df_a, new_df_b,
                    dimensions, playbook,
                    computed_kpis=new_kpis,
                    computed_top_movers=new_top_movers,
                    computed_new_lost=new_new_lost,
                )
                analysis_response = _call_llm(analysis_prompt, provider,
                                              session=session, model=model)
                parsed = _parse_analysis(analysis_response)

                result["answer"] = parsed["narrative"]
                result["date_change"] = True
                result["new_month_a"] = new_month_a
                result["new_month_b"] = new_month_b
                result["new_kpis"] = new_kpis
                result["new_top_movers"] = new_top_movers
                result["new_new_lost"] = new_new_lost
                result["drilldown_df_a"] = new_df_a
                result["drilldown_df_b"] = new_df_b
                result["drilldown_df"] = pd.concat([new_df_a, new_df_b], ignore_index=True)
                result["drilldown_sql"] = "\n---\n".join(sql_blocks[:2])
            else:
                result["answer"] = (
                    "I could not generate both queries for the new date comparison. "
                    "Please try rephrasing your request."
                )
        else:
            result["answer"] = (
                "I understood you want a different date comparison but couldn't "
                "parse the dates. Please specify like: 'compare March 2025 vs March 2026'."
            )
        return result

    # ── Branch 2: Cannot answer — log error ──────────────────────────
    if "CANNOT_ANSWER" in response:
        error_reason = _extract_error_reason(response) or "Unknown reason."

        # Build context JSON for the error log
        conversation_summary = ""
        if chat_history:
            for msg in chat_history[-5:]:
                role = msg.get("role", "user").upper()
                conversation_summary += f"{role}: {msg.get('content', '')}\n"

        sql_attempted = ""
        sql_blocks = _extract_sql_blocks(response)
        if sql_blocks:
            sql_attempted = "\n---\n".join(sql_blocks)

        context_json = {
            "conversation_summary": conversation_summary,
            "sql_attempted": sql_attempted,
            "month_a": month_a,
            "month_b": month_b,
            "dimensions": dimensions,
            "data_columns": list(df_a.columns) if not df_a.empty else list(df_b.columns),
        }

        try:
            if IS_DEMO:
                log_event("analysis_error", question=question,
                          context=context_json, reason=error_reason)
            else:
                log_analysis_error(session, question, context_json, error_reason)
            result["logged_error"] = True
        except Exception:
            pass  # don't break the user flow if logging fails

        # Clean up the answer — remove the CANNOT_ANSWER markers
        clean_answer = response
        clean_answer = re.sub(r"CANNOT_ANSWER\s*", "", clean_answer)
        clean_answer = re.sub(
            r"===ERROR_REASON===.*?===END_ERROR_REASON===", "",
            clean_answer, flags=re.DOTALL
        ).strip()
        result["answer"] = clean_answer
        return result

    # ── Branch 3: Standard drilldown (existing logic) ────────────────
    if "NEEDS_DRILLDOWN" in response:
        sql_blocks = _extract_sql_blocks(response)
        if sql_blocks:
            # Build schema context for retry prompts
            cols_block = "\n".join(f"  {c}" for c in actual_columns)
            schema_context = (
                f"== TABLE ==\n{FULLY_QUALIFIED_TABLE}\n\n"
                f"== ACTUAL COLUMNS (use ONLY these exact names) ==\n"
                f"{cols_block}\n\n"
                f"== METRIC FORMULAS ==\n"
                f"  SUM(VOLUME_TONS)                                          AS VOLUME\n"
                f"  SUM(GROSS_PROFIT)                                        AS GP\n"
                f"  SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0)              AS MARGIN\n"
                f'  SUM(WON_FLAG)                                        AS WON\n'
                f'  SUM(INQUIRY_FLAG)                                       AS INQUIRIES\n'
                f'  SUM(INQUIRY_FLAG)-SUM(WON_FLAG)                     AS LOST\n\n'
                f"NOTE: The columns \"WON_FLAG\" and \"INQUIRY_FLAG\" must be double-quoted.\n"
                f"There is NO column called FIXTURES (without quotes), STATUS, FIXTURE_STATUS, "
                f"INQUIRY_ID, or TRANSACTIONS_WON.\n"
                f"Use only the column names listed above."
            )

            # Execute all SQL blocks returned (could be 1 or 2)
            dfs = []
            for sql in sql_blocks:
                try:
                    dfs.append(execute_query(session, sql))
                except Exception as e:
                    # Retry once: send error + full schema back to LLM
                    retry_prompt = (
                        f"The SQL query failed with error: {e}\n\n"
                        f"Original query:\n```sql\n{sql}\n```\n\n"
                        f"{schema_context}\n\n"
                        f"Fix the query using ONLY the columns listed above "
                        f"and return a corrected version in a ```sql``` block."
                    )
                    retry_resp = _call_llm(retry_prompt, provider,
                                           session=session, model=model)
                    retry_blocks = _extract_sql_blocks(retry_resp)
                    if retry_blocks:
                        dfs.append(execute_query(session, retry_blocks[0]))
                    else:
                        raise

            if len(dfs) == 2:
                drilldown_df = pd.concat(dfs, ignore_index=True)
                result["drilldown_df_a"] = dfs[0]
                result["drilldown_df_b"] = dfs[1]
                data_block = (
                    f"MONTH A DATA ({month_a}):\n{dfs[0].head(100).to_csv(index=False)}\n\n"
                    f"MONTH B DATA ({month_b}):\n{dfs[1].head(100).to_csv(index=False)}"
                )
            else:
                drilldown_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
                data_block = f"DATA:\n{drilldown_df.head(100).to_csv(index=False)}"
                
            result["drilldown_sql"] = "\n---\n".join(sql_blocks)
            result["drilldown_df"] = drilldown_df

            # Build chat context for the final analysis prompt
            history_context = ""
            if chat_history:
                history_context = "CONVERSATION CONTEXT:\n"
                for msg in chat_history[-5:]:
                    role = msg.get("role", "user").upper()
                    history_context += f"{role}: {msg.get('content', '')}\n"
                history_context += "\n"

            # Send drilldown results back to LLM for final answer
            followup_prompt = (
                f"{history_context}"
                f"The user asked: '{question}'\n\n"
                f"{data_block}\n\n"
                f"INSTRUCTIONS:\n"
                f"1. If there are two datasets (Month A and Month B), compute the change "
                f"for each group between months.\n"
                f"2. Identify the top movers (biggest increases and decreases).\n"
                f"3. If data contains multiple dimensions, first summarize at the higher "
                f"level, then break down what drove each top mover.\n"
                f"4. Cite specific numbers. Never use bare $ signs.\n"
                f"5. Answer the user's SPECIFIC question — if they asked about the top "
                f"ports' customers, focus on which customers within those ports drove "
                f"the change, not just the port-level summary.\n"
                f"Provide a concise markdown analysis answering the user's question."
            )
            final_response = _call_llm(followup_prompt, provider,
                                       session=session, model=model)
            result["answer"] = final_response

    return result
