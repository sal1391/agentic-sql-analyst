"""
Token Count Test Script
========================
Standalone CLI script (no Streamlit) that runs the full MoM comparison flow
against Snowflake Cortex and reports input/output/total token counts for
every LLM call.

Uses the options-based form of SNOWFLAKE.CORTEX.COMPLETE which returns a
JSON response containing usage.prompt_tokens, usage.completion_tokens,
and usage.total_tokens.

Usage:
    python test_token_count.py
"""
import json
import re
import sys
import os

# Ensure the project root is on sys.path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import SNOWFLAKE_CONNECTION, CORTEX_MODEL, FULLY_QUALIFIED_TABLE
from app.skill_loader import load_skill_tree
from app.agent import (
    DIMENSIONS, METRICS,
    _build_sql_prompt, _build_analysis_prompt, _build_followup_prompt,
    _extract_sql_blocks, _parse_analysis, _correct_column_names,
    _compute_kpis, _compute_new_lost, _compute_top_movers,
)
from snowflake.snowpark import Session


# ── Token-tracking Cortex call ──────────────────────────────────────────

def call_cortex_with_tokens(session: Session, prompt: str,
                            model: str = None) -> tuple[str, dict]:
    """Call Snowflake Cortex COMPLETE with options to get token usage.

    Uses the array + options form so the response is a JSON object
    containing usage metadata.

    Returns:
        (response_text, usage_dict)
        usage_dict has keys: prompt_tokens, completion_tokens, total_tokens
    """
    model = model or CORTEX_MODEL
    safe_prompt = prompt.replace("'", "''").replace("\\", "\\\\")

    # Options form requires prompt as a role/content array
    query = (
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE("
        f"'{model}', "
        f"[{{'role': 'user', 'content': '{safe_prompt}'}}], "
        f"{{}}"
        f") AS RESPONSE"
    )

    raw = session.sql(query).to_pandas()["RESPONSE"][0]

    # Parse the JSON response
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw

    # Extract the text response
    text = parsed.get("choices", [{}])[0].get("messages", "")

    # Extract usage
    usage = parsed.get("usage", {})
    token_info = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }

    return text, token_info


# ── Helpers ─────────────────────────────────────────────────────────────

def get_table_columns(session: Session) -> list[str]:
    """Return the actual column names from the Snowflake table/view."""
    sql = f"SELECT * FROM {FULLY_QUALIFIED_TABLE} LIMIT 0"
    df = session.sql(sql).to_pandas()
    return list(df.columns)


def execute_query(session: Session, sql: str):
    """Execute a read-only SQL query."""
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        raise ValueError("Only SELECT/WITH queries are allowed.")
    return session.sql(sql).to_pandas()


def print_token_row(step_name: str, usage: dict):
    """Print a single row of the token summary."""
    print(
        f"│ {step_name:<30} │ {usage['prompt_tokens']:>10,} "
        f"│ {usage['completion_tokens']:>10,} "
        f"│ {usage['total_tokens']:>10,} │"
    )


def print_divider():
    print(f"├{'─' * 32}┼{'─' * 12}┼{'─' * 12}┼{'─' * 12}┤")


def print_header():
    print()
    print(f"┌{'─' * 32}┬{'─' * 12}┬{'─' * 12}┬{'─' * 12}┐")
    print(
        f"│ {'Step':<30} │ {'Input':>10} "
        f"│ {'Output':>10} "
        f"│ {'Total':>10} │"
    )
    print_divider()


def print_footer():
    print(f"└{'─' * 32}┴{'─' * 12}┴{'─' * 12}┴{'─' * 12}┘")


# ── Main ────────────────────────────────────────────────────────────────

