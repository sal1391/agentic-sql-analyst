# MoM Comparison App — How It Works

A plain-English guide for tech-savvy business users.

---

## What Does This App Do?

This app compares **month-over-month performance** of fuel transactions. You pick two months, choose how you want to slice the data (by Customer, Port, Broker, etc.), and an **AI agent** automatically:

1. Writes the SQL queries needed
2. Runs them against your Snowflake data warehouse
3. Analyzes the results
4. Generates a written narrative summary with KPIs, charts, and key takeaways

You can then ask **follow-up questions in plain English** — like *"Why did GP drop for Customer X?"* — and the agent drills deeper.

---

## The Flow (Step by Step)

```
┌──────────────────────────────────────────────────────────────┐
│  YOU                                                         │
│  Pick Month A, Month B, and dimensions (Customer, Port, etc.)│
│  Click "Compare"                                             │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AI AGENT — Turn 1: SQL Generation                           │
│  • Reads a "skills playbook" (data model, SQL templates)     │
│  • Generates two SQL queries (one per month)                 │
│  • Runs them on Snowflake                                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AI AGENT — Turn 2: Analysis                                 │
│  • Reads both result sets                                    │
│  • Computes changes (absolute and %)                         │
│  • Identifies top movers (biggest gains and drops)           │
│  • Writes a markdown narrative                               │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  DASHBOARD OUTPUT                                            │
│  • KPI cards with deltas (Volume, GP, Margin, Won, etc.)     │
│  • Bar charts (side-by-side + change waterfall)              │
│  • Auto-generated narrative insights                         │
│  • Raw data tables + SQL queries used                        │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  FOLLOW-UP CHAT                                              │
│  Ask questions in plain English                              │
│  The agent generates new SQL if needed, re-analyzes,         │
│  and responds with specific numbers                          │
└──────────────────────────────────────────────────────────────┘
```

---

## What Data Is Behind It?

| What | Details |
|------|---------|
| **Source** | Snowflake view: `SALES_ACTUALS_V` |
| **Grain** | One row per transaction (LIFT) |
| **Date field** | `DELIVERY_DATE` — delivery or expected delivery date |

### Metrics (what gets measured)

| Metric | How it's calculated | What it means |
|--------|-------------------|---------------|
| **Volume** | Sum of tons delivered | Total fuel volume |
| **GP** | Sum of gross profit | Total profit in dollars |
| **Margin** | GP ÷ Volume | Profit per ton |
| **Won** | Count of won deals | Transactions that converted |
| **Inquiries** | Count of all transactions | Total pipeline |
| **Lost** | Inquiries − Won | Deals that didn't convert |

### Dimensions (how you can slice it)

You can group by any combination of these:

| Category | Options |
|----------|---------|
| **Customer** | Customer Name |
| **Supplier** | Supplier Name |
| **Location** | Port, Supply Region |
| **Brokers** | Primary Broker, Supply Broker, Customer Broker |
| **Offices/Regions** | Broker Office, Broker Region, Supply Team Office, Supply Team Region, Customer Broker Office, Customer Broker Region |

---

## Where Does the AI Come In? (Deep Dive)

### How the LLM Learns the Playbook

The AI doesn't "know" your data model out of the box. Every time a comparison runs, the app **loads the entire skills folder into the LLM's prompt** as context. Here's exactly how:

**File: `app/skill_loader.py`**

- **`load_skill_tree()`** (line 32) — This is the function that builds the playbook. It:
  1. Reads the master `skills/SKILL.md` file (line 42) — contains the data model, metric formulas, dimension list, and rules
  2. Walks every subfolder (`sql-patterns/`, `analysis/`) and reads all `.md` files inside (lines 47–74) — these contain SQL templates and narrative patterns
  3. Lists `references/` files (like `data-model.md`) but doesn't load them yet — they're available on demand (lines 51–58)
  4. Concatenates everything into one big string separated by `---` dividers (line 76)

- **`load_reference()`** (line 79) — Loads a specific reference file when needed (e.g., during follow-up questions)

The result is cached for 1 hour (`@st.cache_data(ttl=3600)`) so the filesystem isn't re-read on every Streamlit rerun.

**File: `app/agent.py`**

