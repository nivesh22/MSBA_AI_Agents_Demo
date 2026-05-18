from __future__ import annotations

import os
import re
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


class AppState(TypedDict, total=False):
    # Inputs
    pdf_path: str
    csv_path: str
    scenario: Dict[str, Any]           # Enhancement 2: optional {"type", "magnitude", "description"}

    # PDF context
    business_context: str
    pdf_retriever: Any                 # Enhancement 3: in-process retriever, reused by csv_analysis

    # CSV analysis
    csv_summary: Dict[str, Any]
    csv_kpis: Dict[str, Any]
    anomalies_md: str
    cross_ref_findings: List[Dict[str, Any]]   # Enhancement 3: missing-ID cross-refs
    ops_insights: str

    # Scenario simulation
    scenario_analysis: str             # Enhancement 2: ScenarioAgent output

    # Weather
    weather_risk: Dict[str, Any]

    # Planning + audit loop
    dispatch_plan: str
    audit_result: Dict[str, Any]       # Enhancement 1: last AuditAgent JSON
    audit_iteration: int               # Enhancement 1: loop counter (max 3)

    # Report
    report_html: str


def node_pdf_context(state: AppState) -> AppState:
    rag = PdfRag(persist_dir="chroma_db")
    vectordb = rag.build(state["pdf_path"])
    retriever = rag.retriever(vectordb, k=6)

    query = "Extract KPI definitions, thresholds, SLAs, constraints, dispatch rules, exceptions."
    docs = retriever.invoke(query)
    snippets = "\n\n---\n\n".join(d.page_content for d in docs)

    business_context = run_context_agent(snippets)
    return {"business_context": business_context, "pdf_retriever": retriever}


def node_csv_analysis(state: AppState) -> AppState:
    retriever = state.get("pdf_retriever")
    res = analyze_csv(state["csv_path"], retriever=retriever)

    anomalies_md = "(none detected or insufficient numeric data)"
    if not res.anomalies.empty:
        anomalies_md = res.anomalies.head(12).to_markdown(index=False)

    ops_insights = run_ops_agent(
        summary=res.summary,
        kpis=res.kpis,
        anomalies_md=anomalies_md,
        cross_ref_findings=res.cross_ref_findings,
    )

    return {
        "csv_summary": res.summary,
        "csv_kpis": res.kpis,
        "anomalies_md": anomalies_md,
        "cross_ref_findings": res.cross_ref_findings,
        "ops_insights": ops_insights,
    }


def node_scenario(state: AppState) -> AppState:
    """No-op if no scenario specified; else runs ScenarioAgent."""
    scenario = state.get("scenario")
    if not scenario:
        return {"scenario_analysis": ""}

    result = run_scenario_agent(
        kpis=state.get("csv_kpis", {}),
        scenario=scenario,
    )
    return {"scenario_analysis": result}


# --- Waypoint parsing helpers (extract W1..W5 rows from PDF-retrieved text) ---
WAYPOINT_RE = re.compile(
    r"(W[1-9]\d*)\s+([A-Za-z][A-Za-z\s\-\.,]*)\s+([A-Z]{2})\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)",
    re.MULTILINE
)


