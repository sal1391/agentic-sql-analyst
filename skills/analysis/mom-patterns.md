# MoM Narrative Patterns

Use these templates to generate the narrative text. Adapt language to match the actual data.

## Overall Summary Template

> **Month-over-Month Summary: {Month A} → {Month B}**
>
> Overall volume {increased/decreased} by {X}% ({absolute change} tons), while gross profit {increased/decreased} by {Y}% ({absolute change}). Margin moved from {Month A margin}/ton to {Month B margin}/ton ({+/-}{change}/ton).
>
> The business won {Won B} transactions in {Month B} vs {Won A} in {Month A} ({change} {more/fewer}), with inquiries {up/down} {Z}% ({Inquiries B} vs {Inquiries A}). The win rate {improved/declined} from {Win Rate A}% to {Win Rate B}%.

## Top Movers Template

> **Key Drivers of Change:**
>
> *Top Increases by GP:*
> 1. **{Dimension Value 1}**: GP up {change} ({pct}%)
>    - Volume: {vol_a} -> {vol_b} ({vol_change} tons, {vol_pct}%)
>    - Margin: {margin_a} -> {margin_b} ({margin_change}/ton, {margin_pct}%)
>    - Driver: {volume-driven | margin-driven | both}
>
> *Top Decreases by GP:*
> 1. **{Dimension Value 1}**: GP down {change} ({pct}%)
>    - Volume: {vol_a} -> {vol_b} ({vol_change} tons, {vol_pct}%)
>    - Margin: {margin_a} -> {margin_b} ({margin_change}/ton, {margin_pct}%)
>    - Driver: {volume loss | margin compression | both}

## New/Lost Template

> **New in {Month B}:** (accounts/groups not present in {Month A})
>
> | {Dim1} | {Dim2} | GP | Volume (tons) | Margin (per ton) |
> |--------|--------|----|---------------|------------------|
> | {val}  | {val}  | {gp} | {vol}      | {margin}         |
>
> **Lost from {Month A}:** (accounts/groups present in {Month A} but not {Month B})
>
> | {Dim1} | {Dim2} | GP | Volume (tons) | Margin (per ton) |
> |--------|--------|----|---------------|------------------|
> | {val}  | {val}  | {gp} | {vol}      | {margin}         |

## Follow-Up Answer Template

When the user asks a follow-up question like "Why did X drop?":

> **{Dimension Value} — GP Change Analysis:**
>
> {Dimension Value} saw GP {drop/rise} of {change} from {Month A} to {Month B}.
>
> Breaking down by {secondary dimension}:
> - {Sub-value 1}: {change description}
> - {Sub-value 2}: {change description}
>
> The primary driver was {explanation based on the drilldown data}.

## Top Movers + Attribution Template

> **Top {Dimension 1} by GP Increase ({Month A} → {Month B}):**
>
> 1. **{Dimension 1 Value 1}**: GP up {change} ({pct}%)
>    - {Dimension 2 Value A}: +{change} (largest contributor)
>    - {Dimension 2 Value B}: +{change}
>
> 2. **{Dimension 1 Value 2}**: GP up {change} ({pct}%)
>    - {Dimension 2 Value A}: +{change}

## Contextual Follow-Up Template

When the user asks to drill into previous drilldown results (e.g., "from the top 10 ports, what customers?"):

> **Customers Driving GP Increase in Top Ports ({Month A} → {Month B}):**
>
> **{Port 1}** (GP change: +{change}):
> | Customer | GP {Month A} | GP {Month B} | Change |
> |----------|-------------|-------------|--------|
> | {Cust A} | {gp_a}      | {gp_b}      | {+/-change} |
> | {Cust B} | {gp_a}      | {gp_b}      | {+/-change} |
>
> **{Port 2}** (GP change: +{change}):
> | Customer | GP {Month A} | GP {Month B} | Change |
> |----------|-------------|-------------|--------|
> | {Cust A} | {gp_a}      | {gp_b}      | {+/-change} |
>
> **Summary:** The largest contributor to port-level GP increases was {Customer X} in {Port Y}, accounting for {pct}% of that port's growth. Across all top ports, {Customer Z} appeared most frequently as a driver.

## Diagnostic Analysis Template

When the user asks a diagnostic question focused on a specific metric ("where did I lose activity?", "worst win rate?", "where did GP drop?"), present results sorted by the **user's metric of interest**, not always GP.

### Single-Metric Diagnostic (Single Month)

> **{Metric} Analysis by {Dimension} — {Month}:**
>
> | {Dimension} | {Primary Metric} | Volume | GP | Margin | Won | Lost | Win Rate |
> |---|---|---|---|---|---|---|---|
> | {val} | {metric_val} | {vol} | {gp} | {margin} | {won} | {lost} | {wr}% |
>
> **Key findings:**
> - {Dimension Value 1} had the {highest/lowest} {metric} at {value}
> - {Dimension Value 2} followed with {value}
> - {Contextual insight linking the metric to other indicators}

### MoM Diagnostic (Comparison)

> **{Metric} Change Analysis by {Dimension} — {Month A} → {Month B}:**
>
> Top {increases/decreases} in {metric}:
> 1. **{Dimension Value 1}**: {metric} went from {val_a} to {val_b} ({change}, {pct}%)
>    - Context: Volume {change description}, GP {change description}
> 2. **{Dimension Value 2}**: {metric} went from {val_a} to {val_b} ({change}, {pct}%)
>
> **Summary:** The largest {improvement/deterioration} in {metric} was in {Dimension Value}, driven by {explanation}.

### Filtered Diagnostic (Specific Entity)

> **{Metric} Breakdown for {Entity} by {Secondary Dimension} — {Month A} → {Month B}:**
>
> | {Secondary Dim} | {Metric} {Month A} | {Metric} {Month B} | Change | Volume | GP |
> |---|---|---|---|---|---|
> | {val} | {a} | {b} | {change} | {vol} | {gp} |
>
> {Entity} {metric context}: The {worst/best} performing {secondary dimension} was {value}, with {metric} of {number}. This was driven by {explanation}.

### Win Rate / Rate Metric Diagnostic

> **Win Rate by {Dimension} — {Month} (minimum {N} inquiries):**
>
> | {Dimension} | Win Rate | Won | Inquiries | Lost | GP |
> |---|---|---|---|---|---|
> | {val} | {wr}% | {won} | {inq} | {lost} | {gp} |
>
> **Below-average performers** (overall win rate: {avg}%):
> - {Dimension Value 1}: {wr}% win rate on {inq} inquiries — {lost} lost deals worth potential GP of {gp_estimate}
>
> **Note:** Groups with fewer than {N} inquiries are excluded to avoid misleading rates.

## Rules

- Always cite specific numbers — never say "significant" or "notable" without a number.
- Round percentages to 1 decimal place.
- Round dollar amounts to whole numbers.
- Round volume (tons) to whole numbers.
- Round margin to 2 decimal places.
- If a metric is unchanged, say "flat" or "unchanged" rather than "0% change".
- Win rate = `WON / INQUIRIES * 100`.
- **NEVER use bare `$` signs** in the output text. Streamlit renders `$...$` as LaTeX math, which garbles the display. Write dollar amounts as plain numbers (e.g., "700" or "1,200") without a `$` prefix.
