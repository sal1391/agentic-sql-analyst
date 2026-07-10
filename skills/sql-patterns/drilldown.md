# Drilldown Pattern — Filter & Break Down

Use this pattern when the user asks about a specific dimension value (e.g., "Why did GP drop for Customer X?"). Filter to that value and break down by a secondary dimension.

## Template

```sql
SELECT
    {secondary_dimension_columns},
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '{month}'
  AND {primary_dimension} = '{filter_value}'
GROUP BY {secondary_dimension_columns}
ORDER BY GP DESC
LIMIT 50
```

## Example: Why did GP drop for "ACME Corp" — drill down by Port

**Month A (January):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND CUSTOMER_NAME = 'ACME Corp'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY GP DESC
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
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
  AND CUSTOMER_NAME = 'ACME Corp'
GROUP BY COALESCE(PORT_NAME, 'Unknown')
ORDER BY GP DESC
```

## Example 2: Drill down into Deal Class for a specific Port

**Month A (January):**
```sql
SELECT
    COALESCE(DEAL_TYPE, 'Unknown') AS DEAL_CLASS,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND PORT_NAME = 'HOUSTON'
GROUP BY COALESCE(DEAL_TYPE, 'Unknown')
ORDER BY GP DESC
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
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
  AND PORT_NAME = 'HOUSTON'
GROUP BY COALESCE(DEAL_TYPE, 'Unknown')
ORDER BY GP DESC
```
## Example 3: Chained Drilldown — Top Movers + Attribution

When the user asks for top movers and what drove them (e.g., "Which ports had the biggest increases and which customers were responsible?"), query at the finer grain (`PORT_NAME` and `CUSTOMER_NAME`) for **both** months. The analysis step will sum up the ports and find the top drivers.

**Month A query:**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
GROUP BY COALESCE(PORT_NAME, 'Unknown'), COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

**Month B query:**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
GROUP BY COALESCE(PORT_NAME, 'Unknown'), COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

## Example: Drill into a Ship Type by Customer

**Month A (March):**
```sql
SELECT
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-03-01'
  AND VESSEL_SHIP_TYPE = 'Tanker'
GROUP BY COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

**Month B (April):**
```sql
SELECT
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-04-01'
  AND VESSEL_SHIP_TYPE = 'Tanker'
GROUP BY COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

## Example: Drill into a Customer Ship Type by actual Vessel Ship Type

Use this when the user asks "for Container customers, what ship types are they actually using?" — it exposes mismatches between a customer's overall classification and their per-transaction vessels.

**Month A (March):**
```sql
SELECT
    COALESCE(VESSEL_SHIP_TYPE, 'Unknown') AS SHIP_TYPE,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-03-01'
  AND CUSTOMER_SHIP_TYPE = 'Container'
GROUP BY COALESCE(VESSEL_SHIP_TYPE, 'Unknown')
ORDER BY GP DESC
```

**Month B (April):**
```sql
SELECT
    COALESCE(VESSEL_SHIP_TYPE, 'Unknown') AS SHIP_TYPE,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-04-01'
  AND CUSTOMER_SHIP_TYPE = 'Container'
GROUP BY COALESCE(VESSEL_SHIP_TYPE, 'Unknown')
ORDER BY GP DESC
```

## When the User Asks "Why?"

1. Identify which dimension value changed the most (from the comparison results already loaded).
2. Pick a secondary dimension to drill into (e.g., if grouping by Customer, drill by Port or Supply Region).
3. Run the drilldown query for both months.
4. Compare the drilldown results to explain what drove the change.

## Example 4: Contextual Chained Drilldown — "From the Top 10 ports, what customers are associated to the increase?"

When the user references results from a previous drilldown (e.g., "from the Top 10 ports…"), the system provides a `DETERMINISTIC TOP VALUES` block with exact dimension values and the column name. Use those exact values in a WHERE IN clause.

**Month A (January):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-01-01'
  AND PORT_NAME IN ('SINGAPORE', 'NEDERLAND', 'TAMPA', 'HOUSTON', 'FUJAIRAH',
                 'NEW ORLEANS', 'DURBAN', 'BEAUMONT', 'CORPUS CHRISTI', 'SANTOS')
GROUP BY COALESCE(PORT_NAME, 'Unknown'), COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

**Month B (February):**
```sql
SELECT
    COALESCE(PORT_NAME, 'Unknown') AS PORT,
    COALESCE(CUSTOMER_NAME, 'Unknown') AS CUSTOMER,
    SUM(VOLUME_TONS) AS VOLUME,
    SUM(GROSS_PROFIT) AS GP,
    SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0) AS MARGIN,
    SUM(WON_FLAG) AS WON,
    SUM(INQUIRY_FLAG) AS INQUIRIES,
    SUM(INQUIRY_FLAG)-SUM(WON_FLAG) AS LOST
FROM SANDBOX.ANALYTICS.SALES_ACTUALS_V
WHERE DATE_TRUNC('MONTH', DELIVERY_DATE) = '2026-02-01'
  AND PORT_NAME IN ('SINGAPORE', 'NEDERLAND', 'TAMPA', 'HOUSTON', 'FUJAIRAH',
                 'NEW ORLEANS', 'DURBAN', 'BEAUMONT', 'CORPUS CHRISTI', 'SANTOS')
GROUP BY COALESCE(PORT_NAME, 'Unknown'), COALESCE(CUSTOMER_NAME, 'Unknown')
ORDER BY GP DESC
```

### Key rules for contextual chained drilldowns:
1. **Always copy values from the DETERMINISTIC TOP VALUES block** — never re-derive from narrative text.
2. **Keep the original dimension in GROUP BY** alongside the new dimension (e.g., both PORT_NAME and CUSTOMER_NAME) so results can be attributed.
3. **Always query BOTH months** so changes can be computed.
4. **If the user says "increase"**, use only the increase values. If they say "decrease", use the decrease values. If ambiguous, use both.
