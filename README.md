# SeeWeeS Ops Multi-Agent Dispatch System

A robust multi-agent AI system built on **LangGraph + LangChain** for real-time pharmaceutical dispatch planning across multiple delivery corridors. Transforms 14-day shipment feeds, resource constraints, and a structured operations playbook into leadership-ready dispatch reports — with self-correcting planning, what-if scenario simulation, and deep-dive multi-corridor trend analysis.

---

## Enhancements Over Baseline

| # | Enhancement | Description |
|---|---|---|
| 1 | **Self-Correction Audit Loop** | AuditAgent reviews every dispatch plan against playbook business rules. Violations trigger an automated revision cycle (max 3 iterations) before the report is generated. |
| 2 | **What-if Scenario Simulation** | Users inject hypothetical disruptions (demand spike, driver shortage, etc.). ScenarioAgent quantifies per-corridor KPI impact and generates contingency recommendations integrated into the dispatch plan. |
| 3 | **Deep-Dive Multi-Corridor Analysis** | Full item master reconciliation (DQ-01..04, legacy ID and alias resolution), per-corridor 48h KPIs, historical trend vs planning window, resource-constrained allocation with explicit penalty scoring. |

---

## Architecture

### Graph Topology

```
[pdf_context] → [csv_analysis] → [scenario] → [weather] → [planner]
                                                                ↓
                                             [planner_revision] ← [audit] (violations & iter < 3)
                                                                      ↓
                                                                 [report] → [email] → END
```

### Agent Roles

| Agent | Node | Responsibility |
|---|---|---|
| **ContextAgent** | `pdf_context` | Reads the Markdown playbook directly; extracts SLAs, DQ rules, corridor definitions, weather thresholds, truck model, and penalty model |
| **OpsDataAgent** | `csv_analysis` | Computes per-corridor KPIs for the 48h planning window, runs item master reconciliation (DQ-01..04), computes truck requirements, and flags resource shortfalls |
| **ScenarioAgent** | `scenario` | Simulates KPI impact of a hypothetical disruption per corridor; produces contingency recommendations |
| **WeatherAgent** | `weather` | Fetches Open-Meteo forecasts for both corridor waypoints (C1: 5 waypoints, C2: 4 waypoints); computes per-corridor Day0/Day1 and 48h risk scores (0–3) |
| **PlannerAgent** | `planner` | Combines business rules + multi-corridor ops insights + per-corridor weather + resource constraints into a 48h corridor-aware dispatch plan with buffer and allocation rationale |
| **AuditAgent** | `audit` | Verifies dispatch plan compliance (SLA tiers, weather buffers, DQ adherence, truck model, penalty model); outputs structured JSON verdict |
| **PlannerRevisionAgent** | `planner_revision` | Rewrites the dispatch plan to fix audit violations; feeds back into audit loop |
| **ReportAgent** | `report` | Produces an 8-section leadership-ready HTML report: corridor comparison, DQ summary, weather by corridor, resource allocation, dispatch plan, SLA flags |
| **EmailAgent** | `email` | Sends the HTML report via SMTP (skipped if `REPORT_EMAIL_TO` is unset) |

### Self-Correction Loop

```
planner → audit
             │
             ├─ compliant=True OR iteration ≥ 3  ──→  report
             │
             └─ compliant=False AND iteration < 3  ──→  planner_revision → audit (repeat)
```

Audit verdict is structured JSON: `{"compliant": bool, "violations": [...], "feedback": str}`.

---

## Corridors

| corridor_id | Route | SLA Tier | Waypoints |
|---|---|---|---|
| `C1_I95_NJ_BOS` | Newark NJ → Boston MA (I-95) | Tier 1 (life-critical, 6h max) | C1_W1..C1_W5 |
| `C2_NJ_PHL` | Newark NJ → Philadelphia PA | Tier 2 (standard specialty, 12h max) | C2_W1..C2_W4 |

---

## KPIs Computed (Enhancement 3)