def _parse_waypoints_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Extract rows like:
      W1 Newark NJ 40.7357 -74.1724
      W3 New Haven CT 41.3083 -72.9279
    from arbitrary text. Returns sorted list by waypoint number.
    """
    wps: List[Dict[str, Any]] = []
    for m in WAYPOINT_RE.finditer(text):
        wid, city, state, lat, lon = m.groups()
        wps.append(
            {
                "id": wid.strip(),
                "city": city.strip(),
                "state": state.strip(),
                "lat": float(lat),
                "lon": float(lon),
            }
        )

    def wp_key(w: Dict[str, Any]) -> int:
        n = re.sub(r"\D", "", w["id"])
        return int(n) if n else 0

    wps.sort(key=wp_key)
    return wps


def node_weather(state: AppState) -> AppState:
    tz = os.getenv("WEATHER_TZ", "America/New_York")

    rag = PdfRag(persist_dir="chroma_db")
    vectordb = rag.build(state["pdf_path"])
    retriever = rag.retriever(vectordb, k=20)

    wp_query = (
        "Find the section titled 'Route Definition' or 'Waypoints' or 'I-95 Corridor Waypoints'. "
        "Return the waypoint list including W1, W2, W3, W4, W5 and their latitude and longitude."
    )
    docs = retriever.invoke(wp_query)
    wp_text = "\n".join(d.page_content for d in docs)
    print("\n===== WAYPOINT RETRIEVAL (RAW) =====")
    print(wp_text[:1200])
    print("===================================\n")
    waypoints = _parse_waypoints_from_text(wp_text)

    if len(waypoints) < 5:
        print(f"Waypoint extraction failed (found {len(waypoints)}). Falling back to WEATHER_LAT/LON.")
        lat = os.getenv("WEATHER_LAT", "40.7282")
        lon = os.getenv("WEATHER_LON", "-74.0776")
        forecast = get_weather_forecast(lat, lon, tz)
        risk = derive_dispatch_weather_risk(forecast)
        print("\n===== WEATHER_RISK DEBUG (FALLBACK) =====")
        print(forecast)
        print(risk)
        print("=========================================\n")
        return {"weather_risk": risk}

    per_waypoint: List[Dict[str, Any]] = []
    worst: Dict[str, Any] | None = None
    max_score = -1

    for wp in waypoints:
        forecast = get_weather_forecast(str(wp["lat"]), str(wp["lon"]), tz)
        risk = derive_dispatch_weather_risk(forecast)
        enriched = {"waypoint": wp["id"], "city": wp["city"], "state": wp["state"], **risk}
        per_waypoint.append(enriched)

        if enriched.get("risk_score_0_3", -1) > max_score:
            max_score = enriched["risk_score_0_3"]
            worst = enriched

    route_risk: Dict[str, Any] = {
        "route_risk_score_0_3": max_score,
        "worst_waypoint": worst,
        "per_waypoint": per_waypoint,
    }

    if worst:
        route_risk.update(
            {
                "max_precip_mm_day": worst.get("max_precip_mm_day"),
                "max_wind_gust_kmh": worst.get("max_wind_gust_kmh"),
                "min_temp_c": worst.get("min_temp_c"),
                "risk_flags": worst.get("risk_flags"),
                "risk_score_0_3": worst.get("risk_score_0_3"),
            }
        )
    print("\n===== WEATHER_RISK DEBUG =====")
    print(route_risk)
    print("================================\n")
    return {"weather_risk": route_risk}


def node_planner(state: AppState) -> AppState:
    plan = run_planner_agent(
        business_context=state.get("business_context", ""),
        ops_insights=state.get("ops_insights", ""),
        weather_risk=state.get("weather_risk", {}),
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
    audit = state.get("audit_result", {})
    revised = run_planner_revision_agent(
        business_context=state.get("business_context", ""),
        ops_insights=state.get("ops_insights", ""),
        weather_risk=state.get("weather_risk", {}),
        scenario_analysis=state.get("scenario_analysis", ""),
        prior_plan=state.get("dispatch_plan", ""),
        audit_feedback=audit.get("feedback", ""),
        violations=audit.get("violations", []),
    )
    return {"dispatch_plan": revised}


def route_after_audit(state: AppState) -> str:
    """Conditional routing: loop back to planner_revision or proceed to report."""
    MAX_ITERATIONS = 3
    audit = state.get("audit_result", {})
    iteration = state.get("audit_iteration", 0)

    if audit.get("compliant", False) or iteration >= MAX_ITERATIONS:
        return "report"
    return "planner_revision"


def node_report(state: AppState) -> AppState:
    html = run_report_agent(
        business_context=state.get("business_context", ""),
        kpis=state.get("csv_kpis", {}),
        anomaly_highlights=state.get("anomalies_md", "(none)"),
        weather_risk=state.get("weather_risk", {}),
        dispatch_plan=state.get("dispatch_plan", ""),
    )
    return {"report_html": html}


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

    g.add_node("pdf_context", node_pdf_context)
    g.add_node("csv_analysis", node_csv_analysis)
    g.add_node("scenario", node_scenario)
    g.add_node("weather", node_weather)
    g.add_node("planner", node_planner)
    g.add_node("audit", node_audit)
    g.add_node("planner_revision", node_planner_revision)
    g.add_node("report", node_report)
    g.add_node("email", node_email)

    g.set_entry_point("pdf_context")
    g.add_edge("pdf_context", "csv_analysis")
    g.add_edge("csv_analysis", "scenario")
    g.add_edge("scenario", "weather")
    g.add_edge("weather", "planner")
    g.add_edge("planner", "audit")
    g.add_edge("planner_revision", "audit")

    g.add_conditional_edges(
        "audit",
        route_after_audit,
        {
            "report": "report",
            "planner_revision": "planner_revision",
        },
    )

    g.add_edge("report", "email")
    g.add_edge("email", END)

    return g.compile()