def main():
    # ── Gather user inputs with defaults ─────────────────────────────
    print("=" * 60)
    print("  MoM Comparison — Token Count Test")
    print("=" * 60)
    print()

    month_a = input("Month A (baseline)  [2025-04-01]: ").strip() or "2025-04-01"
    month_b = input("Month B (compare)   [2025-05-01]: ").strip() or "2025-05-01"

    dim_input = input(
        "Dimensions (comma-separated) [CUSTOMER_NAME, PORT_NAME]: "
    ).strip()
    if dim_input:
        dimensions = [d.strip() for d in dim_input.split(",")]
    else:
        dimensions = ["CUSTOMER_NAME", "PORT_NAME"]

    model = input(f"Cortex model [{CORTEX_MODEL}]: ").strip() or CORTEX_MODEL

    print()
    print(f"  Month A:    {month_a}")
    print(f"  Month B:    {month_b}")
    print(f"  Dimensions: {', '.join(dimensions)}")
    print(f"  Model:      {model}")
    print()

    # ── Connect to Snowflake ─────────────────────────────────────────
    print("Connecting to Snowflake...", end=" ", flush=True)
    session = Session.builder.configs(SNOWFLAKE_CONNECTION).create()
    print("OK")

    actual_columns = get_table_columns(session)
    playbook = load_skill_tree()

    all_usage = []  # list of (step_name, usage_dict)

    # ── Step 1: SQL Generation ───────────────────────────────────────
    print("\n[Step 1/4] Generating SQL...", flush=True)
    sql_prompt = _build_sql_prompt(month_a, month_b, dimensions, actual_columns)
    sql_response, sql_usage = call_cortex_with_tokens(
        session, sql_prompt, model=model
    )
    all_usage.append(("1. SQL Generation", sql_usage))
    print(f"  → {sql_usage['total_tokens']:,} tokens")

    sql_blocks = _extract_sql_blocks(sql_response)
    if len(sql_blocks) < 2:
        print(f"ERROR: LLM returned {len(sql_blocks)} SQL blocks, expected 2.")
        print("Raw response:")
        print(sql_response[:2000])
        session.close()
        return

    sql_a, sql_b = sql_blocks[0], sql_blocks[1]

    # ── Execute queries ──────────────────────────────────────────────
    print("\n  Executing Month A query...", end=" ", flush=True)
    try:
        df_a = execute_query(session, sql_a)
        print(f"OK ({len(df_a)} rows)")
    except Exception as e:
        print(f"FAILED: {e}")
        # Retry once
        print("  Retrying with error feedback...", flush=True)
        retry_prompt = (
            f"The SQL query failed with error: {e}\n\n"
            f"Original query:\n```sql\n{sql_a}\n```\n\n"
            f"Fix the query and return a corrected version in a ```sql``` block."
        )
        retry_response, retry_usage = call_cortex_with_tokens(
            session, retry_prompt, model=model
        )
        all_usage.append(("1b. SQL Retry (Month A)", retry_usage))
        retry_blocks = _extract_sql_blocks(retry_response)
        if retry_blocks:
            sql_a = retry_blocks[0]
            df_a = execute_query(session, sql_a)
            print(f"  → Retry OK ({len(df_a)} rows)")
        else:
            print("  → Retry failed, aborting.")
            session.close()
            return

    print("  Executing Month B query...", end=" ", flush=True)
    try:
        df_b = execute_query(session, sql_b)
        print(f"OK ({len(df_b)} rows)")
    except Exception as e:
        print(f"FAILED: {e}")
        retry_prompt = (
            f"The SQL query failed with error: {e}\n\n"
            f"Original query:\n```sql\n{sql_b}\n```\n\n"
            f"Fix the query and return a corrected version in a ```sql``` block."
        )
        retry_response, retry_usage = call_cortex_with_tokens(
            session, retry_prompt, model=model
        )
        all_usage.append(("1c. SQL Retry (Month B)", retry_usage))
        retry_blocks = _extract_sql_blocks(retry_response)
        if retry_blocks:
            sql_b = retry_blocks[0]
            df_b = execute_query(session, sql_b)
            print(f"  → Retry OK ({len(df_b)} rows)")
        else:
            print("  → Retry failed, aborting.")
            session.close()
            return

    # ── Step 2: Analysis ─────────────────────────────────────────────
    print("\n[Step 2/4] Analyzing results...", flush=True)

    # Pre-compute deterministic data from full dataframes
    computed_kpis = _compute_kpis(df_a, df_b)
    computed_new_lost = _compute_new_lost(df_a, df_b, dimensions)
    computed_top_movers = _compute_top_movers(df_a, df_b, dimensions)
    print(f"  Deterministic: {len(computed_new_lost.get('new', []))} new, "
          f"{len(computed_new_lost.get('lost', []))} lost, "
          f"{len(computed_top_movers.get('increases', []))} top increases, "
          f"{len(computed_top_movers.get('decreases', []))} top decreases")

    analysis_prompt = _build_analysis_prompt(
        month_a, month_b, df_a, df_b, dimensions, playbook,
        computed_kpis=computed_kpis,
        computed_top_movers=computed_top_movers,
        computed_new_lost=computed_new_lost,
    )
    analysis_response, analysis_usage = call_cortex_with_tokens(
        session, analysis_prompt, model=model
    )
    all_usage.append(("2. Analysis", analysis_usage))
    print(f"  → {analysis_usage['total_tokens']:,} tokens")

    parsed = _parse_analysis(analysis_response)

    # ── Step 3: Follow-up Question 1 ─────────────────────────────────
    question_1 = (
        "What ports did we see the biggest increase and drop in GP? "
        "What were the customers associated to that?"
    )
    print(f"\n[Step 3/4] Follow-up: \"{question_1[:60]}...\"", flush=True)

    followup_prompt_1 = _build_followup_prompt(
        question_1, month_a, month_b, df_a, df_b, dimensions, actual_columns
    )
    followup_response_1, followup_usage_1 = call_cortex_with_tokens(
        session, followup_prompt_1, model=model
    )
    all_usage.append(("3. Follow-up Q1", followup_usage_1))
    print(f"  → {followup_usage_1['total_tokens']:,} tokens")

    # Handle NEEDS_DRILLDOWN
    if "NEEDS_DRILLDOWN" in followup_response_1:
        drill_blocks = _extract_sql_blocks(followup_response_1)
        if drill_blocks:
            print("  → Drilldown detected, running SQL...", flush=True)
            import pandas as pd
            dfs = []
            for sql in drill_blocks:
                try:
                    dfs.append(execute_query(session, sql))
                except Exception as e:
                    print(f"    Drilldown query failed: {e}")
            if dfs:
                drilldown_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
                drill_prompt = (
                    f"Here are the drilldown results for the user's question: "
                    f"'{question_1}'\n\n"
                    f"DATA:\n{drilldown_df.head(100).to_csv(index=False)}\n\n"
                    f"Provide a concise analysis answering the user's question "
                    f"with specific numbers from this data."
                )
                drill_resp, drill_usage = call_cortex_with_tokens(
                    session, drill_prompt, model=model
                )
                all_usage.append(("3b. Q1 Drilldown Analysis", drill_usage))
                followup_response_1 = drill_resp
                print(f"  → Drilldown analysis: {drill_usage['total_tokens']:,} tokens")

    # ── Step 4: Follow-up Question 2 ─────────────────────────────────
    question_2 = (
        "What customer did we see the biggest increase and what was the port?"
    )
    print(f"\n[Step 4/4] Follow-up: \"{question_2[:60]}...\"", flush=True)

    # Include Q1 in chat history for context
    chat_history = [
        {"role": "user", "content": question_1},
        {"role": "assistant", "content": followup_response_1},
    ]

    followup_prompt_2 = _build_followup_prompt(
        question_2, month_a, month_b, df_a, df_b, dimensions, actual_columns,
        chat_history=chat_history,
    )
    followup_response_2, followup_usage_2 = call_cortex_with_tokens(
        session, followup_prompt_2, model=model
    )
    all_usage.append(("4. Follow-up Q2", followup_usage_2))
    print(f"  → {followup_usage_2['total_tokens']:,} tokens")

    # Handle NEEDS_DRILLDOWN for Q2
    if "NEEDS_DRILLDOWN" in followup_response_2:
        drill_blocks = _extract_sql_blocks(followup_response_2)
        if drill_blocks:
            print("  → Drilldown detected, running SQL...", flush=True)
            import pandas as pd
            dfs = []
            for sql in drill_blocks:
                try:
                    dfs.append(execute_query(session, sql))
                except Exception as e:
                    print(f"    Drilldown query failed: {e}")
            if dfs:
                drilldown_df = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
                drill_prompt = (
                    f"Here are the drilldown results for the user's question: "
                    f"'{question_2}'\n\n"
                    f"DATA:\n{drilldown_df.head(100).to_csv(index=False)}\n\n"
                    f"Provide a concise analysis answering the user's question "
                    f"with specific numbers from this data."
                )
                drill_resp, drill_usage = call_cortex_with_tokens(
                    session, drill_prompt, model=model
                )
                all_usage.append(("4b. Q2 Drilldown Analysis", drill_usage))
                followup_response_2 = drill_resp
                print(f"  → Drilldown analysis: {drill_usage['total_tokens']:,} tokens")

    # ── Summary ──────────────────────────────────────────────────────
    print_header()
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for step_name, usage in all_usage:
        print_token_row(step_name, usage)
        totals["prompt_tokens"] += usage["prompt_tokens"]
        totals["completion_tokens"] += usage["completion_tokens"]
        totals["total_tokens"] += usage["total_tokens"]
    print_divider()
    print_token_row("GRAND TOTAL", totals)
    print_footer()

    print()
    print(f"Model: {model}")
    print(f"LLM calls: {len(all_usage)}")
    print()

    session.close()
    print("Done. Snowflake session closed.")


if __name__ == "__main__":
    main()
