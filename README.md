# MoM Comparison — AI Agent App

An LLM-agent Streamlit app that compares month-over-month shipping & fuel transaction data. The agent reads a `skills/` playbook at runtime to dynamically generate SQL, query Snowflake, and produce analysis with KPIs, charts, and narrative insights.

## Architecture

```
User (Streamlit UI) → Agent Orchestrator → reads skills/ playbook
                                         → calls LLM (Cortex or Azure)
                                         → generates SQL → executes on Snowflake
                                         → analyzes results → renders UI
```

The `skills/` folder is the LLM's knowledge base — it contains the data model, SQL patterns with few-shot examples, and analysis templates. No SQL or analysis logic is hardcoded.

## Demo mode (default — no Snowflake needed)

The app ships with a built-in demo: 18 months of realistic (fake) marine-fuel
transactions in an in-process DuckDB, an AI analyst, a rate-limited start screen, and strict
topic guardrails on the chat.

**Run locally:**

```bash
pip install -r requirements.txt
# OPENAI_API_KEY must be set in your environment
streamlit run app/main.py
```

**Deploy on Railway:**

1. Push this repo to GitHub and create a new Railway service from it
   (`railway.toml` provides the start command).
2. Set service variables: `OPENAI_API_KEY` (required), `OPENAI_MODEL`
   (optional, default `gpt-4o-mini`), `DEPLOY_MODE=demo` (optional — demo is
   already the default).
3. Deploy. Email entries and guardrail events appear in the Railway log
   console as `[demo-log]` lines.

To run against real Snowflake instead, set `DEPLOY_MODE=local` (or `aws`/`sis`)
and fill in the Snowflake variables from `.env.example`.

## Usage

1. Pick **Month A** (baseline) and **Month B** (comparison)
2. Choose which **dimensions** to group by (Customer, Port, Broker, etc.)
3. Click **Compare** — the agent generates SQL, runs it, and produces:
   - KPI summary cards with deltas
   - Bar charts (side-by-side + change waterfall)
   - Auto-generated narrative insights
   - Raw data tables
4. Ask **follow-up questions** in the chat (e.g., "Why did GP drop for Customer X?")

## Skills Folder Structure

```
skills/
├── SKILL.md                  # Master playbook (data model, routing, rules)
├── sql-patterns/
│   ├── SKILL.md              # When/how to pick a SQL pattern
│   ├── aggregation.md        # Single-month aggregation examples
│   ├── comparison.md         # Two-month comparison examples
│   └── drilldown.md          # Drill-down query examples
├── analysis/
│   ├── SKILL.md              # How to interpret results
│   └── mom-patterns.md       # Narrative templates
└── references/
    ├── data-model.md          # Full column catalog
    └── dimensions.md          # Dimension hierarchy
```

## Data Source

- **Table**: `SANDBOX.ANALYTICS.SALES_ACTUALS_V`
- **Metrics**: Volume, GP, Margin, # Won, # Inquiries, # Lost
- **Dimensions**: 13 fields (Customer, Supplier, Port, Supply Region, brokers, offices, regions)
