# SeeWeeS Ops Multi-Agent Dispatch System

A robust multi-agent AI system built on **LangGraph + LangChain** for real-time pharmaceutical dispatch planning. Transforms raw shipment data and business documentation into leadership-ready dispatch reports — with self-correcting planning, what-if scenario simulation, and deep-dive trend analysis.

---

## Enhancements Over Baseline

| # | Enhancement | Description |
|---|---|---|
| 1 | **Self-Correction Audit Loop** | An AuditAgent reviews every dispatch plan against PDF-extracted business rules. Violations trigger an automated revision cycle (max 3 iterations) before the report is generated. |
| 2 | **What-if Scenario Simulation** | Users inject hypothetical disruptions (demand spike, driver shortage, etc.). ScenarioAgent quantifies KPI impact and generates contingency recommendations integrated into the dispatch plan. |
| 3 | **Deep-Dive Trend Analysis** | Domain-specific pharma KPIs replace generic statistics. Items with missing identifiers are cross-referenced against the PDF Item Master Appendix to surface substitution and traceability information. |

---

## Architecture

### Graph Topology

```
[pdf_context] → [csv_analysis] → [scenario] → [weather] → [planner]
                                                                ↓
                                             [planner_revision] ← [audit] (if violations & iter < 3)
                                                                      ↓
                                                                 [report] → [email] → END
```

### Agent Roles

| Agent | Node | Responsibility |
|---|---|---|
| **ContextAgent** | `pdf_context` | Extracts KPI definitions, SLAs, dispatch rules, and constraints from PDF via RAG (ChromaDB) |
| **OpsDataAgent** | `csv_analysis` | Computes pharma-specific KPIs, detects anomalies, cross-references missing item IDs with PDF |
| **ScenarioAgent** | `scenario` | Simulates KPI impact of a hypothetical disruption; produces contingency recommendations |
| **WeatherAgent** | `weather` | Fetches Open-Meteo forecasts for all I-95 corridor waypoints; computes per-waypoint and route-level risk scores (0–3) |
| **PlannerAgent** | `planner` | Combines business rules + ops insights + weather risk (+ scenario) into a 24–48h dispatch plan with buffer policy |
| **AuditAgent** | `audit` | Verifies dispatch plan compliance against PDF constraints; outputs structured JSON verdict |
| **PlannerRevisionAgent** | `planner_revision` | Rewrites the dispatch plan to fix audit violations; feeds back into audit loop |
| **ReportAgent** | `report` | Produces a leadership-ready HTML report (skimmable, decision-oriented) |
| **EmailAgent** | `email` | Sends the HTML report via SMTP (skipped if `REPORT_EMAIL_TO` is unset) |

### Self-Correction Loop Detail

```
planner → audit
             │
             ├─ compliant=True OR iteration ≥ 3  ──→  report
             │
             └─ compliant=False AND iteration < 3  ──→  planner_revision → audit (repeat)
```

The audit verdict is structured JSON: `{"compliant": bool, "violations": [...], "feedback": str}`.  
Console output per cycle: `===== AUDIT (iteration N) =====`

---

## KPIs Computed (Enhancement 3)

| KPI | Description |
|---|---|
| `total_shipments` | Total shipment rows after cleaning |
| `unique_item_types` | Count of distinct drug names |
| `missing_id_rate_pct` | % of rows with null/blank `unique_item_id` |
| `missing_id_count` | Absolute count of missing IDs |
| `dispatch_locations` | Number of distinct hospital destinations |
| `items_by_hospital` | Shipment count per hospital |
| `top_5_items` | Five most frequently dispatched drugs |
| `experimental_items_flagged` | Rows where `item_id` starts with "9" (e.g., experimental drug 99999) |

Missing-ID rows are additionally cross-referenced against the **Item Master Appendix** in the PDF, surfacing traceability and substitution notes.

---

## Weather Risk Scoring

| Score | Conditions | Buffer Policy |
|---|---|---|
| 0 | Normal | 0% buffer |
| 1 | Moderate precipitation or wind | 10% buffer |
| 2 | Heavy rain (≥15 mm/day) OR high wind (≥45 km/h) | 25% buffer |
| 3 | Multiple hazards or freezing (≤0°C) | 40% buffer + escalation |

Waypoints W1–W5 along the I-95 corridor are fetched from the PDF via RAG; per-waypoint scores roll up to a route-level max.

---

## Project Structure

