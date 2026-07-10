"""
MoM Comparison — Streamlit App
================================
AI-agent app that reads a skills/ playbook to dynamically generate SQL,
query Snowflake, and produce month-over-month analysis.
"""
import os
import streamlit as st
# Note: load_dotenv is called inside config.py before all os.getenv calls

try:
    from app.config import LLM_PROVIDER, CORTEX_MODEL, AZURE_MODEL, FULLY_QUALIFIED_TABLE, DEPLOY_MODE, IS_DEMO
    from app.agent import DIMENSIONS, run_comparison, run_followup
    from app.components.kpi_cards import render_kpi_cards
    from app.components.charts import render_comparison_charts, render_metric_selector
    from app.components.narrative import render_narrative, render_top_movers, render_new_lost, escape_dollars
    from app import guardrails
    from app.email_gate import require_email
except ImportError:
    from config import LLM_PROVIDER, CORTEX_MODEL, AZURE_MODEL, FULLY_QUALIFIED_TABLE, DEPLOY_MODE, IS_DEMO
    from agent import DIMENSIONS, run_comparison, run_followup
    from components.kpi_cards import render_kpi_cards
    from components.charts import render_comparison_charts, render_metric_selector
    from components.narrative import render_narrative, render_top_movers, render_new_lost, escape_dollars
    import guardrails
    from email_gate import require_email

if IS_DEMO:
    try:
        from app.local_session import get_local_session
    except ImportError:
        from local_session import get_local_session
else:
    try:
        from app.snowflake_client import get_session
    except ImportError:
        from snowflake_client import get_session

try:
    from app.snowflake_client import get_available_months
except ImportError:
    from snowflake_client import get_available_months

# Drops canned-rejection exchanges from the history passed to the LLM
# (the displayed transcript keeps them).
_llm_safe_history = guardrails.llm_safe_history

# ── Page config ──────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MoM Comparison",
    page_icon="📊",
    layout="wide",
)

if IS_DEMO and not require_email():
    st.stop()

st.title("📊 Month-over-Month Comparison")

# Per-session cap on Compare runs in demo mode (mirrors guardrails' turn-cap
# philosophy for the second LLM-calling entry point).
MAX_COMPARES_PER_SESSION = 25

# ── Chat avatars ─────────────────────────────────────────────────────────

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_TRIDENT_PATH = os.path.join(_ASSETS_DIR, "trident.png")
CHAT_AVATARS = {
    "assistant": _TRIDENT_PATH if os.path.exists(_TRIDENT_PATH) else None,
    "user": "🧑‍✈️",
}

# ── Session state init ───────────────────────────────────────────────────

if "comparison_result" not in st.session_state:
    st.session_state.comparison_result = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_drilldown" not in st.session_state:
    st.session_state.last_drilldown = None

# ── Snowflake session ────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading data...")
def _get_session():
    if IS_DEMO:
        return get_local_session()
    return get_session()

try:
    session = _get_session()
except Exception as _conn_err:
    if IS_DEMO:
        st.error("The demo data could not be loaded. Please refresh the page.")
    else:
        st.error(
            f"**Cannot connect to Snowflake.** Check your `.env` credentials.\n\n"
            f"```\n{_conn_err}\n```"
        )
    st.stop()

