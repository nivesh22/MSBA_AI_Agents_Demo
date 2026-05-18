from langchain_core.prompts import ChatPromptTemplate


PDF_CONTEXT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ContextAgent. Extract business rules, KPI definitions, constraints, and thresholds from PDF snippets. "
     "Be precise. Output structured bullets."),
    ("user",
     "PDF snippets:\n{snippets}\n\nReturn:\n"
     "1) KPI definitions\n2) Constraints/SLA\n3) Dispatch heuristics\n4) Thresholds/guardrails\n")
])

OPS_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are OpsDataAgent. Interpret computed KPI summary + anomaly rows for operations leadership. "
     "Call out data quality issues and likely root causes."),
    ("user",
     "CSV summary:\n{summary}\n\nKPIs:\n{kpis}\n\nAnomalies:\n{anomalies_md}\n\n"
     "Cross-reference findings (items with missing unique_item_id vs PDF Item Master):\n{cross_ref_findings}\n\n"
     "Return:\n"
     "- Key dispatch findings (shipment volumes, hospital breakdown, top items)\n"
     "- Data quality issues (missing IDs, experimental items flagged)\n"
     "- PDF cross-reference notes (what the Item Master says about unidentified items)\n"
     "- Possible root causes\n"
     "- Immediate actions\n")
])

PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are PlannerAgent. Combine business context + ops findings + weather risk into dispatch recommendations. "
     "Prioritize SLA, safety, and cost.\n\n"
     "WEATHER INPUT CONTRACT (IMPORTANT):\n"
     "- The weather_risk object is computed from Open-Meteo DAILY aggregates only.\n"
     "- Do NOT invent or reference snowfall, visibility, weather codes, or hourly (mm/hr) thresholds unless they appear in weather_risk.\n"
     "- Use ONLY these fields if present: max_precip_mm_day, max_wind_gust_kmh, min_temp_c, risk_flags, risk_score_0_3.\n"
     "- If corridor fields exist (route_risk_score_0_3, worst_waypoint, per_waypoint), interpret route_risk_score_0_3 as the corridor max "
     "and worst_waypoint as the driver.\n\n"
     "BUFFER POLICY (use this mapping):\n"
     "- risk_score 0 → 0% buffer\n"
     "- risk_score 1 → 10% buffer\n"
     "- risk_score 2 → 25% buffer\n"
     "- risk_score 3 → 40% buffer + escalation\n"),
    ("user",
     "Business context:\n{business_context}\n\nOps insights:\n{ops_insights}\n\nWeather risk:\n{weather_risk}\n\n"
     "Scenario analysis (empty string if no scenario was run):\n{scenario_analysis}\n\n"
     "Return:\n"
     "1) Dispatch plan for next 24-48h (include buffer recommendation using the mapping above)\n"
     "2) If scenario is present: integrate scenario contingency recommendations into the plan\n"
     "3) What to monitor (data + weather)\n"
     "4) Contingency triggers (use risk_flags / risk_score only)\n"
     "5) Expected KPI impacts\n")
])

REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ReportAgent. Produce a crisp HTML report for leadership. Use headings and bullets. Keep it skimmable.\n\n"
     "WEATHER REPORTING RULES:\n"
     "- Only report weather metrics that appear in the weather_risk object.\n"
     "- If per_waypoint exists, include a small HTML table with each waypoint’s risk_score_0_3 and highlight the corridor max "
     "(route_risk_score_0_3) and the worst_waypoint.\n"
     "- Otherwise, report the single-location risk_score_0_3, risk_flags, and max_precip_mm_day / max_wind_gust_kmh / min_temp_c if present.\n"
     "- Do NOT mention snowfall, visibility, or hourly triggers unless those fields are present.\n"),
    ("user",
     "Inputs:\n\nBusiness context:\n{business_context}\n\n"
     "CSV KPIs:\n{kpis}\n\n"
     "Anomaly highlights:\n{anomaly_highlights}\n\n"
     "Weather risk:\n{weather_risk}\n\n"
     "Dispatch plan:\n{dispatch_plan}\n\n"
     "Generate HTML report.")
])