### Global
| KPI | Description |
|---|---|
| `total_shipments` | All rows across 14-day feed |
| `planning_window_valid` | Valid (non-excluded) units in the 48h window |
| `planning_window_excluded` | Units excluded by DQ rules |
| `missing_id_rate_pct` | % of rows with null/blank `unique_item_id` (DQ-01) |
| `experimental_items_flagged` | Rows with `item_id = 99999` (clinical trial drug) |

### Per-Corridor (Day0 + Day1)
| KPI | Description |
|---|---|
| `total_valid` | Valid dispatch units per corridor per day |
| `excluded` | Excluded units per corridor per day |
| `temp_controlled_units` | Units requiring cold-chain trucks |
| `sla_tier` | Tier 1 (C1) or Tier 2 (C2) |
| `trucks_needed` | Standard + temp-controlled trucks required (incl. 10% packing buffer) |
| `historical_avg_units_per_day` | 12-day baseline average for trend comparison |

### Data Quality (DQ-01..04)
| Rule | Description | Action |
|---|---|---|
| DQ-01 | Missing `unique_item_id` | Exclude from dispatch |
| DQ-02 | `item_id` not in item master | Exclude; flag as unresolved |
| DQ-03 | `item_name` mismatch for valid `item_id` | Flag for investigation; still dispatched |
| DQ-04 | Duplicate `unique_item_id` | Flag for investigation |

Legacy IDs (e.g., `20021`, `1070`) and name aliases (e.g., "EpiPen Auto Injector", "Heparin Na") are resolved against Appendix A and logged with reason codes.

### Resource Allocation
- Available pool: `driver`, `truck_standard`, `truck_temp_controlled` per day (from `Resource_availability_48h.csv`)
- Allocation objective: minimize total penalty score (Tier 1 violation: 100 pts, Tier 2: 40 pts, cold-chain: +80 pts additional)
- Shortfalls and estimated penalty exposure surfaced per corridor per day

---

## Weather Risk Scoring

| Score | Condition | Buffer |
|---|---|---|
| 0 | No triggers | 0% |
| 1 | 1 trigger (precip ≥15mm OR wind ≥45km/h OR temp ≤0°C) | +10% |
| 2 | 2 triggers | +25% |
| 3 | All 3 triggers | +40% + escalation |

Per-corridor 48h risk = max(Day0 corridor risk, Day1 corridor risk), where each day's corridor risk = max waypoint score for that day.

---

## Project Structure

```
MSBA_AI_Agents_Demo/
├── src/
│   ├── main.py                  # Entry point
│   ├── graph.py                 # LangGraph state machine (9 nodes, CORRIDOR_WAYPOINTS)
│   ├── agents.py                # All agent runner functions
│   ├── prompts.py               # ChatPromptTemplates for each agent
│   ├── tracing.py               # LangSmith observability setup
│   └── tools/
│       ├── pdf_tools.py         # PdfRag — ChromaDB-backed PDF retrieval (fallback)
│       ├── csv_tools.py         # analyze_csv() — item master, DQ-01..04, multi-corridor KPIs, resource allocation
│       ├── weather_tools.py     # Open-Meteo API + risk scoring
│       └── email_tools.py       # SMTP sender (SSL/TLS)
├── data/
│   ├── SeeWeeS Specialty Dispatch Playbook.md   # Active: Markdown playbook (read directly)
│   ├── Incoming_shipments_14d_multi_corridor.csv # Active: 14-day, 2-corridor shipment feed
│   ├── Resource_availability_48h.csv             # Active: driver/truck availability per day
│   ├── SeeWeeS Specialty Dispatch Playbook.pdf   # Legacy (no longer used)
│   └── About SeeWeeS Specialty distribution.pdf # Background reference
├── diagrams/
│   ├── architecture.png         # Full system architecture diagram
│   ├── agent_flow.png           # Agent data flow diagram
│   └── generate_diagrams.py    # Regenerate diagrams: python diagrams/generate_diagrams.py
├── sample_docs/
│   ├── dispatch_report_baseline_2026-05-19.html
│   └── dispatch_report_demand_spike_2026-05-19.html
├── save_report.py               # Runs both pipelines and saves HTML to sample_docs/
├── tests/
│   └── test_smoke.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup

### 1. Create and activate environment

```bash
conda create -n msba_ai_agents python=3.11
conda activate msba_ai_agents
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Required
OPENAI_API_KEY=sk-...