- **Line 367**: `playbook = load_skill_tree()` — This is where the playbook gets loaded when you click Compare
- **Line 368**: `actual_columns = get_table_columns(session)` — The app also queries Snowflake for the real column names (via `SELECT * FROM table LIMIT 0`) so the LLM sees the ground truth, not just what's in the docs
- **Lines 170–208**: `_build_sql_prompt()` — Constructs Turn 1's prompt by combining the actual column list, metric formulas, and the user's selections (months + dimensions) into a structured template
- **Lines 212–260**: `_build_analysis_prompt()` — Constructs Turn 2's prompt by embedding the playbook text, both data sets (as CSV), and formatting instructions

**In short**: The playbook is injected into the LLM prompt as plain text. The LLM doesn't have persistent memory — it reads the playbook fresh each time.

---

### What Is the "Two-Turn LLM Pattern"?

This is not an official industry term — it's a descriptive name for the architecture used here. It means we call the LLM **twice** per comparison, each call with a different job:

| | Turn 1: SQL Generation | Turn 2: Analysis |
|---|---|---|
| **Input** | Column names + metric formulas + user selections | Query results (data) + playbook + formatting rules |
| **Output** | Two SQL queries (Month A & Month B) | KPIs (JSON) + narrative (markdown) + top movers (JSON) |
| **What happens next** | SQL runs on Snowflake, returns data | Output is parsed and rendered in the UI |
| **Code location** | `agent.py` lines 370–381 | `agent.py` lines 419–425 |

```
Turn 1                          Turn 2
┌─────────────┐                ┌─────────────┐
│ LLM receives│                │ LLM receives│
│ • columns   │   SQL runs     │ • data CSVs │
│ • formulas  │──on Snowflake──│ • playbook  │──→ KPIs + Narrative
│ • user picks│   returns data │ • rules     │
│             │                │             │
│ Returns SQL │                │ Returns     │
│ (2 queries) │                │ analysis    │
└─────────────┘                └─────────────┘
```

**Why two turns instead of one?**

- **Turn 1 needs schema knowledge but no data** — It only needs to know column names and metric formulas to write SQL
- **Turn 2 needs data but no schema** — It only needs the actual numbers to write analysis
- Splitting them keeps each prompt **smaller and more focused**, which improves LLM accuracy
- If we combined everything into one call, the prompt would be enormous and the LLM would be more likely to make mistakes

**Follow-up questions** add a **third turn** (or more): the LLM gets the original data + the new question + chat history, and decides whether to answer directly or generate new SQL for a drilldown.

---

### Why This Approach? (Design Rationale)

**1. Separation of concerns**
Each LLM call has one clear job. Turn 1 is a "SQL expert." Turn 2 is a "data analyst." This makes prompts simpler and outputs more reliable than asking one prompt to do everything.

**2. The playbook is editable, not the code**
Business logic lives in markdown files (`skills/`), not in Python. If you add a new metric or dimension, you edit a `.md` file — no code changes, no redeployment. This is sometimes called a **"prompt-as-config"** pattern.

**3. Ground-truth column validation**
The app doesn't blindly trust the playbook. It queries Snowflake for the actual column list (`get_table_columns()`) and passes those to the LLM. This catches cases where the playbook is outdated or a column was renamed.

**4. Built-in error correction**
If the LLM generates SQL that fails, the app catches the Snowflake error, sends it back to the LLM with the full schema context, and asks it to fix the query. This retry loop (lines 386–400 in `agent.py`) handles most hallucination issues automatically.

---

### Industry Comparisons — Similar Patterns

| Pattern | What It Is | How This App Compares |
|---------|-----------|----------------------|
| **Text-to-SQL** | LLM generates SQL from natural language (used by tools like DIN-SQL, C3SQL, Vanna.ai) | This app is a Text-to-SQL system. The "skills playbook" serves the same purpose as schema descriptions and few-shot examples in academic Text-to-SQL papers. |
| **RAG (Retrieval-Augmented Generation)** | LLM retrieves relevant documents before generating a response (used by ChatGPT plugins, enterprise search) | The playbook loading is a simple form of RAG — the app "retrieves" the relevant skill files and injects them into the prompt. It's not vector-search RAG, but the principle is the same: give the LLM context it doesn't have natively. |
| **ReAct (Reason + Act)** | LLM alternates between reasoning and taking actions like running code (used by LangChain agents, AutoGPT) | The two-turn pattern is a **simplified, deterministic version** of ReAct. Instead of letting the LLM decide what tool to call next (which is unpredictable), we hardcode the sequence: generate SQL → execute → analyze. This is more reliable for production use. |
| **Chain-of-Thought Prompting** | Breaking a complex task into steps to improve accuracy | Splitting into Turn 1 (SQL) and Turn 2 (analysis) is effectively chain-of-thought at the architecture level — each step builds on the previous one's output. |
| **Multi-Agent Systems** | Multiple specialized AI agents collaborate (used by CrewAI, AutoGen) | Conceptually similar — Turn 1 is a "SQL Agent" and Turn 2 is an "Analyst Agent" — but this app uses the same LLM with different prompts rather than separate agent instances. Simpler and cheaper. |