# ── Sidebar controls ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")

    # LLM provider toggle (hidden in demo; Azure not available in SiS)
    if IS_DEMO:
        provider = "openai"
        model = None  # openai_client falls back to OPENAI_MODEL
    elif DEPLOY_MODE == "sis":
        provider = "cortex"
        model = st.text_input("Cortex Model", value=CORTEX_MODEL, key="cortex_model_input")
    else:
        provider = st.radio(
            "LLM Provider",
            options=["cortex", "azure"],
            index=0 if LLM_PROVIDER == "cortex" else 1,
            format_func=lambda x: "Snowflake Cortex" if x == "cortex" else "Azure AI Foundry",
            key="llm_provider_radio",
        )

        if provider == "cortex":
            model = st.text_input("Cortex Model", value=CORTEX_MODEL, key="cortex_model_input")
        else:
            model = st.text_input("Azure Model", value=AZURE_MODEL or "gpt-4o", key="azure_model_input")

    st.divider()
    st.header("Comparison")

    # Show active configuration (never in demo — it names the LLM backend)
    if not IS_DEMO:
        with st.expander("⚙️ Active configuration", expanded=False):
            st.code(
                f"Table : {FULLY_QUALIFIED_TABLE}\n"
                f"LLM   : {LLM_PROVIDER} / {CORTEX_MODEL if LLM_PROVIDER == 'cortex' else AZURE_MODEL}",
                language="text",
            )
            st.caption(
                "Adjust `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, `SNOWFLAKE_TABLE` in `.env` to change the table."
            )

    # Load available months
    with st.spinner("Loading months..."):
        try:
            months = get_available_months(session)
        except RuntimeError as _table_err:
            if IS_DEMO:
                st.error("The demo data could not be loaded. Please refresh the page.")
            else:
                st.error(str(_table_err))
            st.stop()
        except Exception as _table_err:
            if IS_DEMO:
                st.error("The demo data could not be loaded. Please refresh the page.")
            else:
                st.error(f"Failed to load months: {_table_err}")
            st.stop()

    if not months:
        st.error("No data found in the table.")
        st.stop()
    # Calculate default months based on today's date (skip future months)
    from datetime import date, timedelta

    _today = date.today()
    # First day of previous month
    _prev_month = (_today.replace(day=1) - timedelta(days=1)).replace(day=1)
    # First day of two months ago
    _two_months_ago = (_prev_month - timedelta(days=1)).replace(day=1)

    _prev_str = _prev_month.strftime("%Y-%m-%d")
    _two_ago_str = _two_months_ago.strftime("%Y-%m-%d")

    # Find the index of each target month in the list, fallback to 0
    _idx_b = months.index(_prev_str) if _prev_str in months else 0
    _idx_a = months.index(_two_ago_str) if _two_ago_str in months else min(1, len(months) - 1)

    month_a = st.selectbox("Month A (baseline)", options=months, index=_idx_a, key="month_a_select")
    month_b = st.selectbox("Month B (compare to)", options=months, index=_idx_b, key="month_b_select")

    # Dimension picker
    dim_options = list(DIMENSIONS.keys())
    dim_labels = list(DIMENSIONS.values())
    selected_dims = st.multiselect(
        "Group by dimensions",
        options=dim_options,
        default=["CUSTOMER_NAME"],
        format_func=lambda x: DIMENSIONS.get(x, x),
        key="dimensions_multiselect",
    )

    if not selected_dims:
        st.warning("Select at least one dimension.")

    compare_btn = st.button("🔍 Compare", type="primary", use_container_width=True,
                            disabled=not selected_dims or month_a == month_b,
                            key="compare_button")

    if month_a == month_b:
        st.caption("⚠️ Select two different months to compare.")

# ── Run comparison ───────────────────────────────────────────────────────

if compare_btn and IS_DEMO and st.session_state.get("compare_count", 0) >= MAX_COMPARES_PER_SESSION:
    st.warning("You've reached the comparison limit for this session.")
elif compare_btn:
    if IS_DEMO:
        st.session_state.compare_count = st.session_state.get("compare_count", 0) + 1
    st.session_state.chat_history = []
    st.session_state.last_drilldown = None
    with st.spinner("🤖 Agent is generating SQL and analyzing data..."):
        try:
            result = run_comparison(
                session=session,
                month_a=month_a,
                month_b=month_b,
                dimensions=selected_dims,
                provider=provider,
                model=model,
            )
            st.session_state.comparison_result = result
            st.session_state.compare_meta = {
                "month_a": month_a,
                "month_b": month_b,
                "dimensions": selected_dims,
                "provider": provider,
                "model": model,
            }
        except Exception as e:
            if IS_DEMO:
                st.error("The comparison could not be completed. Please try again in a moment.")
            else:
                st.error(f"Comparison failed: {e}")
                import traceback
                with st.expander("🔍 Error Trace", expanded=True):
                    st.code(traceback.format_exc(), language="text")
            st.session_state.comparison_result = None

# ── Display results ──────────────────────────────────────────────────────

result = st.session_state.comparison_result

