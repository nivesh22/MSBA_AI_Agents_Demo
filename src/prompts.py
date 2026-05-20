from langchain_core.prompts import ChatPromptTemplate


PDF_CONTEXT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ContextAgent. Extract business rules, KPI definitions, constraints, and thresholds from the playbook. "
     "Be precise. Output structured bullets. Cover: corridors, SLA tiers, weather triggers, buffer policy, "
     "truck capacity model, DQ rules (DQ-01..DQ-04), resource constraints, penalty model."),
    ("user",
     "Playbook content:\n{snippets}\n\nReturn:\n"
     "1) Corridor definitions and SLA tiers\n"
     "2) Weather risk thresholds and buffer policy\n"
     "3) Truck capacity model and packing rules\n"
     "4) Data quality rules (DQ-01..DQ-04)\n"
     "5) Resource constraint policy and penalty model\n"
     "6) Reporting requirements\n")
])

OPS_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are OpsDataAgent. Interpret multi-corridor shipment KPIs for operations leadership. "
     "Focus on the 48-hour planning window, corridor-level differences, data quality, and resource constraints."),
    ("user",
     "Overall CSV summary:\n{summary}\n\n"
     "Global KPIs:\n{kpis}\n\n"
     "Multi-corridor KPIs (per corridor, per day, resource allocation):\n{multi_corridor_kpis}\n\n"
     "Resource constraints (available trucks/drivers per day):\n{resource_constraints}\n\n"
     "Anomaly highlights:\n{anomalies_md}\n\n"
     "Data quality / reconciliation findings:\n{cross_ref_findings}\n\n"
     "Return:\n"
     "- Corridor comparison: volume, Tier mix, excluded rate per corridor for Day0 and Day1\n"
     "- Historical trend: avg daily units per corridor vs planning-window demand\n"
     "- Data quality summary: DQ-01 (missing UID), DQ-02 (invalid ID), DQ-03 (name mismatch), DQ-04 (duplicates); "
     "  legacy/alias resolutions applied\n"
     "- Resource gap: trucks and drivers needed vs available per corridor per day; any shortfall\n"
     "- Estimated penalty exposure if shortfalls occur (Tier 1: 100pts, Tier 2: 40pts, cold-chain: +80pts)\n"
     "- Immediate actions and monitoring priorities\n")
])

_PLANNER_SYSTEM = (
    "You are PlannerAgent. Produce a corridor-aware, resource-constrained dispatch plan for the 48-hour planning window.\n\n"
    "WEATHER CONTRACT:\n"
    "- Use only fields present in weather_risk and weather_risk_by_corridor.\n"
    "- Do NOT reference snowfall, visibility, or hourly thresholds.\n"
    "- Per-corridor: use corridor_48h_risk_score_0_3 (max of Day0/Day1 waypoint scores).\n\n"
    "BUFFER POLICY (apply per corridor based on its risk score):\n"
    "  0 → no buffer | 1 → +10% | 2 → +25% | 3 → +40% + escalation\n\n"
    "RESOURCE CONSTRAINT:\n"
    "- Available pool is shared across both corridors per day.\n"
    "- Allocate to minimize total penalty: Tier 1 SLA violation = 100 pts/unit, "
    "Tier 2 = 40 pts/unit, cold-chain violation = +80 pts/unit additional.\n"
    "- Prioritize Tier 1 (C1_I95_NJ_BOS) cold-chain units first when resources are scarce.\n\n"
    "TRUCK MODEL: each unit = 1 vol unit; truck = 10 vol; +10% packing buffer; "
    "cold-chain items require temp-controlled trucks.\n"
)

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _PLANNER_SYSTEM),
    ("user",
     "Business context (rules and constraints):\n{business_context}\n\n"
     "Ops insights:\n{ops_insights}\n\n"
     "Weather risk (global summary):\n{weather_risk}\n\n"
     "Weather risk by corridor:\n{weather_risk_by_corridor}\n\n"
     "Multi-corridor KPIs (48h planning window + resource allocation):\n{multi_corridor_kpis}\n\n"
     "Resource constraints (available per day):\n{resource_constraints}\n\n"
     "Scenario analysis (empty if none):\n{scenario_analysis}\n\n"
     "Return:\n"
     "1) Per-corridor dispatch plan (Day0 + Day1): valid units, weather buffer applied, trucks allocated\n"
     "2) Resource allocation decision: how trucks/drivers are split between C1 and C2 per day, with rationale\n"
     "3) Penalty score estimate for the proposed allocation\n"
     "4) SLA risk flags (any Tier 1 or cold-chain exposure)\n"
     "5) What to monitor over the 48h window\n"
     "6) Contingency triggers (weather / DQ / resource)\n"
     "7) If scenario present: integrate contingency into plan\n")
])

