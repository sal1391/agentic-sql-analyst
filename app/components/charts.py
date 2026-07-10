"""
Charts component — Plotly bar charts for MoM comparison.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go


def render_comparison_charts(df_a: pd.DataFrame, df_b: pd.DataFrame,
                             dimensions: list[str], month_a: str,
                             month_b: str, metric: str = "GP"):
    """Render side-by-side grouped bar chart comparing Month A vs Month B.

    Args:
        df_a: Month A aggregated data.
        df_b: Month B aggregated data.
        dimensions: List of dimension column names used for grouping.
        month_a: Month A label (e.g., "2026-01-01").
        month_b: Month B label.
        metric: Which metric column to chart (default: GP).
    """
    if df_a.empty and df_b.empty:
        st.info("No data to chart.")
        return

    # Build a dimension key for merging (concatenate dimension columns)
    # The LLM may alias columns (e.g., COALESCE(CUSTOMER_NAME,'Unknown') AS CUSTOMER),
    # so we also match by friendly-name mapping.
    _FRIENDLY_TO_COL = {
        "CUSTOMER": "CUSTOMER_NAME", "SUPPLIER": "SUPPLIER_NAME", "PORT": "PORT_NAME",
        "SUPPLY_REGION": "SUPPLY_REGION", "SUPPLY_BROKER": "SUPPLY_BROKER",
        "DEAL_CLASS": "DEAL_TYPE",
    }
    available_cols = set(df_a.columns) | set(df_b.columns)
    dim_cols = []
    for d in dimensions:
        if d in available_cols:
            dim_cols.append(d)
        else:
            # Check if a friendly alias exists in the dataframe
            found = False
            for alias, orig in _FRIENDLY_TO_COL.items():
                if orig == d and alias in available_cols:
                    dim_cols.append(alias)
                    found = True
                    break
            if not found:
                # Fallback: pick any non-metric column
                for c in available_cols:
                    if c not in ["VOLUME", "GP", "MARGIN", "WON", "INQUIRIES", "LOST", "_label"] and c not in dim_cols:
                        dim_cols.append(c)
                        break
    if not dim_cols:
        dim_cols = [c for c in df_a.columns
                    if c not in ["VOLUME", "GP", "MARGIN", "WON", "INQUIRIES", "LOST"]]
        dim_cols = dim_cols[:len(dimensions)] if dim_cols else ["index"]

    def _make_label(row, cols):
        parts = [str(row.get(c, "")) for c in cols]
        return " | ".join(parts)

    # Merge on dimension columns
    df_a = df_a.copy()
    df_b = df_b.copy()
    df_a["_label"] = df_a.apply(lambda r: _make_label(r, dim_cols), axis=1)
    df_b["_label"] = df_b.apply(lambda r: _make_label(r, dim_cols), axis=1)

    metric_upper = metric.upper()

    merged = pd.merge(
        df_a[["_label", metric_upper]].rename(columns={metric_upper: "month_a"}),
        df_b[["_label", metric_upper]].rename(columns={metric_upper: "month_b"}),
        on="_label", how="outer",
    ).fillna(0)

    # Sort by absolute change and take top 20
    merged["abs_change"] = abs(merged["month_b"] - merged["month_a"])
    merged = merged.nlargest(20, "abs_change")

    # ── Grouped Bar Chart ──
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=month_a, x=merged["_label"], y=merged["month_a"],
        marker_color="#636EFA",
    ))
    fig.add_trace(go.Bar(
        name=month_b, x=merged["_label"], y=merged["month_b"],
        marker_color="#EF553B",
    ))
    fig.update_layout(
        title=f"{metric} Comparison — Top 20 by Change",
        barmode="group",
        xaxis_tickangle=-45,
        height=500,
        margin=dict(b=150),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Change Waterfall (horizontal bar) ──
    merged["change"] = merged["month_b"] - merged["month_a"]
    merged = merged.sort_values("change")

    colors = ["#EF553B" if v < 0 else "#00CC96" for v in merged["change"]]

    fig2 = go.Figure(go.Bar(
        x=merged["change"],
        y=merged["_label"],
        orientation="h",
        marker_color=colors,
    ))
    fig2.update_layout(
        title=f"{metric} Change (Month B - Month A)",
        height=max(400, len(merged) * 25),
        margin=dict(l=200),
    )
    st.plotly_chart(fig2, use_container_width=True)


def render_metric_selector() -> str:
    """Render a selectbox to choose which metric to chart."""
    return st.selectbox(
        "Chart metric",
        options=["GP", "VOLUME", "MARGIN", "WON", "INQUIRIES", "LOST"],
        index=0,
        key="chart_metric_select",
    )
