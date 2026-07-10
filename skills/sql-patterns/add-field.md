# Add a New Field (Procedure)

When the user asks you to "add a new field" or "add a column" to the agent's knowledge, follow this checklist to ensure all playbook files are updated correctly.

## 1. Gather Field Details
First, ask the user or determine:
- **Column name** (e.g., `PRODUCT_TYPE`)
- **Data type** (e.g., `VARCHAR`, `DOUBLE`)
- **Category**: Is it a Dimension (group-by) or Metric (aggregated amount)?
- **Friendly name** and **Description**
- **Dimension Category** (e.g., Customer, Broker) or **Aggregation rule** (e.g., `SUM()`)

## 2. Update the Playbook Files
Update the following files depending on whether it is a Dimension or Metric:

### For All Fields
- [ ] `skills/references/data-model.md`: Add the column to the **All Columns** table. Ensure it has the Column name, Type, Category, and Description.
- [ ] `skills/SKILL.md`: Add a routing rule if necessary (though usually the general routing handles it).

### If it is a Dimension
- [ ] `skills/SKILL.md`: Add the column to the **Dimensions** table. Include the Column, Friendly Name, and Category.
- [ ] `skills/references/dimensions.md`: Add the column to the matched Category table. Update the Drill-Down Paths section if it introduces a new conceptual hierarchy.
- [ ] `skills/sql-patterns/aggregation.md`: (Optional but recommended) Add an example querying entirely by this dimension.
- [ ] `skills/sql-patterns/comparison.md`: (Optional but recommended) Add an example comparing by this dimension.
- [ ] `skills/sql-patterns/drilldown.md`: (Optional but recommended) Add an example drilling down into or by this dimension.

### If it is a Metric
- [ ] `skills/SKILL.md`: Add the column to the **Metrics** table. Include the Metric, SQL Formula, and Description.
- [ ] `skills/references/data-model.md`: Add the aggregation rule to the **Aggregation Rules** section.
- [ ] `skills/sql-patterns/aggregation.md`, `comparison.md`, `drilldown.md`: Update ALL SELECT templates and examples to include this new metric in the aggregated output.
- [ ] `skills/analysis/SKILL.md`: Add the metric to the KPI JSON template. Define its computation changes.
- [ ] `skills/analysis/mom-patterns.md`: Update the summary and top movers narrative templates to optionally factor in this new metric.

## 3. Verification
- Verify the agent generates correct SQL via a hypothetical query request utilizing the new field.
- Ensure that you wrap dimension columns with `COALESCE(col, 'Unknown')` in SQL templates.
- Run any local script (like `test_token_count.py`) if validating token limits.