**Bottom line**: The two-turn pattern is a pragmatic blend of Text-to-SQL + lightweight RAG + deterministic orchestration. It's not a novel invention — it's a practical combination of well-established patterns, optimized for reliability over flexibility.

---

## This App vs. Snowflake Cortex Analyst — Detailed Comparison

Snowflake offers a built-in product called **Cortex Analyst** that does something similar to this app: it lets users ask questions about structured data in natural language and gets SQL-backed answers. So a natural question is: *why build a custom app instead of using Cortex Analyst?*

Here's a deep breakdown.

### What Is Cortex Analyst?

Cortex Analyst is Snowflake's **managed Text-to-SQL service**. You define a **semantic model** (a YAML file or Semantic View) that describes your tables, columns, metrics, and relationships in business terms. Then users ask questions in plain English, and Cortex Analyst generates and executes SQL behind the scenes.

**Key components:**

- **Semantic Model (YAML)** — A structured file that maps business concepts to physical columns. Example: `"Total Revenue"` maps to `SUM(NET_REV_AMT_USD)`. It includes column descriptions, synonyms (e.g., "revenue" = "sales amount"), dimension/metric classifications, and table join relationships.
- **Semantic Views** — Snowflake's newer, recommended approach. Same concept as the YAML file, but stored as a first-class database object with RBAC integration.
- **Verified Queries** — Pre-approved SQL examples you can add to the semantic model, giving the LLM "gold-standard" patterns for complex questions.
- **REST API** — Available at `POST /api/v2/cortex/analyst/message` for embedding into custom apps.
- **Multi-turn conversations** — Supports follow-up questions within a session.

### What Is Our "Skills Playbook"?

Our app uses a `skills/` folder of **markdown files** that serve a purpose similar to Cortex Analyst's semantic model — but with key differences:

| Aspect | Cortex Analyst Semantic Model | Our Skills Playbook |
|--------|-------------------------------|---------------------|
| **Format** | YAML (structured, schema-validated) | Markdown (free-form, human-readable) |
| **Where it lives** | Inside Snowflake (stage or Semantic View) | In the app's file system (`skills/` folder) |
| **What it contains** | Column definitions, metrics, relationships, synonyms | Data model + SQL pattern examples + analysis templates + narrative rules |
| **Who maintains it** | Data engineers (needs YAML syntax knowledge) | Anyone who can write markdown |
| **Analysis output** | SQL + raw data (no narrative) | SQL + data + KPIs + narrative + charts |

### Feature-by-Feature Comparison

| Feature | Cortex Analyst | This App |
|---------|---------------|----------|
| **Natural language → SQL** | ✅ Built-in, managed | ✅ Custom-built via LLM prompts |
| **Semantic layer** | ✅ YAML / Semantic Views | ✅ Markdown playbook (`skills/`) |
| **Auto-generated narrative** | ❌ Returns data only | ✅ Full written analysis with KPIs and top movers |
| **Charts & visualizations** | ❌ Not included (use Streamlit/Snowsight separately) | ✅ Built-in (Plotly bar charts, waterfall) |
| **Follow-up questions** | ✅ Multi-turn via API | ✅ Chat interface with drilldown |
| **Error self-correction** | ✅ Internal validation agents | ✅ Regex corrections + retry loop with schema context |
| **LLM model choice** | ❌ Snowflake picks automatically | ✅ You choose (Cortex model or Azure) |
| **Works outside Snowflake** | ❌ Snowflake only | ✅ Can use Azure AI Foundry as alternative |
| **Multi-table joins** | ✅ Defined in semantic model relationships | ❌ Single table/view only |
| **RBAC / governance** | ✅ Native Snowflake integration | ⚠️ Inherits from Snowflake session credentials |
| **Setup effort** | Medium (write YAML, validate, iterate) | Medium (write markdown playbook, tune prompts) |
| **Pricing** | Per-message credits + warehouse compute | Per-LLM-call tokens + warehouse compute |
| **Vendor lock-in** | High (Snowflake-only) | Low (swap LLM provider, or move off Snowflake) |

### Where Cortex Analyst Wins