if result:
    meta = st.session_state.get("compare_meta", {})
    ma = meta.get("month_a", "?")
    mb = meta.get("month_b", "?")

    st.subheader(f"Results: {ma} → {mb}")

    # Debug SQL expander (hidden in demo — model-generated SQL is unfiltered here)
    debug_sql = result.get("_debug_sql", {})
    if debug_sql and not IS_DEMO:
        with st.expander("🔍 Debug: Generated SQL"):
            st.markdown("**Month A (final)**")
            st.code(debug_sql.get("sql_a_final", result.get("sql_a", "")), language="sql")
            st.markdown("**Month B (final)**")
            st.code(debug_sql.get("sql_b_final", result.get("sql_b", "")), language="sql")
            if debug_sql.get("sql_a_raw") != debug_sql.get("sql_a_final"):
                st.markdown("**Month A (before corrections)**")
                st.code(debug_sql.get("sql_a_raw", ""), language="sql")
            if debug_sql.get("sql_b_raw") != debug_sql.get("sql_b_final"):
                st.markdown("**Month B (before corrections)**")
                st.code(debug_sql.get("sql_b_raw", ""), language="sql")

    # KPI Cards
    render_kpi_cards(result.get("kpis", {}))

    st.divider()

    # Charts
    col_chart, col_picker = st.columns([4, 1])
    with col_picker:
        chart_metric = render_metric_selector()
    with col_chart:
        render_comparison_charts(
            result["df_a"], result["df_b"],
            meta.get("dimensions", []),
            ma, mb,
            metric=chart_metric,
        )

    st.divider()

    # Narrative
    _narrative = result.get("narrative", "")
    render_narrative(guardrails.filter_output(_narrative, st.session_state) if IS_DEMO else _narrative)
    render_top_movers(result.get("top_movers", []))
    render_new_lost(result.get("new_lost", {}), ma, mb)

    st.divider()

    # Data tables
    with st.expander("📋 View Raw Data", expanded=False):
        tab_a, tab_b = st.tabs([f"Month A: {ma}", f"Month B: {mb}"])
        with tab_a:
            st.dataframe(result["df_a"], use_container_width=True)
        with tab_b:
            st.dataframe(result["df_b"], use_container_width=True)

    # SQL used
    _sql_a = result.get("sql_a", "")
    _sql_b = result.get("sql_b", "")
    if IS_DEMO:
        _sql_a = guardrails.filter_output(_sql_a, st.session_state)
        _sql_b = guardrails.filter_output(_sql_b, st.session_state)
    with st.expander("🔧 SQL Queries Generated", expanded=False):
        st.code(_sql_a, language="sql")
        st.code(_sql_b, language="sql")

    st.divider()

    # ── Chat follow-up ───────────────────────────────────────────────────

    st.subheader("💬 Ask a Follow-Up Question")

    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar=CHAT_AVATARS.get(msg["role"])):
            st.markdown(escape_dollars(msg["content"]))

    if IS_DEMO and guardrails.is_locked(st.session_state):
        st.warning(guardrails.LOCK_MESSAGE
                   if st.session_state.get("gr_locked") else guardrails.LIMIT_MESSAGE)
        question = None
    else:
        question = st.chat_input("e.g., Why did GP drop for Customer X?", key="followup_chat_input")

    if question and IS_DEMO:
        allowed, block_msg = guardrails.check_question(question, st.session_state)
        if not allowed:
            st.session_state.chat_history.append({"role": "user", "content": question})
            with st.chat_message("user", avatar=CHAT_AVATARS["user"]):
                st.markdown(question)
            with st.chat_message("assistant", avatar=CHAT_AVATARS["assistant"]):
                st.markdown(block_msg)
            st.session_state.chat_history.append({"role": "assistant", "content": block_msg})
            question = None

    if question:
        st.session_state.chat_history.append({"role": "user", "content": question})
        with st.chat_message("user", avatar=CHAT_AVATARS["user"]):
            st.markdown(question)

        with st.chat_message("assistant", avatar=CHAT_AVATARS["assistant"]):
            with st.spinner("Thinking..."):
                try:
                    followup = run_followup(
                        session=session,
                        question=question,
                        month_a=meta["month_a"],
                        month_b=meta["month_b"],
                        df_a=result["df_a"],
                        df_b=result["df_b"],
                        dimensions=meta["dimensions"],
                        provider=meta["provider"],
                        model=meta.get("model"),
                        chat_history=_llm_safe_history(st.session_state.chat_history) if IS_DEMO
                        else st.session_state.chat_history,
                        prev_drilldown=st.session_state.last_drilldown,
                    )
                    answer = followup["answer"]
                    if IS_DEMO:
                        answer = guardrails.filter_output(answer, st.session_state)
                    st.markdown(escape_dollars(answer))
                    st.session_state.chat_history.append(
                        {"role": "assistant", "content": answer}
                    )

                    # ── Date change: render inline comparison ────────
                    if followup.get("date_change"):
                        new_ma = followup["new_month_a"]
                        new_mb = followup["new_month_b"]
                        st.divider()
                        st.caption(f"📅 New comparison: {new_ma} → {new_mb}")
                        render_kpi_cards(followup["new_kpis"])
                        render_top_movers(followup.get("new_top_movers", {}))
                        render_new_lost(followup.get("new_new_lost", {}), new_ma, new_mb)

                        # Persist date-change state so subsequent follow-ups
                        # use the NEW dates/data instead of the original sidebar values.
                        st.session_state.compare_meta["month_a"] = new_ma
                        st.session_state.compare_meta["month_b"] = new_mb
                        if followup.get("drilldown_df_a") is not None:
                            st.session_state.comparison_result["df_a"] = followup["drilldown_df_a"]
                            st.session_state.comparison_result["df_b"] = followup["drilldown_df_b"]
                        if followup.get("new_kpis"):
                            st.session_state.comparison_result["kpis"] = followup["new_kpis"]
                        if followup.get("new_top_movers"):
                            st.session_state.comparison_result["top_movers"] = followup["new_top_movers"]
                        if followup.get("new_new_lost"):
                            st.session_state.comparison_result["new_lost"] = followup["new_new_lost"]

                        st.session_state.last_drilldown = {
                            "df_a": followup.get("drilldown_df_a"),
                            "df_b": followup.get("drilldown_df_b"),
                            "sql": followup.get("drilldown_sql"),
                            "question": question,
                        }
                        with st.expander("New Comparison Data"):
                            tab_a, tab_b = st.tabs([f"Month A: {new_ma}", f"Month B: {new_mb}"])
                            with tab_a:
                                st.dataframe(followup.get("drilldown_df_a"), use_container_width=True)
                            with tab_b:
                                st.dataframe(followup.get("drilldown_df_b"), use_container_width=True)
                        if followup.get("drilldown_sql"):
                            _new_cmp_sql = followup["drilldown_sql"]
                            if IS_DEMO:
                                _new_cmp_sql = guardrails.filter_output(_new_cmp_sql, st.session_state)
                            with st.expander("New Comparison SQL"):
                                st.code(_new_cmp_sql, language="sql")

                    # ── Error logged: show feedback ──────────────────
                    elif followup.get("logged_error"):
                        st.info("📝 This question has been logged for review. We'll use it to improve the agent.")

                    # ── Standard drilldown ────────────────────────────
                    elif followup.get("drilldown_df") is not None:
                        # Persist drilldown state for next follow-up
                        st.session_state.last_drilldown = {
                            "df_a": followup.get("drilldown_df_a"),
                            "df_b": followup.get("drilldown_df_b"),
                            "sql": followup.get("drilldown_sql"),
                            "question": question,
                        }
                        with st.expander("Drilldown Data"):
                            st.dataframe(followup["drilldown_df"],
                                         use_container_width=True)
                        if followup.get("drilldown_sql"):
                            _drilldown_sql = followup["drilldown_sql"]
                            if IS_DEMO:
                                _drilldown_sql = guardrails.filter_output(_drilldown_sql, st.session_state)
                            with st.expander("Drilldown SQL"):
                                st.code(_drilldown_sql, language="sql")
                except Exception as e:
                    if IS_DEMO:
                        st.error("The follow-up could not be completed. Please try again in a moment.")
                    else:
                        st.error(f"Follow-up failed: {e}")
else:
    st.info("👈 Select two months and dimensions in the sidebar, then click **Compare**.")
