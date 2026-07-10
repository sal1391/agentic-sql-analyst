"""Unit tests for the pure (no-Snowflake) helpers in app.agent."""
import pandas as pd

from app.agent import (
    _compute_kpis,
    _extract_sql_blocks,
    _strip_hash_comments,
)


def _df(volume, gp, won, inquiries, lost):
    return pd.DataFrame(
        {
            "VOLUME": [volume],
            "GP": [gp],
            "WON": [won],
            "INQUIRIES": [inquiries],
            "LOST": [lost],
        }
    )


class TestComputeKpis:
    def test_basic_deltas(self):
        df_a = _df(volume=100.0, gp=500.0, won=4, inquiries=10, lost=6)
        df_b = _df(volume=200.0, gp=800.0, won=6, inquiries=12, lost=6)

        kpis = _compute_kpis(df_a, df_b)

        assert kpis["volume"]["month_a"] == 100.0
        assert kpis["volume"]["month_b"] == 200.0
        assert kpis["volume"]["change"] == 100.0
        assert kpis["volume"]["pct_change"] == 100.0
        assert kpis["gp"]["change"] == 300.0

    def test_margin_is_gp_per_ton_not_summed(self):
        df_a = _df(volume=100.0, gp=500.0, won=1, inquiries=1, lost=0)
        df_b = _df(volume=400.0, gp=1200.0, won=1, inquiries=1, lost=0)

        kpis = _compute_kpis(df_a, df_b)

        assert kpis["margin"]["month_a"] == 5.0  # 500 / 100
        assert kpis["margin"]["month_b"] == 3.0  # 1200 / 400

    def test_zero_baseline_does_not_divide_by_zero(self):
        df_a = _df(volume=0.0, gp=0.0, won=0, inquiries=0, lost=0)
        df_b = _df(volume=50.0, gp=100.0, won=2, inquiries=3, lost=1)

        kpis = _compute_kpis(df_a, df_b)

        assert kpis["volume"]["pct_change"] == 0.0
        assert kpis["margin"]["month_a"] == 0.0

    def test_missing_columns_treated_as_zero(self):
        kpis = _compute_kpis(pd.DataFrame({"OTHER": [1]}), pd.DataFrame({"OTHER": [2]}))
        assert kpis["volume"]["month_a"] == 0.0
        assert kpis["gp"]["change"] == 0.0


class TestExtractSqlBlocks:
    def test_extracts_fenced_sql(self):
        resp = "Here you go:\n```sql\nSELECT 1 FROM t\n```\ndone"
        blocks = _extract_sql_blocks(resp)
        assert len(blocks) == 1
        assert blocks[0].startswith("SELECT 1")

    def test_extracts_multiple_fenced_blocks(self):
        resp = "```sql\nSELECT 1 FROM a\n```\ntext\n```sql\nSELECT 2 FROM b\n```"
        blocks = _extract_sql_blocks(resp)
        assert len(blocks) == 2

    def test_fallback_bare_select(self):
        resp = "SELECT COL FROM MY_TABLE WHERE X = 1;"
        blocks = _extract_sql_blocks(resp)
        assert len(blocks) == 1
        assert "MY_TABLE" in blocks[0]


class TestStripHashComments:
    def test_drops_full_line_hash_comments(self):
        sql = "# a python-style comment\nSELECT 1"
        assert _strip_hash_comments(sql).strip() == "SELECT 1"

    def test_preserves_hash_inside_quoted_identifier(self):
        sql = 'SELECT SUM("#_COUNT") FROM t'
        assert '"#_COUNT"' in _strip_hash_comments(sql)

    def test_truncates_inline_hash_comment(self):
        sql = "SELECT 1  # trailing note"
        assert _strip_hash_comments(sql) == "SELECT 1"