1. **Zero application code** — You don't build or deploy an app. You define a YAML file and use the REST API or Snowsight.
2. **Governed by Snowflake RBAC** — Semantic Views integrate with Snowflake's role-based access control and row-level security policies. Access is managed at the database level.
3. **Multi-table joins** — The semantic model can define relationships between tables, so the LLM can JOIN across multiple tables. Our app queries a single denormalized view.
4. **Internal validation** — Cortex Analyst uses internal agents to validate generated SQL against the semantic model before execution. It's a more mature guardrail than regex corrections.
5. **Snowflake-managed updates** — As Snowflake improves Cortex Analyst, you get better accuracy for free without changing your app.

### Where This App Wins

1. **Full analysis output, not just data** — Cortex Analyst returns SQL results. This app returns KPIs, narrative text, charts, and top movers — a complete analytical dashboard. Cortex Analyst would need a separate front-end to present insights.
2. **Narrative generation** — The two-turn pattern lets the AI write a human-readable summary explaining what changed and why. Cortex Analyst doesn't generate prose.
3. **LLM flexibility** — You can pick the exact model (Claude, GPT-4o, etc.) and switch between Cortex and Azure. Cortex Analyst doesn't let you choose the underlying model.
4. **Customizable prompts** — The skills playbook can include analysis templates, narrative patterns, and business-specific writing rules (e.g., "never use bare $ signs"). The semantic model is limited to schema metadata.
5. **No YAML required** — The playbook is plain markdown. Anyone can read it, edit it, and understand it without knowing YAML syntax or Snowflake-specific schema validation rules.
6. **Portable** — Not locked into Snowflake. If the company moves to another data warehouse, you swap the client code. Cortex Analyst only works with Snowflake.

### When to Use Which

| Scenario | Best Choice |
|----------|-------------|
| Ad-hoc data exploration ("what were total sales in Q3?") | **Cortex Analyst** — fast, no app needed |
| Structured MoM comparison with narrative and charts | **This app** — purpose-built for this workflow |
| Multi-table analytical queries | **Cortex Analyst** — supports JOINs via semantic model |
| Presenting insights to non-technical stakeholders | **This app** — auto-generates readable summaries |
| Embedding analytics in a Slack bot or internal tool | **Either** — both have APIs |
| Strict governance / compliance requirements | **Cortex Analyst** — native RBAC and audit |
| Need to work with non-Snowflake LLMs or data sources | **This app** — provider-agnostic |

### Can They Work Together?

Yes. They're not mutually exclusive. A reasonable evolution could be:

1. **Today**: Use this app for structured MoM comparisons with narrative output
2. **Future**: Use Cortex Analyst's semantic model as the schema source (replacing or supplementing the `skills/` playbook), while keeping the custom analysis and narrative layer on top

The semantic model and the skills playbook solve the same problem (teaching the LLM about your data) in different ways. The key difference is what happens **after** the SQL runs — Cortex Analyst stops at data, while this app continues to analysis and storytelling.

---

## This App vs. Snowflake Cortex Agents

Cortex Agents are a **different product** from Cortex Analyst. While Analyst is a specialized Text-to-SQL engine, **Cortex Agents are an orchestration framework** — closer in concept to what this app does.

### What Are Cortex Agents?

Cortex Agents are Snowflake's managed service for building **autonomous, multi-step AI assistants**. An agent:

1. **Plans** — Breaks a complex user request into sub-tasks
2. **Selects tools** — Chooses which Snowflake service to call for each sub-task
3. **Executes** — Runs the tools and collects results
4. **Reflects** — Checks if the answer is good enough, or if more steps are needed

**Available tools a Cortex Agent can use:**

| Tool | Purpose |
|------|---------|
| **Cortex Analyst** | Query structured data (Text-to-SQL via semantic model) |
| **Cortex Search** | Search unstructured data (PDFs, docs) via hybrid vector + keyword search |
| **Data-to-Chart** | Auto-generate visualizations (Vega-Lite specs) from query results |
| **Custom Tools** | Your own stored procedures or UDFs for any business logic |

**Key infrastructure:**
- **Agent Object** — Configuration containing tool definitions, instructions, and orchestration settings
- **Threads** — Persistent conversation contexts (multi-turn state management is handled by Snowflake, not your app)
- **REST API** — `DATA_AGENT_RUN` API for embedding agents into custom UIs

### How This App Compares to Cortex Agents

