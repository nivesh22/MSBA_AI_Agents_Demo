from __future__ import annotations

import os
from typing import TypedDict, Dict, Any, List

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from tools.pdf_tools import PdfRag
from tools.csv_tools import analyze_csv
from tools.weather_tools import get_weather_forecast, derive_dispatch_weather_risk
from tools.email_tools import send_email_smtp
from agents import (
    run_context_agent,
    run_ops_agent,
    run_planner_agent,
    run_planner_revision_agent,
    run_scenario_agent,
    run_audit_agent,
    run_report_agent,
)

load_dotenv()

# Authoritative corridor waypoints (from SeeWeeS Playbook v0.2, Section 3.2)
CORRIDOR_WAYPOINTS: Dict[str, List[Dict[str, Any]]] = {
    "C1_I95_NJ_BOS": [
        {"id": "C1_W1", "city": "Newark NJ",      "lat": 40.7357, "lon": -74.1724},
        {"id": "C1_W2", "city": "Bronx NY",        "lat": 40.8448, "lon": -73.8648},
        {"id": "C1_W3", "city": "New Haven CT",    "lat": 41.3083, "lon": -72.9279},
        {"id": "C1_W4", "city": "Providence RI",   "lat": 41.8240, "lon": -71.4128},
        {"id": "C1_W5", "city": "Boston MA",       "lat": 42.3601, "lon": -71.0589},
    ],
    "C2_NJ_PHL": [
        {"id": "C2_W1", "city": "Newark NJ",       "lat": 40.7357, "lon": -74.1724},
        {"id": "C2_W2", "city": "New Brunswick NJ","lat": 40.4862, "lon": -74.4518},
        {"id": "C2_W3", "city": "Trenton NJ",      "lat": 40.2204, "lon": -74.7643},
        {"id": "C2_W4", "city": "Philadelphia PA", "lat": 39.9526, "lon": -75.1652},
    ],
}


class AppState(TypedDict, total=False):
    # Inputs
    pdf_path: str
    csv_path: str
    resources_path: str
    scenario: Dict[str, Any]

    # PDF / playbook context
    business_context: str
    pdf_retriever: Any

    # CSV analysis
    csv_summary: Dict[str, Any]
    csv_kpis: Dict[str, Any]
    multi_corridor_kpis: Dict[str, Any]
    resource_constraints: Dict[str, Any]
    anomalies_md: str
    cross_ref_findings: List[Dict[str, Any]]
    ops_insights: str

    # Scenario simulation
    scenario_analysis: str

    # Weather (per-corridor + global summary)
    weather_risk: Dict[str, Any]
    weather_risk_by_corridor: Dict[str, Any]

    # Planning + audit loop
    dispatch_plan: str
    audit_result: Dict[str, Any]
    audit_iteration: int

    # Report
    report_html: str


def node_pdf_context(state: AppState) -> AppState:
    pdf_path = state["pdf_path"]

    if pdf_path.endswith(".md"):
        with open(pdf_path, "r") as f:
            text = f.read()
        business_context = run_context_agent(text)
        return {"business_context": business_context, "pdf_retriever": None}

    # Fallback: PDF via ChromaDB RAG
    rag = PdfRag(persist_dir="chroma_db")
    vectordb = rag.build(pdf_path)
    retriever = rag.retriever(vectordb, k=6)
    query = "Extract KPI definitions, thresholds, SLAs, constraints, dispatch rules, exceptions."
    docs = retriever.invoke(query)
    snippets = "\n\n---\n\n".join(d.page_content for d in docs)
    business_context = run_context_agent(snippets)
    return {"business_context": business_context, "pdf_retriever": retriever}


def node_csv_analysis(state: AppState) -> AppState:
    res = analyze_csv(
        state["csv_path"],
        retriever=state.get("pdf_retriever"),
        resources_path=state.get("resources_path"),
    )

    anomalies_md = "(none detected)"
    if not res.anomalies.empty:
        anomalies_md = res.anomalies.head(12).to_markdown(index=False)

    ops_insights = run_ops_agent(
        summary=res.summary,
        kpis=res.kpis,
        multi_corridor_kpis=res.multi_corridor_kpis,
        resource_constraints=res.resource_constraints,
        anomalies_md=anomalies_md,
        cross_ref_findings=res.cross_ref_findings,
    )

    return {
        "csv_summary":        res.summary,
        "csv_kpis":           res.kpis,
        "multi_corridor_kpis": res.multi_corridor_kpis,
        "resource_constraints": res.resource_constraints,
        "anomalies_md":       anomalies_md,
        "cross_ref_findings": res.cross_ref_findings,
        "ops_insights":       ops_insights,
    }


