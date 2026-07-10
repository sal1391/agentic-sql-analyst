"""
KPI Cards component — renders a row of st.metric widgets from the agent's KPI output.
"""
import streamlit as st


def _n(val, default=0.0) -> float:
    """Safely coerce any value (None, str, int, float) to float."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def render_kpi_cards(kpis: dict):
    """Render KPI metric cards in a row.

    Args:
        kpis: Dict with keys like "volume", "gp", "margin", "won", "inquiries", "lost".
              Each value is a dict with "month_a", "month_b", "change", "pct_change".
    """
    if not kpis:
        st.info("No KPI data available.")
        return

    st.markdown(
        """
        <style>
        [data-testid="stMetricValue"] {
            font-size: clamp(0.85rem, 1.4vw, 1.25rem);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stMetricDelta"] {
            font-size: clamp(0.7rem, 1.1vw, 0.95rem);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        [data-testid="stMetricLabel"] {
            font-size: clamp(0.7rem, 1.1vw, 0.9rem);
            white-space: nowrap;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Define display config for each metric
    metric_config = {
        "volume": {"label": "Volume (tons)", "format": "{:,.0f}", "delta_format": "{:,.0f}", "inverse": False},
        "gp": {"label": "Gross Profit ($)", "format": "${:,.0f}", "delta_format": "${:,.0f}", "inverse": False},
        "margin": {"label": "Margin ($/ton)", "format": "${:,.2f}", "delta_format": "${:,.2f}", "inverse": False},
        "won": {"label": "# Won", "format": "{:,.0f}", "delta_format": "{:,.0f}", "inverse": False},
        "inquiries": {"label": "# Inquiries", "format": "{:,.0f}", "delta_format": "{:,.0f}", "inverse": False},
        "lost": {"label": "# Lost", "format": "{:,.0f}", "delta_format": "{:,.0f}", "inverse": True},
    }

    cols = st.columns(len(metric_config))

    for col, (key, config) in zip(cols, metric_config.items()):
        data = kpis.get(key, {})
        if not data:
            continue

        month_b_val = _n(data.get("month_b"))
        change = _n(data.get("change"))
        pct_change = _n(data.get("pct_change"))

        # Format values
        display_val = config["format"].format(month_b_val)
        delta_str = f"{config['delta_format'].format(change)} ({pct_change:+.1f}%)"

        # Delta color: "inverse" means lower is better (e.g., Lost)
        delta_color = "inverse" if config["inverse"] else "normal"

        col.metric(
            label=config["label"],
            value=display_val,
            delta=delta_str,
            delta_color=delta_color,
        )