| Aspect | Cortex Agents | This App |
|--------|--------------|----------|
| **Architecture** | Snowflake-managed orchestrator; agent decides which tools to call | Custom Python orchestrator; code controls the sequence |
| **Planning** | Autonomous — agent plans sub-tasks | Deterministic — hardcoded two-turn flow |
| **Tool routing** | Dynamic — LLM decides Analyst vs. Search vs. custom tool | Fixed — always: generate SQL → execute → analyze |
| **Data sources** | Structured (Analyst) + unstructured (Search) | Structured only (single Snowflake view) |
| **Visualizations** | Data-to-Chart tool (Vega-Lite) | Built-in Plotly charts |
| **Narrative/analysis** | Not built-in (returns data, not prose) | ✅ Auto-generated narrative + KPIs + top movers |
| **Conversation state** | Managed by Snowflake (Threads) | Managed in Streamlit session state |
| **LLM choice** | Snowflake picks automatically | You choose (Cortex model or Azure) |
| **Custom logic** | Stored procedures / UDFs as tools | Python functions in `agent.py` |
| **Error handling** | Agent reflects and retries autonomously | Deterministic retry with schema context |
| **Deployment** | Snowflake-native (no app server) | Streamlit app (you host it) |
| **Vendor lock-in** | High (Snowflake only) | Low (swap provider or data source) |

### The Key Architectural Difference

**Cortex Agents** are *autonomous* — the LLM decides what to do next. Think of it as giving the AI a toolkit and saying: *"Figure out how to answer this."* This is powerful for open-ended questions but less predictable.

**This app** is *deterministic* — the Python code controls every step. The LLM is only called at specific moments with specific instructions. Think of it as: *"I'll tell you exactly when to speak and what to talk about."* This is more predictable and easier to debug, but less flexible.

```
Cortex Agent (autonomous):                    This App (deterministic):
┌──────────┐                                  ┌──────────┐
│ User asks│                                  │ User asks│
│ question │                                  │ question │
└────┬─────┘                                  └────┬─────┘
     │                                              │
     ▼                                              ▼
┌──────────┐  ← Agent decides                ┌──────────┐  ← Code decides
│ Plan     │     what to do                  │ Turn 1   │     (always SQL)
│ sub-tasks│                                  │ Gen SQL  │
└────┬─────┘                                  └────┬─────┘
     │                                              │
     ▼                                              ▼
┌──────────┐  ← Picks Analyst,               ┌──────────┐  ← Always runs on
│ Call tool│     Search, or custom            │ Execute  │     Snowflake
│ (varies) │                                  │ on SF    │
└────┬─────┘                                  └────┬─────┘
     │                                              │
     ▼                                              ▼
┌──────────┐  ← Checks if done,              ┌──────────┐  ← Always analyze
│ Reflect  │     maybe calls more tools      │ Turn 2   │     the results
│ & iterate│                                  │ Analyze  │
└────┬─────┘                                  └────┬─────┘
     │                                              │
     ▼                                              ▼
┌──────────┐                                  ┌──────────┐
│ Response │  (data only)                     │ Dashboard│  (KPIs + charts +
└──────────┘                                  └──────────┘   narrative)
```

### When to Use Which

| Scenario | Best Choice |
|----------|-------------|
| Open-ended questions across structured + unstructured data | **Cortex Agents** — can route to Analyst + Search |
| Structured MoM comparison with full analytical output | **This app** — purpose-built, predictable, rich output |
| Need the LLM to autonomously decide what to query | **Cortex Agents** — agentic planning |
| Need deterministic, reproducible analysis pipeline | **This app** — fixed flow, easy to audit |
| Quick deployment with zero app code | **Cortex Agents** — Snowflake-native |
| Custom narrative, KPIs, and branded dashboard | **This app** — full UI control |
| Querying PDFs, reports, or documents alongside tables | **Cortex Agents** — Cortex Search integration |

---

## Does This App Align with Snowflake's Roadmap?

**Short answer: Yes — more than you might think.**

### Snowflake's "Skills" Concept

In 2026, Snowflake introduced a **Skills framework** (primarily through Cortex Code) that is remarkably similar to what this app already does:

| Snowflake's Skills Concept | This App's `skills/` Folder |
|----------------------------|---------------------------|
| Reusable, shareable workflows defined in **markdown files** | Reusable playbook defined in **markdown files** |
| Codifies complex procedures into "playbooks" that others can execute | Codifies data model, SQL patterns, and analysis templates into a playbook the LLM executes |
| Used to institutionalize best practices across teams | Encodes business-specific metric formulas and analysis rules |
| Discoverable and modular | Organized by subfolder: `sql-patterns/`, `analysis/`, `references/` |