def node_scenario(state: AppState) -> AppState:
    scenario = state.get("scenario")
    if not scenario:
        return {"scenario_analysis": ""}
    result = run_scenario_agent(kpis=state.get("csv_kpis", {}), scenario=scenario)
    return {"scenario_analysis": result}


def node_weather(state: AppState) -> AppState:
    tz = os.getenv("WEATHER_TZ", "America/New_York")
    weather_risk_by_corridor: Dict[str, Any] = {}

    for corridor_id, waypoints in CORRIDOR_WAYPOINTS.items():
        per_waypoint: List[Dict[str, Any]] = []
        day0_scores: List[int] = []
        day1_scores: List[int] = []

        for wp in waypoints:
            forecast = get_weather_forecast(str(wp["lat"]), str(wp["lon"]), tz)
            daily    = forecast.get("daily", {})
            precip   = daily.get("precipitation_sum", []) or []
            gusts    = daily.get("wind_gusts_10m_max", []) or []
            tmin     = daily.get("temperature_2m_min", []) or []

            for day_idx, day_label in enumerate(["Day0", "Day1"]):
                p = precip[day_idx] if day_idx < len(precip) else 0.0
                g = gusts[day_idx]  if day_idx < len(gusts)  else 0.0
                t = tmin[day_idx]   if day_idx < len(tmin)   else None
                flags = {
                    "heavy_rain_risk": p >= 15.0,
                    "high_wind_risk":  g >= 45.0,
                    "freezing_risk":   t is not None and t <= 0.0,
                }
                score = int(flags["heavy_rain_risk"]) + int(flags["high_wind_risk"]) + int(flags["freezing_risk"])
                per_waypoint.append({
                    "waypoint": wp["id"], "city": wp["city"], "day": day_label,
                    "precip_mm_day": round(p, 2), "wind_gust_kmh": round(g, 2),
                    "min_temp_c": round(t, 1) if t is not None else None,
                    "risk_flags": flags, "risk_score_0_3": score,
                })
                (day0_scores if day_label == "Day0" else day1_scores).append(score)

        day0_risk    = max(day0_scores) if day0_scores else 0
        day1_risk    = max(day1_scores) if day1_scores else 0
        corridor_risk = max(day0_risk, day1_risk)

        weather_risk_by_corridor[corridor_id] = {
            "corridor_48h_risk_score_0_3": corridor_risk,
            "day0_risk_score": day0_risk,
            "day1_risk_score": day1_risk,
            "per_waypoint":   per_waypoint,
        }

    # Global summary for backward-compat with planner/audit/report
    all_wps    = [wp for c in weather_risk_by_corridor.values() for wp in c["per_waypoint"]]
    worst_wp   = max(all_wps, key=lambda w: w["risk_score_0_3"]) if all_wps else {}
    max_score  = max((c["corridor_48h_risk_score_0_3"] for c in weather_risk_by_corridor.values()), default=0)

    weather_risk = {
        "route_risk_score_0_3": max_score,
        "worst_waypoint":       worst_wp,
        "by_corridor":          weather_risk_by_corridor,
    }
    if worst_wp:
        weather_risk.update({
            "max_precip_mm_day":  worst_wp.get("precip_mm_day"),
            "max_wind_gust_kmh":  worst_wp.get("wind_gust_kmh"),
            "min_temp_c":         worst_wp.get("min_temp_c"),
            "risk_flags":         worst_wp.get("risk_flags"),
            "risk_score_0_3":     worst_wp.get("risk_score_0_3"),
        })

    print("\n===== WEATHER_RISK BY CORRIDOR =====")
    for cid, cr in weather_risk_by_corridor.items():
        print(f"  {cid}: Day0={cr['day0_risk_score']} Day1={cr['day1_risk_score']} 48h={cr['corridor_48h_risk_score_0_3']}")
    print("=====================================\n")
    return {"weather_risk": weather_risk, "weather_risk_by_corridor": weather_risk_by_corridor}


