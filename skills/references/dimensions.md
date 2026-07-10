# Dimension Reference

## Dimension Categories

### Customer
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| CUSTOMER_NAME | Customer | The end customer |

### Supplier
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| SUPPLIER_NAME | Supplier | Fuel supplier |

### Location
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| PORT_NAME | Port | Physical port location |
| SUPPLY_REGION | Supply Region | Regional supply team |

### Primary Broker (Account Owner)
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| ACCOUNT_BROKER | Primary Broker | Owner of the customer account |
| ACCOUNT_BROKER_OFFICE | Primary Broker Office | Office of the account owner |
| ACCOUNT_BROKER_REGION | Primary Broker Region | Region of the account owner |

### Supply Broker
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| SUPPLY_BROKER | Supply Broker | Broker handling the supply side |
| SUPPLY_TEAM_OFFICE | Supply Team Office | Office of the supply team |
| SUPPLY_TEAM_REGION | Supply Team Region | Region of the supply team |

### Customer Broker
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| CUSTOMER_BROKER | Customer Broker | Broker handling the customer side |
| CUSTOMER_BROKER_OFFICE | Customer Broker Office | Office of the customer broker |
| CUSTOMER_BROKER_REGION | Customer Broker Region | Region of the customer broker |

### Deal Type
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| DEAL_TYPE | Deal Class / Deal Type | Categorizes deals by business type (e.g. TRADED, INVENTORY) |

### Vessel
| Column | Friendly Name | Notes |
|--------|--------------|-------|
| VESSEL_SHIP_TYPE | Ship Type | Ship type of the **individual vessel on this transaction** (e.g., Tanker, Bulker, Container). Per-ship — a customer can show up under multiple ship types (e.g., a Container customer with a few Bulk carrier transactions). Distinct from a customer-level overall ship type. |
| CUSTOMER_SHIP_TYPE | Customer Ship Type | **Customer's overall ship type** (e.g., Tanker, Bulker, Container). Same value for every transaction of a given customer. Use to classify business by customer fleet identity; pair with `VESSEL_SHIP_TYPE` to spot fleet-mix differences (e.g., a Container customer with Bulk carrier transactions). |

## Common Drill-Down Paths

When the user starts broad and wants to drill down, these are natural hierarchies:

1. **Region → Office → Broker**: e.g., `ACCOUNT_BROKER_REGION` → `ACCOUNT_BROKER_OFFICE` → `ACCOUNT_BROKER`
2. **Supply Region → Port**: `SUPPLY_REGION` → `PORT_NAME`
3. **Customer Broker Region → Office → Broker**: `CUSTOMER_BROKER_REGION` → `CUSTOMER_BROKER_OFFICE` → `CUSTOMER_BROKER`
4. **Customer → Port**: `CUSTOMER_NAME` → `PORT_NAME` (where does this customer buy?)
5. **Supplier → Port**: `SUPPLIER_NAME` → `PORT_NAME` (where does this supplier deliver?)
6. **Ship Type → Customer**: `VESSEL_SHIP_TYPE` → `CUSTOMER_NAME` (which customers drive each ship type?)
7. **Customer Ship Type → Ship Type**: `CUSTOMER_SHIP_TYPE` → `VESSEL_SHIP_TYPE` (where does a customer's actual fleet differ from their overall classification?)

## Display Defaults

- Default dimension when user doesn't specify: **CUSTOMER_NAME** (Customer)
- Default metric for sorting: **GP** (Gross Profit) descending
- Default limit: Top 50 results
