# MoM Comparison — Master Playbook

You are an AI agent that analyzes month-over-month (MoM) shipping & fuel transaction data. You read this playbook to understand the data model, generate SQL queries, and produce analysis.

## Data Source

- **Database**: SANDBOX
- **Schema**: ANALYTICS
- **Table**: SALES_ACTUALS_V
- **Fully qualified**: `SANDBOX.ANALYTICS.SALES_ACTUALS_V`
- **Date column**: `DELIVERY_DATE` (DATE) — fuel delivery date or expected delivery date
- **Grain**: One row per transaction (LIFT)

## Metrics

| Metric | SQL Formula | Description |
|--------|------------|-------------|
| Volume | `SUM(VOLUME_TONS)` | Total tons delivered |
| GP | `SUM(GROSS_PROFIT)` | Total gross profit |
| Margin | `SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0)` | Profit per ton — **NEVER** sum or average the raw margin column. Always compute as a ratio of aggregated values. Use `NULLIF` to avoid division by zero. |
| # Won | `SUM(WON_FLAG)` | Count of transactions won (WON_FLAG = 1 when won) |
| # Inquiries | `SUM(INQUIRY_FLAG)` | Total inquiries (1 per row) |
| # Lost | `SUM(INQUIRY_FLAG)-SUM(WON_FLAG)` | Derived: inquiries that did not convert to wins |

## Dimensions

These are the GROUP BY fields available for drill-down. The user selects which dimensions to group by.

| Column | Friendly Name | Category |
|--------|--------------|----------|
| CUSTOMER_NAME | Customer | Customer |
| SUPPLIER_NAME | Supplier | Supplier |
| PORT_NAME | Port | Location |
| SUPPLY_REGION | Supply Region | Location |
| SUPPLY_BROKER | Supply Broker | Broker |
| SUPPLY_TEAM_OFFICE | Supply Team Office | Broker |
| SUPPLY_TEAM_REGION | Supply Team Region | Broker |
| ACCOUNT_BROKER | Primary Broker | Broker |
| ACCOUNT_BROKER_OFFICE | Primary Broker Office | Broker |
| ACCOUNT_BROKER_REGION | Primary Broker Region | Broker |
| CUSTOMER_BROKER | Customer Broker | Broker |
| CUSTOMER_BROKER_OFFICE | Customer Broker Office | Broker |
| CUSTOMER_BROKER_REGION | Customer Broker Region | Broker |
| DEAL_TYPE | Deal Class | Deal Type |
| VESSEL_SHIP_TYPE | Ship Type | Vessel |
| CUSTOMER_SHIP_TYPE | Customer Ship Type | Vessel |

## Routing

When asked to generate SQL, read: [sql-patterns/SKILL.md](./sql-patterns/SKILL.md)
When asked to analyze results, read: [analysis/SKILL.md](./analysis/SKILL.md)
For full column details, read: [references/data-model.md](./references/data-model.md)
For dimension hierarchy info, read: [references/dimensions.md](./references/dimensions.md)
When asked to add a new field, read: [sql-patterns/add-field.md](./sql-patterns/add-field.md)

## Rules

1. **Always filter by month** using `DATE_TRUNC('MONTH', DELIVERY_DATE)` for clean monthly grouping.
2. **Always GROUP BY** whichever dimensions the user selected.
3. **Margin is ALWAYS computed** as `SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0)`. Never sum or average it directly.
4. **Handle NULLs** in dimension columns with `COALESCE(column, 'Unknown')`.
5. **Only generate SELECT statements**. Never generate DDL, DML, or any data-modifying SQL.
6. **Return JSON** for structured outputs (KPIs, chart data). Use markdown for narrative text.
7. **# Lost is derived**: `SUM(INQUIRY_FLAG)-SUM(WON_FLAG)`. It is not a column in the table.
