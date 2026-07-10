# Diagnostic Pattern — Metric-Focused Analysis

Use this pattern when the user asks a diagnostic question: "where did I lose activity?", "which ports had the most won deals?", "where did GP drop?", "lowest win rate?", or any question that focuses on a **specific metric** rather than a general overview.

The key difference from other patterns: the **ORDER BY** targets the metric the user is asking about, not always GP.

## Metric Intent Mapping

Identify which metric the user cares about from their question, then choose the ORDER BY:

| User Intent | Metric Column | ORDER BY | Notes |
|---|---|---|---|
| Lost activity / where did I lose | `SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST` | `LOST DESC` | Highest losses first |
| Won activity / where did I win | `SUM(WON_FLAG) AS WON` | `WON DESC` | Most wins first |
| GP dropped / lost GP / worst GP | `SUM(GROSS_PROFIT) AS GP` | `GP ASC` | Lowest GP first (for single month) |
| GP increased / best GP | `SUM(GROSS_PROFIT) AS GP` | `GP DESC` | Highest GP first |
| Volume dropped / lost volume | `SUM(VOLUME_TONS) AS VOLUME` | `VOLUME ASC` | Lowest volume first |
| Volume increased / most volume | `SUM(VOLUME_TONS) AS VOLUME` | `VOLUME DESC` | Highest volume first |
| Margin dropped / worst margin | `SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN` | `MARGIN ASC` | Lowest margin first |
| Margin increased / best margin | `SUM(GROSS_PROFIT)/NULLIF(SUM(VOLUME_TONS),0) AS MARGIN` | `MARGIN DESC` | Highest margin first |
| Win rate / conversion / lowest win rate | `SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE` | `WIN_RATE ASC` | Lowest win rate first |
| Best win rate / highest conversion | `SUM(WON_FLAG)/NULLIF(SUM(INQUIRY_FLAG),0) AS WIN_RATE` | `WIN_RATE DESC` | Highest win rate first |

## Template — Single Month Diagnostic

Use when the user asks about one month (e.g., "which ports had the most lost activity in January?").

```sql
SELECT
    {dimension_columns},
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
  AND {optional_filter}
GROUP BY {dimension_columns}
HAVING {optional_threshold}
ORDER BY {metric_column} {ASC|DESC}
LIMIT 50
```

## Template — MoM Diagnostic (Two Queries)

Use when the user asks a diagnostic question in a Month A vs Month B context (e.g., "where did I lose the most activity?"). Generate TWO queries — one per month — so the application can compute changes.

**Month A:**
```sql
SELECT
    {dimension_columns},
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month_a}'
  AND {optional_filter}
GROUP BY {dimension_columns}
ORDER BY {metric_column} {ASC|DESC}
LIMIT 50
```

(Repeat with `'{month_b}'` for Month B.)

---

## Example 1: Lost Activity — Where did a specific customer lose the most? (MoM)

**Question:** "Where did I lose the most HARBORLINE SHIPPING activity?"

Filter to the customer, break down by port (or any secondary dimension), sort by LOST DESC.

**Month A (January):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND CUSTOMER_NAME = 'HARBORLINE SHIPPING'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY LOST DESC
```

**Month B (February):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
  AND CUSTOMER_NAME = 'HARBORLINE SHIPPING'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY LOST DESC
```

## Example 2: Won Activity — Which suppliers had the most won deals? (Single Month)

**Question:** "Show me won activity by supplier for January."

```sql
SELECT
    COALESCE(SUPPLIER_NAME, 'Unknown') AS SUPPLIER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
GROUP BY COALESCE(SUPPLIER_NAME, 'Unknown')
ORDER BY WON DESC
LIMIT 50
```

## Example 3: GP Drop — Where did GP drop the most? (MoM)

**Question:** "Where did we lose the most GP by port?"

Sort by GP ascending so the lowest (worst) GP appears first. Generate TWO queries for MoM comparison.

**Month A (January):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY GP ASC
```

**Month B (February):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY GP ASC
```

## Example 4: Win Rate — Which deal types have the lowest win rate? (Single Month)

**Question:** "Which deal types have the lowest win rate in February?"

Use HAVING to filter out low-sample groups (fewer than 5 inquiries) that would produce noisy rates.

```sql
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY COALESCE(DEAL_TYPE, 'Unknown')
HAVING SUM(INQUIRY_FLAG) >= 5
ORDER BY WIN_RATE ASC
LIMIT 50
```

## Example 5: Margin — Worst margin by broker region (MoM)

**Question:** "Which broker regions have the worst margin?"

**Month A (January):**
```sql
SELECT
    COALESCE(ACCOUNT_BROKER_REGION, 'Unknown') AS BROKER_REGION,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
GROUP BY COALESCE(ACCOUNT_BROKER_REGION, 'Unknown')
ORDER BY MARGIN ASC
```

**Month B (February):**
```sql
SELECT
    COALESCE(ACCOUNT_BROKER_REGION, 'Unknown') AS BROKER_REGION,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY COALESCE(ACCOUNT_BROKER_REGION, 'Unknown')
ORDER BY MARGIN ASC
```

## Example 6: Volume Increase — Which customers grew volume the most? (MoM)

**Question:** "Which customers increased volume the most?"

**Month A (January):**
```sql
SELECT
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
GROUP BY COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY VOLUME DESC
```

**Month B (February):**
```sql
SELECT
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY VOLUME DESC
```

## Example 7: Combined Filter + Diagnostic — Lost activity for a customer by deal class (MoM)

**Question:** "Where did HARBORLINE SHIPPING lose the most activity by deal type?"

**Month A (January):**
```sql
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND CUSTOMER_NAME = 'HARBORLINE SHIPPING'
GROUP BY COALESCE(DEAL_TYPE, 'Unknown')
ORDER BY LOST DESC
```

**Month B (February):**
```sql
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST,
    SUM(WON_FLAG) / NULLIF(SUM(INQUIRY_FLAG), 0) AS WIN_RATE
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
  AND CUSTOMER_NAME = 'HARBORLINE SHIPPING'
GROUP BY COALESCE(DEAL_TYPE, 'Unknown')
ORDER BY LOST DESC
```

## Common Rules

1. **Always include ALL standard metrics** in the SELECT (VOLUME, GP, MARGIN, WON, INQUIRIES, LOST, WIN_RATE) — even when the user asks about one metric. The extra metrics provide context for the analysis.
2. **ORDER BY the metric the user asked about**, not always GP.
3. **Use HAVING for rate metrics** (win rate, margin) to filter groups with very few observations. A minimum of `SUM(INQUIRY_FLAG) >= 5` is recommended for win rate queries.
4. **Use COALESCE on dimension columns** to handle NULL values.
5. **Only generate SELECT statements** — never DDL, DML, or any data-modifying SQL.
6. **Double-quote `WON_FLAG` and `INQUIRY_FLAG`** — they contain the `#` character.
7. When comparing MoM, generate **TWO separate queries** (Month A and Month B). The application computes changes.
8. When the user specifies a filter value (e.g., a customer name), use an exact-match WHERE clause. Use the value exactly as the user provides it.