def node_planner(state: AppState) -> AppState:
    plan = run_planner_agent(
        business_context=state.get("business_context", ""),
        ops_insights=state.get("ops_insights", ""),
        weather_risk=state.get("weather_risk", {}),
        weather_risk_by_corridor=state.get("weather_risk_by_corridor", {}),
        multi_corridor_kpis=state.get("multi_corridor_kpis", {}),
        resource_constraints=state.get("resource_constraints", {}),
        scenario_analysis=state.get("scenario_analysis", ""),
    )
    return {"dispatch_plan": plan}


def node_audit(state: AppState) -> AppState:
    result = run_audit_agent(
        business_context=state.get("business_context", ""),
        dispatch_plan=state.get("dispatch_plan", ""),
    )
    iteration = state.get("audit_iteration", 0) + 1
    print(f"\n===== AUDIT (iteration {iteration}) =====")
    print(f"compliant={result.get('compliant')}  violations={result.get('violations')}")
    print("==========================================\n")
    return {"audit_result": result, "audit_iteration": iteration}


def node_planner_revision(state: AppState) -> AppState:
    audit  = state.get("audit_result", {})
    revised = run_planner_revision_agent(
        business_context=state.get("business_context", ""),
        ops_insights=state.get("ops_insights", ""),
        weather_risk=state.get("weather_risk", {}),
        weather_risk_by_corridor=state.get("weather_risk_by_corridor", {}),
        multi_corridor_kpis=state.get("multi_corridor_kpis", {}),
        resource_constraints=state.get("resource_constraints", {}),
        scenario_analysis=state.get("scenario_analysis", ""),
        prior_plan=state.get("dispatch_plan", ""),
        audit_feedback=audit.get("feedback", ""),
        violations=audit.get("violations", []),
    )
    return {"dispatch_plan": revised}


def route_after_audit(state: AppState) -> str:
    MAX_ITERATIONS = 3
    audit     = state.get("audit_result", {})
    iteration = state.get("audit_iteration", 0)
    if audit.get("compliant", False) or iteration >= MAX_ITERATIONS:
        return "report"
    return "planner_revision"


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines).strip()
    return text


def node_report(state: AppState) -> AppState:
    html = run_report_agent(
        business_context=state.get("business_context", ""),
        kpis=state.get("csv_kpis", {}),
        multi_corridor_kpis=state.get("multi_corridor_kpis", {}),
        anomaly_highlights=state.get("anomalies_md", "(none)"),
        weather_risk=state.get("weather_risk", {}),
        weather_risk_by_corridor=state.get("weather_risk_by_corridor", {}),
        resource_constraints=state.get("resource_constraints", {}),
        dispatch_plan=state.get("dispatch_plan", ""),
    )
    return {"report_html": _strip_code_fences(html)}


def node_email(state: AppState) -> AppState:
    to_email = os.getenv("REPORT_EMAIL_TO", "").strip()
    if not to_email:
        print("REPORT_EMAIL_TO not set -> skipping email send.")
        return {}
    subject = "MSBA Ops Multi-Agent Dispatch Report"
    send_email_smtp(subject=subject, html_body=state["report_html"], to_email=to_email)
    return {}


def build_graph():
    g = StateGraph(AppState)

    g.add_node("pdf_context",      node_pdf_context)
    g.add_node("csv_analysis",     node_csv_analysis)
    g.add_node("scenario",         node_scenario)
    g.add_node("weather",          node_weather)
    g.add_node("planner",          node_planner)
    g.add_node("audit",            node_audit)
    g.add_node("planner_revision", node_planner_revision)
    g.add_node("report",           node_report)
    g.add_node("email",            node_email)

    g.set_entry_point("pdf_context")
    g.add_edge("pdf_context",  "csv_analysis")
    g.add_edge("csv_analysis", "scenario")
    g.add_edge("scenario",     "weather")
    g.add_edge("weather",      "planner")
    g.add_edge("planner",      "audit")
    g.add_edge("planner_revision", "audit")

    g.add_conditional_edges(
        "audit",
        route_after_audit,
        {"report": "report", "planner_revision": "planner_revision"},
    )

    g.add_edge("report", "email")
    g.add_edge("email",  END)

    return g.compile()