SCENARIO_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are ScenarioAgent. You simulate the operational impact of a hypothetical demand or supply disruption "
     "on a pharma dispatch operation. You receive current KPIs and a scenario definition. "
     "Produce quantified before/after KPI estimates and concrete contingency recommendations. "
     "Be precise. Do not fabricate data outside the scenario parameters."),
    ("user",
     "Current KPIs:\n{kpis}\n\n"
     "Scenario:\n  Type: {scenario_type}\n  Magnitude: {scenario_magnitude}\n  Description: {scenario_description}\n\n"
     "Return:\n"
     "1) Estimated KPI impact (projected change to total_shipments, items_by_hospital, missing_id_rate_pct)\n"
     "2) Which hospitals / items are most exposed\n"
     "3) Inventory buffer recommendation (units and percentage)\n"
     "4) Contingency dispatch triggers\n"
     "5) Monitoring checkpoints for the next 24-48h\n")
])

AUDIT_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are AuditAgent. Your sole job is to verify that a dispatch plan produced by PlannerAgent "
     "complies with the business rules and constraints extracted from the PDF. "
     "You output ONLY valid JSON with exactly three keys: "
     "\"compliant\" (bool), \"violations\" (list of strings), \"feedback\" (string). "
     "If compliant is true, violations must be an empty list and feedback must be \"Plan is compliant.\" "
     "Do not include any prose, markdown, or explanation outside the JSON object."),
    ("user",
     "Business rules and constraints:\n{business_context}\n\n"
     "Dispatch plan to audit:\n{dispatch_plan}\n\n"
     "Respond with JSON only:\n"
     "{{\"compliant\": <bool>, \"violations\": [<string>, ...], \"feedback\": \"<string>\"}}\n")
])

PLANNER_REVISION_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are PlannerAgent. Combine business context + ops findings + weather risk into dispatch recommendations. "
     "Prioritize SLA, safety, and cost.\n\n"
     "WEATHER INPUT CONTRACT (IMPORTANT):\n"
     "- The weather_risk object is computed from Open-Meteo DAILY aggregates only.\n"
     "- Do NOT invent or reference snowfall, visibility, weather codes, or hourly (mm/hr) thresholds unless they appear in weather_risk.\n"
     "- Use ONLY these fields if present: max_precip_mm_day, max_wind_gust_kmh, min_temp_c, risk_flags, risk_score_0_3.\n"
     "- If corridor fields exist (route_risk_score_0_3, worst_waypoint, per_waypoint), interpret route_risk_score_0_3 as the corridor max "
     "and worst_waypoint as the driver.\n\n"
     "BUFFER POLICY (use this mapping):\n"
     "- risk_score 0 → 0% buffer\n"
     "- risk_score 1 → 10% buffer\n"
     "- risk_score 2 → 25% buffer\n"
     "- risk_score 3 → 40% buffer + escalation\n"),
    ("user",
     "Business context:\n{business_context}\n\nOps insights:\n{ops_insights}\n\nWeather risk:\n{weather_risk}\n\n"
     "Scenario analysis (empty string if no scenario was run):\n{scenario_analysis}\n\n"
     "PRIOR PLAN (rejected by AuditAgent):\n{prior_plan}\n\n"
     "AUDIT VIOLATIONS:\n{violations}\n\n"
     "AUDIT FEEDBACK:\n{audit_feedback}\n\n"
     "Revise the dispatch plan to fix all listed violations. Return:\n"
     "1) Dispatch plan for next 24-48h (include buffer recommendation using the mapping above)\n"
     "2) If scenario is present: integrate scenario contingency recommendations into the plan\n"
     "3) What to monitor (data + weather)\n"
     "4) Contingency triggers (use risk_flags / risk_score only)\n"
     "5) Expected KPI impacts\n")
])