PLANNER_REVISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _PLANNER_SYSTEM),
    ("user",
     "Business context:\n{business_context}\n\n"
     "Ops insights:\n{ops_insights}\n\n"
     "Weather risk (global):\n{weather_risk}\n\n"
     "Weather risk by corridor:\n{weather_risk_by_corridor}\n\n"
     "Multi-corridor KPIs:\n{multi_corridor_kpis}\n\n"
     "Resource constraints:\n{resource_constraints}\n\n"
     "Scenario analysis:\n{scenario_analysis}\n\n"
     "PRIOR PLAN (rejected by AuditAgent):\n{prior_plan}\n\n"
     "AUDIT VIOLATIONS:\n{violations}\n\n"
     "AUDIT FEEDBACK:\n{audit_feedback}\n\n"
     "Revise the dispatch plan to fix all listed violations. Return the same 7-section structure as the original plan.\n")
])

REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ReportAgent. Produce a crisp HTML report for leadership. Use headings, tables, and bullets. Keep it skimmable.\n\n"
     "WEATHER RULES: Only report fields present in weather_risk / weather_risk_by_corridor. "
     "Include a per-corridor risk table (Day0 / Day1 / 48h). Do NOT invent weather metrics not in the data.\n\n"
     "REQUIRED SECTIONS:\n"
     "1. Executive Summary\n"
     "2. Corridor Comparison Table (C1 vs C2: volume, excluded, Tier mix, temp-controlled units, 48h weather risk)\n"
     "3. Data Quality Summary (DQ-01..DQ-04 counts, legacy/alias resolutions)\n"
     "4. Weather Risk by Corridor (Day0/Day1 per corridor, applied travel buffers)\n"
     "5. Resource Allocation Plan (trucks/drivers by corridor/day, shortfalls, penalty exposure)\n"
     "6. Dispatch Plan Summary\n"
     "7. SLA Risk Flags\n"
     "8. Monitoring & Contingency Triggers\n"),
    ("user",
     "Business context:\n{business_context}\n\n"
     "Global KPIs:\n{kpis}\n\n"
     "Multi-corridor KPIs:\n{multi_corridor_kpis}\n\n"
     "Anomaly highlights:\n{anomaly_highlights}\n\n"
     "Weather risk (global):\n{weather_risk}\n\n"
     "Weather risk by corridor:\n{weather_risk_by_corridor}\n\n"
     "Resource constraints:\n{resource_constraints}\n\n"
     "Dispatch plan:\n{dispatch_plan}\n\n"
     "Generate complete HTML report.")
])

SCENARIO_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ScenarioAgent. Simulate the operational impact of a hypothetical disruption on a multi-corridor "
     "pharma dispatch operation. Produce quantified before/after KPI estimates and concrete contingency recommendations."),
    ("user",
     "Current KPIs:\n{kpis}\n\n"
     "Scenario:\n  Type: {scenario_type}\n  Magnitude: {scenario_magnitude}\n  Description: {scenario_description}\n\n"
     "Return:\n"
     "1) Estimated KPI impact per corridor (projected change to volume, excluded rate, Tier 1/2 mix)\n"
     "2) Which corridor / hospitals / items are most exposed\n"
     "3) Resource reallocation recommendation\n"
     "4) Contingency dispatch triggers\n"
     "5) Monitoring checkpoints for the 48h window\n")
])

AUDIT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are AuditAgent. Verify that the dispatch plan complies with the business rules and constraints. "
     "Check: corridor SLA tiers, weather buffers, DQ rule adherence (DQ-01..DQ-04), "
     "truck capacity model, resource constraint policy, and penalty model usage. "
     "Output ONLY valid JSON with exactly three keys: "
     "\"compliant\" (bool), \"violations\" (list of strings), \"feedback\" (string). "
     "If compliant, violations must be [] and feedback must be \"Plan is compliant.\" "
     "No prose, markdown, or explanation outside the JSON."),
    ("user",
     "Business rules and constraints:\n{business_context}\n\n"
     "Dispatch plan to audit:\n{dispatch_plan}\n\n"
     "Respond with JSON only:\n"
     "{{\"compliant\": <bool>, \"violations\": [<string>, ...], \"feedback\": \"<string>\"}}\n")
])
