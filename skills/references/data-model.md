# Data Model — SALES_ACTUALS_V

**Fully qualified name**: `SANDBOX.ANALYTICS.SALES_ACTUALS_V` (runtime value controlled by env vars)

## All Columns

| Column | Type | Category | Description |
|--------|------|----------|-------------|
| LIFT_ID | VARCHAR | Identifier | Unique transaction ID. Always referred to as "LIFT". |
| WON_FLAG | FLOAT | Metric | 1 if transaction won, 0 otherwise |
| INQUIRY_FLAG | FLOAT | Metric | 1 per row (1 inquiry per transaction) |
| DELIVERY_DATE | DATE | Date | Fuel delivery date, or expected delivery date if not yet delivered |
| GROSS_PROFIT | DOUBLE | Metric | Gross profit for this transaction |
| VOLUME_TONS | DOUBLE | Metric | Volume of fuel delivered (in tons) |
| CUSTOMER_NAME | VARCHAR | Dimension | Customer name |
| SUPPLIER_NAME | VARCHAR | Dimension | Supplier name |
| PORT_NAME | VARCHAR | Dimension | Port location |
| SUPPLY_REGION | VARCHAR | Dimension | Supply region / team |
| SUPPLY_BROKER | VARCHAR | Dimension | Supply broker for the transaction |
| SUPPLY_TEAM_OFFICE | VARCHAR | Dimension | Supply team office |
| SUPPLY_TEAM_REGION | VARCHAR | Dimension | Supply team region |
| ACCOUNT_BROKER | VARCHAR | Dimension | Account owner (primary broker) |
| ACCOUNT_BROKER_OFFICE | VARCHAR | Dimension | Primary broker's office |
| ACCOUNT_BROKER_REGION | VARCHAR | Dimension | Primary broker's region |
| CUSTOMER_BROKER | VARCHAR | Dimension | Customer broker for the transaction |
| CUSTOMER_BROKER_OFFICE | VARCHAR | Dimension | Customer broker's office |
| CUSTOMER_BROKER_REGION | VARCHAR | Dimension | Customer broker's region |
| DEAL_TYPE | VARCHAR | Dimension | Deal Class/Deal Type categorizing business type (e.g. TRADED, INVENTORY) |
| VESSEL_SHIP_TYPE | VARCHAR | Dimension | Ship type of the **individual vessel on this transaction** (e.g., Tanker, Bulker, Container). Per-ship classification — a single customer can have transactions across multiple ship types (e.g., a Container customer may also operate a few Bulk carriers). Do not confuse with a customer-level overall ship type. |
| CUSTOMER_SHIP_TYPE | VARCHAR | Dimension | **Customer's overall ship type** classification (e.g., Tanker, Bulker, Container). Per-customer label — every transaction for that customer rolls up to the same value, even if some of their individual vessels are a different type. Pair with `VESSEL_SHIP_TYPE` to see fleet-mix vs. customer-classification differences. |

## Aggregation Rules

- **Volume**: `SUM(VOLUME_TONS)` — total tons
- **GP**: `SUM(GROSS_PROFIT)` — total gross profit
- **Margin**: `SUM(GROSS_PROFIT) / NULLIF(SUM(VOLUME_TONS), 0)` — GP per ton. NEVER sum or average M column directly.
- **Won**: `SUM(WON_FLAG)` — count of won transactions
- **Inquiries**: `SUM(INQUIRY_FLAG)` — count of all inquiries
- **Lost**: `SUM(INQUIRY_FLAG)-SUM(WON_FLAG)` — derived, not a column

## Monthly Grouping

Always use `DATE_TRUNC('MONTH', DELIVERY_DATE)` to group by month. This normalizes all dates to the first of the month (e.g., `2026-01-15` becomes `2026-01-01`).