# Email (optional — skipped if REPORT_EMAIL_TO is unset)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
REPORT_EMAIL_TO=recipient@example.com

# Weather timezone
WEATHER_TZ=America/New_York

# LangSmith tracing (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=ls_...
LANGCHAIN_PROJECT=MSBA_AI_Agents_Demo
```

### 3. Run

```bash
python src/main.py
```

The HTML report is printed to stdout (first 2000 chars) and optionally emailed.

To save sample reports for both baseline and scenario runs:

```bash
python save_report.py
# → sample_docs/dispatch_report_baseline_<date>.html
# → sample_docs/dispatch_report_demand_spike_<date>.html
```

---

## What-if Scenario Simulation (Enhancement 2)

To simulate a disruption, uncomment and edit the `scenario` key in `src/main.py`:

```python
state = {
    "pdf_path":       "data/SeeWeeS Specialty Dispatch Playbook.md",
    "csv_path":       "data/Incoming_shipments_14d_multi_corridor.csv",
    "resources_path": "data/Resource_availability_48h.csv",
    "scenario": {
        "type": "demand_spike",
        "magnitude": 0.20,
        "description": "20% surge in Remdesivir demand across both corridors due to regional outbreak.",
    },
}
```

Supported scenario types (freeform — describe any disruption):
- `demand_spike` — sudden increase in demand for specific drugs
- `driver_shortage` — reduced fleet capacity
- `cold_chain_failure` — temperature excursion event
- `corridor_closure` — one corridor unavailable, volume rerouted to other

---

## Technical Stack

| Component | Technology |
|---|---|
| Agent orchestration | LangGraph 0.2+ |
| LLM | OpenAI GPT-4.1-mini (via LangChain) |
| Playbook ingestion | Direct Markdown read (no vector store required) |
| Data analysis | Pandas, NumPy |
| Weather API | Open-Meteo (free, no key required) |
| Observability | LangSmith (optional) |
| Email | SMTP/SSL via smtplib |

---

## Key Design Decisions

- **Markdown playbook over PDF/RAG**: Reading the structured Markdown directly is simpler, faster, and eliminates fragile regex-based waypoint extraction. The `node_pdf_context` node falls back to ChromaDB RAG for `.pdf` inputs.
- **Hardcoded corridor waypoints**: Both corridors' waypoints are defined in `CORRIDOR_WAYPOINTS` in `graph.py`, sourced directly from the playbook. This replaces the prior approach of extracting them from the PDF at runtime via RAG.
- **Item master as code**: Appendix A tables (canonical items, legacy IDs, accepted name aliases) are hardcoded in `csv_tools.py`. This gives deterministic DQ results without needing a retriever.
- **Audit loop bound**: Max 3 audit iterations prevents infinite loops when constraints are ambiguous. The plan at iteration 3 proceeds regardless.
- **Scenario as optional input**: `node_scenario` is always in the graph but no-ops when `scenario` is absent.
- **Structured audit output**: AuditAgent returns only JSON — no prose — reducing parse failures. Malformed responses are treated as non-compliant with a fallback.

---

## Limitations & Next Steps

- **No persistent report storage** — reports are ephemeral. A future version could write to S3 or a database.
- **Single-run, no scheduling** — adding a cron trigger or Airflow DAG would enable daily automated runs.
- **LLM hallucination risk** — audit and planning agents could miss violations or invent constraints. Human-in-the-loop approval would add an additional safeguard.
- **Scenario agent is generative** — it reasons from KPIs but does not run a quantitative simulation model. Integrating a demand forecasting model would improve accuracy.
- **Resource allocation is penalty-estimated, not optimized** — a proper LP/ILP solver (e.g., PuLP) would give a provably optimal allocation rather than a heuristic.
