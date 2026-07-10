"""
Narrative component — renders the LLM-generated analysis text.
"""
import re
import streamlit as st


def _to_float(val, default=0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def escape_dollars(text: str) -> str:
    """Escape bare $ signs so Streamlit does not render them as LaTeX.

    Replaces any $ that is NOT already escaped (i.e., not preceded by a
    backslash) with \\$ so st.markdown() treats it as literal text.
    """
    if not text:
        return text
    return re.sub(r'(?<!\\)\$', r'\\$', text)


def render_narrative(narrative: str):
    """Render the narrative insights block.

    Args:
        narrative: Markdown-formatted narrative text from the agent.
    """
    if not narrative:
        st.info("No narrative generated.")
        return

    st.subheader("📊 Analysis & Insights")
    st.markdown(escape_dollars(narrative))


def render_top_movers(top_movers):
    """Render the top movers as an expandable section.

    Supports both the new deterministic format (dict with "increases"/"decreases"
    keys containing multi-metric entries) and the legacy LLM format (flat list).
    """
    if not top_movers:
        return

    # Detect format: new deterministic dict vs legacy list
    if isinstance(top_movers, dict) and ("increases" in top_movers or "decreases" in top_movers):
        _render_top_movers_deterministic(top_movers)
    elif isinstance(top_movers, list):
        _render_top_movers_legacy(top_movers)


def _render_top_movers_deterministic(top_movers: dict):
    """Render deterministic top movers with GP, Volume, Margin detail."""
    increases = top_movers.get("increases", [])
    decreases = top_movers.get("decreases", [])

    if not increases and not decreases:
        return

    with st.expander("Top Movers (expand for details)", expanded=False):
        if increases:
            st.markdown("**Top Increases by GP:**")
            for m in increases:
                dim_str = ", ".join(m.get("dimensions", {}).values())
                gp = m.get("gp", {})
                vol = m.get("volume", {})
                margin = m.get("margin", {})
                driver = m.get("driver", "")

                st.markdown(
                    f"- **{dim_str}**: GP +{_to_float(gp.get('change')):,.0f} "
                    f"({_to_float(gp.get('pct')):+.1f}%)"
                )
                st.markdown(
                    f"  - Volume: {_to_float(vol.get('a')):,.0f} -> "
                    f"{_to_float(vol.get('b')):,.0f} "
                    f"({_to_float(vol.get('change')):+,.0f} tons, "
                    f"{_to_float(vol.get('pct')):+.1f}%)"
                )
                st.markdown(
                    f"  - Margin: {_to_float(margin.get('a')):.2f} -> "
                    f"{_to_float(margin.get('b')):.2f} "
                    f"({_to_float(margin.get('change')):+.2f}/ton)"
                )
                if driver:
                    st.markdown(f"  - Driver: {driver}")

        if decreases:
            st.markdown("**Top Decreases by GP:**")
            for m in decreases:
                dim_str = ", ".join(m.get("dimensions", {}).values())
                gp = m.get("gp", {})
                vol = m.get("volume", {})
                margin = m.get("margin", {})
                driver = m.get("driver", "")

                st.markdown(
                    f"- **{dim_str}**: GP {_to_float(gp.get('change')):,.0f} "
                    f"({_to_float(gp.get('pct')):+.1f}%)"
                )
                st.markdown(
                    f"  - Volume: {_to_float(vol.get('a')):,.0f} -> "
                    f"{_to_float(vol.get('b')):,.0f} "
                    f"({_to_float(vol.get('change')):+,.0f} tons, "
                    f"{_to_float(vol.get('pct')):+.1f}%)"
                )
                st.markdown(
                    f"  - Margin: {_to_float(margin.get('a')):.2f} -> "
                    f"{_to_float(margin.get('b')):.2f} "
                    f"({_to_float(margin.get('change')):+.2f}/ton)"
                )
                if driver:
                    st.markdown(f"  - Driver: {driver}")


def _render_top_movers_legacy(top_movers: list):
    """Render legacy LLM-format top movers (flat list)."""
    with st.expander("Top Movers (expand for details)", expanded=False):
        increases = [m for m in top_movers
                     if _to_float(m.get("change")) > 0 or m.get("direction") == "increase"]
        decreases = [m for m in top_movers
                     if _to_float(m.get("change")) < 0 or m.get("direction") == "decrease"]

        if increases:
            st.markdown("**Top Increases:**")
            for m in increases[:5]:
                dim_val = str(m.get("dimension_value", m.get("dimension", "Unknown")) or "Unknown")
                metric = str(m.get("metric", "GP") or "GP")
                change = _to_float(m.get("change"))
                pct = _to_float(m.get("pct_change"))
                st.markdown(f"- **{dim_val}** — {metric}: +{change:,.0f} ({pct:+.1f}%)")

        if decreases:
            st.markdown("**Top Decreases:**")
            for m in decreases[:5]:
                dim_val = str(m.get("dimension_value", m.get("dimension", "Unknown")) or "Unknown")
                metric = str(m.get("metric", "GP") or "GP")
                change = _to_float(m.get("change"))
                pct = _to_float(m.get("pct_change"))
                st.markdown(f"- **{dim_val}** — {metric}: {change:,.0f} ({pct:+.1f}%)")


def render_new_lost(new_lost: dict, month_a: str, month_b: str):
    """Render new and lost dimension groups as expandable tables.

    Args:
        new_lost: Dict with "new" and "lost" keys, each a list of entries
                  with "dimensions", "gp", "volume", "margin".
        month_a: Label for the baseline month.
        month_b: Label for the comparison month.
    """
    if not new_lost:
        return

    new_items = new_lost.get("new", [])
    lost_items = new_lost.get("lost", [])

    if not new_items and not lost_items:
        return

    with st.expander(
        f"New & Lost ({len(new_items)} new, {len(lost_items)} lost)",
        expanded=False,
    ):
        if new_items:
            st.markdown(f"**New in {month_b}** ({len(new_items)} groups)")
            _render_new_lost_table(new_items)

        if lost_items:
            st.markdown(f"**Lost from {month_a}** ({len(lost_items)} groups)")
            _render_new_lost_table(lost_items)


def _render_new_lost_table(items: list):
    """Render a list of new/lost entries as a dataframe."""
    import pandas as pd

    rows = []
    for entry in items:
        row = dict(entry.get("dimensions", {}))
        row["GP"] = entry.get("gp", 0)
        row["Volume"] = entry.get("volume", 0)
        row["Margin (per ton)"] = entry.get("margin", 0)
        rows.append(row)

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