```
MSBA_AI_Agents_Demo/
├── src/
│   ├── main.py                  # Entry point
│   ├── graph.py                 # LangGraph state machine (9 nodes)
│   ├── agents.py                # All agent runner functions
│   ├── prompts.py               # ChatPromptTemplates for each agent
│   ├── tracing.py               # LangSmith observability setup
│   └── tools/
│       ├── pdf_tools.py         # PdfRag — ChromaDB-backed PDF retrieval
│       ├── csv_tools.py         # analyze_csv() — KPIs + anomalies + PDF cross-ref
│       ├── weather_tools.py     # Open-Meteo API + risk scoring
│       └── email_tools.py       # SMTP sender (SSL/TLS)
├── data/
│   ├── SeeWeeS Specialty Dispatch Playbook.pdf
│   ├── About SeeWeeS Specialty distribution.pdf
│   └── Incoming_shipment_03_06.csv
├── diagrams/
│   ├── architecture.png         # Full system architecture diagram
│   └── agent_flow.png           # Agent data flow diagram
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
# Using conda (recommended)
conda create -n msba_ai_agents python=3.11
conda activate msba_ai_agents
pip install -r requirements.txt

# OR using venv
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
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
SMTP_PASSWORD=your-app-password      # Gmail: Settings → Security → App Passwords
REPORT_EMAIL_TO=recipient@example.com

# Weather fallback (used if waypoint extraction fails)
WEATHER_LAT=40.7282
WEATHER_LON=-74.0776
WEATHER_TZ=America/New_York

# LangSmith tracing (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=ls_...
LANGCHAIN_PROJECT=MSBA_AI_Agents_Demo
```

### 3. Run

```bash
cd src
python main.py
```

The HTML report is printed to stdout (first 2000 chars) and optionally emailed.

---

## What-if Scenario Simulation (Enhancement 2)

To simulate a disruption, uncomment and edit the `scenario` key in `src/main.py`:

```python
state = {
    "pdf_path": "data/SeeWeeS Specialty Dispatch Playbook.pdf",
    "csv_path": "data/Incoming_shipment_03_06.csv",
    "scenario": {
        "type": "demand_spike",
        "magnitude": 0.20,
        "description": "20% increase in Remdesivir demand from Boston-MGH due to outbreak.",
    },
}
```

Supported scenario types (freeform — describe any disruption):
- `demand_spike` — sudden increase in demand for specific drugs
- `warehouse_closure` — primary distribution center offline
- `driver_shortage` — reduced fleet capacity
- `cold_chain_failure` — temperature excursion event

---

## Technical Stack

| Component | Technology |
|---|---|
| Agent orchestration | LangGraph 0.2+ |
| LLM | OpenAI GPT-4.1-mini (via LangChain) |
| Vector store | ChromaDB (local) |
| PDF parsing | PyPDF |
| Data analysis | Pandas, NumPy, Scikit-learn |
| Anomaly detection | Isolation Forest |
| Weather API | Open-Meteo (free, no key required) |
| Observability | LangSmith (optional) |

---

## Key Design Decisions

- **Retriever reuse**: The ChromaDB retriever built in `pdf_context` is passed through `AppState` (`pdf_retriever`) so `csv_analysis` can perform PDF cross-referencing without rebuilding the vector store.
- **Audit loop bound**: Max 3 audit iterations prevents infinite loops when constraints are ambiguous or irresolvable. The plan at iteration 3 proceeds regardless.
- **Scenario as optional input**: `node_scenario` is always in the graph but no-ops when `scenario` is absent, keeping the baseline run path identical to the original system.
- **Structured audit output**: AuditAgent is instructed to return only JSON — no prose — reducing parse failures. A fallback handles malformed responses by treating them as non-compliant.

---

## Limitations & Next Steps

- **Waypoint parsing is regex-based** — fragile if PDF table formatting changes. A layout-aware PDF parser (e.g., pdfplumber) would be more robust.
- **No persistent report storage** — reports are ephemeral. A future version could write to S3 or a database.
- **Single-run, no scheduling** — adding a cron trigger or Airflow DAG would enable daily automated runs.
- **LLM hallucination risk** — audit and planning agents could miss violations or invent constraints. Human-in-the-loop approval (Enhancement 4 from the project spec) would add an additional safeguard.
- **Scenario agent is purely generative** — it reasons from KPIs but does not run a quantitative simulation model. Integrating a demand forecasting model would significantly improve accuracy.
