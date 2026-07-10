# Analysis Patterns — How to Interpret Results

You receive query results as DataFrames (Month A and Month B), along with pre-computed KPIs, top movers, and new/lost data. Follow these procedures to write the narrative.

## Pre-Computed Data (Steps 1-3)

Steps 1-3 below are **pre-computed by the application** and provided to you in the prompt. Do NOT recompute these values. They are calculated from the FULL dataset (not truncated).

### Step 1: Changes (Pre-Computed)

For each dimension group, absolute and percentage changes have been computed:

| Change Type | Formula |
|-------------|---------|
| Absolute change | `Month_B_value - Month_A_value` |
| % change | `(Month_B_value - Month_A_value) / ABS(Month_A_value) * 100` when Month A ≠ 0 |
| New entry | Present in Month B only (Month A is NULL) |
| Lost entry | Present in Month A only (Month B is NULL) |

**Special rule for Margin**: Since margin is a ratio, report both the absolute point change (e.g., +$2.50/ton) and the % change. Do NOT compute % change of margin as a simple ratio — explain the change in context of volume and GP shifts.

### Step 2: Top Movers (Pre-Computed)

The top increases and decreases by GP are provided with:
- GP, Volume, and Margin values for both months
- Change amounts and percentages
- Driver classification (volume-driven, margin-driven, or both)

### Step 3: Summary KPIs (Pre-Computed)

KPI totals are provided as a JSON object. Use these exact numbers.

## Step 4: Generate Narrative (YOUR JOB)

This is your primary task. Using the pre-computed data provided, write a narrative following the patterns in [mom-patterns.md](./mom-patterns.md).

Your narrative must:
1. **Explain WHY, not just WHAT** — contextualize each change
2. **For each top mover**, explain whether the change was volume-driven, margin-driven, or both (the driver is provided — reference it)
3. **Reference exact numbers** from the pre-computed data — do not approximate or round differently
4. **Include new/lost analysis** with GP, Volume, and Margin for each new/lost group
5. **Cite specific numbers** — never say "significant" or "notable" without a number

## Output Format

Return your analysis in this exact structure:

```
===KPI_JSON===
{...the pre-computed KPI JSON, echoed back...}
===END_KPI_JSON===

===NARRATIVE===
{...the markdown narrative from Step 4...}
===END_NARRATIVE===
```

**NOTE:** The `===TOP_MOVERS_JSON===` section is no longer needed — top movers are computed deterministically by the application.