The naming overlap is not a coincidence. **Snowflake is moving toward the same pattern this app already uses**: markdown-based knowledge files that teach AI agents how to do specific tasks.

### Roadmap Alignment Scorecard

| Snowflake Direction (2025–2026) | This App | Alignment |
|--------------------------------|----------|-----------|
| **Agentic AI** — agents that plan, act, and reflect | Two-turn orchestrator with follow-up chat | ⚠️ Partial — deterministic, not fully autonomous |
| **Skills framework** — markdown-based reusable workflows | `skills/` folder with data model, SQL patterns, analysis templates | ✅ Strong match |
| **Semantic models** — structured metadata for accurate SQL | Playbook contains data model, metric formulas, dimension definitions | ✅ Conceptually equivalent |
| **Multi-source reasoning** (structured + unstructured) | Structured data only | ❌ Not supported |
| **Governed AI** — RBAC, audit, security perimeter | Inherits Snowflake session credentials | ⚠️ Partial |
| **Human-AI collaboration** — users guide, AI executes | Follow-up chat, dimension selection, metric picker | ✅ Yes |
| **Custom tools** — stored procs as agent capabilities | Not using stored procs; custom Python functions instead | ⚠️ Different approach |
| **Data-to-Chart** — auto-generated visualizations | Built-in Plotly charts | ✅ Already does this (different tech) |

### What This Means for the Future

This app is not fighting Snowflake's direction — it's **running ahead of it** in some areas (narrative generation, analysis output) and **running parallel** in others (skills-based playbooks). Here's a realistic evolution path:

1. **Now** — The app works independently with its own skills playbook and LLM orchestration.
2. **Near-term** — Swap the markdown playbook for a Snowflake **Semantic View** as the schema source, while keeping the custom analysis and narrative layer.
3. **Mid-term** — Register the analysis logic as a **custom tool** (stored procedure) within a Cortex Agent, so the agent can call it alongside Cortex Analyst and Cortex Search.
4. **Long-term** — The app's `skills/` folder could become a Snowflake-native **Skill** that any Cortex Agent can use, making the MoM analysis pattern available organization-wide.

**The bottom line**: This app anticipated Snowflake's direction. The `skills/` folder is essentially a proto-Skill, and the two-turn orchestration pattern is a simpler version of what Cortex Agents do. The app can evolve alongside Snowflake's roadmap rather than being replaced by it.

---

## 10 Things Every Expert Should Know When Presenting to Business Users

### 1. No SQL is hardcoded — the AI writes it every time
The app doesn't contain pre-built queries. Each time you click Compare, the AI reads the playbook and generates fresh SQL. This means it adapts to whatever dimensions you pick.

### 2. The "skills playbook" is the app's brain
The `skills/` folder contains the data model, SQL patterns, and analysis templates. If the business needs change (new metrics, new dimensions), you update the playbook — not the application code.

### 3. Follow-up questions can go beyond your initial selection
If you compared by Customer and Port but then ask *"What about by Supplier?"*, the AI generates new queries for that dimension automatically. You don't need to re-run the comparison.

### 4. Margin is always computed correctly (GP ÷ Volume)
Margin is never summed or averaged directly. It's always recalculated as `SUM(GP) / SUM(Volume)` at whatever aggregation level you're looking at. This prevents misleading averages.

### 5. The data is live from Snowflake
Every comparison queries Snowflake in real time. There's no stale cache or overnight batch — you're seeing the current state of the data.

### 6. The AI can make mistakes — and the app handles it
LLMs can occasionally generate SQL with wrong column names. The app has a built-in correction layer that catches common mistakes and a retry mechanism that sends errors back to the AI for self-correction.

### 7. KPI cards show Month B values with change deltas
The KPI cards display the **latest month's value** with the change from the baseline month. Green = improvement, red = decline (inverted for "Lost" where fewer is better).

### 8. Charts show the top 20 by absolute change
To keep visuals readable, charts automatically show only the 20 dimension values with the largest changes. The full data is available in the expandable raw data tables.

### 9. The app supports two LLM providers
You can toggle between **Snowflake Cortex** (runs inside your Snowflake account) and **Azure AI Foundry** (external API). Cortex keeps all data within Snowflake's security boundary.

### 10. Everything is read-only
The app only runs SELECT queries. It cannot insert, update, delete, or modify any data. A built-in safety check rejects any non-SELECT SQL before it reaches Snowflake.
