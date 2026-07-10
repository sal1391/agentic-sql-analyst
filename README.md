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

## Setup

1. **Copy the env template:**
   ```bash
   cp .env.example .env
   ```

2. **Fill in your Snowflake credentials** in `.env`
   - Set `SNOWFLAKE_DATABASE`, `SNOWFLAKE_SCHEMA`, and `SNOWFLAKE_TABLE` to the real object name.
   - If the role can only access the current database/schema, keep those aligned with your Snowflake permissions.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app:**
   ```bash
   streamlit run app/main.py
   ```

## Usage

1. Select an **LLM provider** (Snowflake Cortex or Azure AI Foundry)
2. Pick **Month A** (baseline) and **Month B** (comparison)
3. Choose which **dimensions** to group by (Customer, Port, Broker, etc.)
4. Click **Compare** — the agent generates SQL, runs it, and produces:
   - KPI summary cards with deltas
   - Bar charts (side-by-side + change waterfall)
   - Auto-generated narrative insights
   - Raw data tables
5. Ask **follow-up questions** in the chat (e.g., "Why did GP drop for Customer X?")

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
