# SQL Patterns — When & How

You generate SQL for the table `SANDBOX.ANALYTICS.SALES_ACTUALS_V`. Read the examples below to understand the query patterns. Pick the right pattern based on the user's request.

## Pattern Selection

| User Request | Pattern File | Description |
|---|---|---|
| Compare two months | [comparison.md](./comparison.md) | Side-by-side metrics for Month A vs Month B with changes |
| Show data for one month | [aggregation.md](./aggregation.md) | Aggregate metrics by dimensions for a single month |
| Drill into a specific value | [drilldown.md](./drilldown.md) | Filter to a specific dimension value and break down further |
| Diagnostic: lost/won activity, GP drop/increase, win rate, margin, volume | [diagnostic.md](./diagnostic.md) | Metric-focused analysis — ORDER BY the metric the user asks about, not always GP. Covers lost activity, won deals, GP/volume/margin changes, win rate, and conversion analysis. Supports any dimension filter + any secondary breakdown. |

## Common Rules

- Always use `DATE_TRUNC('MONTH', DELIVERY_DATE)` for monthly grouping.
- Date filters use: `DATE_TRUNC('MONTH', DELIVERY_DATE) = :month_param`
- Wrap dimension columns in `COALESCE(col, 'Unknown')` to handle NULLs.
- Margin = `SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0)` — computed, never summed.
- ORDER BY the primary metric descending unless the user specifies otherwise.
- LIMIT results to top 50 unless the user asks for all.
