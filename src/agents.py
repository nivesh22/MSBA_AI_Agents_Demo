from __future__ import annotations
import json
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI
from prompts import (
    PDF_CONTEXT_PROMPT,
    OPS_ANALYSIS_PROMPT,
    PLANNER_PROMPT,
    PLANNER_REVISION_PROMPT,
    REPORT_PROMPT,
    SCENARIO_PROMPT,
    AUDIT_PROMPT,
)

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.2,
    tags=["msba-demo", "multi-agent"],
    metadata={"repo": "MSBA_AI_Agents_Demo"}
)


def run_context_agent(snippets: str) -> str:
    return llm.invoke(PDF_CONTEXT_PROMPT.format_messages(snippets=snippets)).content


def run_ops_agent(
    summary: Dict[str, Any],
    kpis: Dict[str, Any],
    multi_corridor_kpis: Dict[str, Any],
    resource_constraints: Dict[str, Any],
    anomalies_md: str,
    cross_ref_findings: List[Dict[str, Any]] = None,
) -> str:
    cross_ref_findings = cross_ref_findings or []
    return llm.invoke(OPS_ANALYSIS_PROMPT.format_messages(
        summary=summary,
        kpis=kpis,
        multi_corridor_kpis=multi_corridor_kpis,
        resource_constraints=resource_constraints,
        anomalies_md=anomalies_md,
        cross_ref_findings=cross_ref_findings,
    )).content


def run_planner_agent(
    business_context: str,
    ops_insights: str,
    weather_risk: Dict[str, Any],
    weather_risk_by_corridor: Dict[str, Any],
    multi_corridor_kpis: Dict[str, Any],
    resource_constraints: Dict[str, Any],
    scenario_analysis: str = "",
) -> str:
    return llm.invoke(PLANNER_PROMPT.format_messages(
        business_context=business_context,
        ops_insights=ops_insights,
        weather_risk=weather_risk,
        weather_risk_by_corridor=weather_risk_by_corridor,
        multi_corridor_kpis=multi_corridor_kpis,
        resource_constraints=resource_constraints,
        scenario_analysis=scenario_analysis,
    )).content


def run_scenario_agent(
    kpis: Dict[str, Any],
    scenario: Dict[str, Any],
) -> str:
    return llm.invoke(SCENARIO_PROMPT.format_messages(
        kpis=kpis,
        scenario_type=scenario.get("type", "unspecified"),
        scenario_magnitude=scenario.get("magnitude", "unspecified"),
        scenario_description=scenario.get("description", ""),
    )).content


def run_audit_agent(
    business_context: str,
    dispatch_plan: str,
) -> Dict[str, Any]:
    raw = llm.invoke(AUDIT_PROMPT.format_messages(
        business_context=business_context,
        dispatch_plan=dispatch_plan,
    )).content

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        result = {
            "compliant": False,
            "violations": ["AuditAgent returned malformed JSON; treating as non-compliant."],
            "feedback": raw[:500],
        }
    return result


def run_planner_revision_agent(
    business_context: str,
    ops_insights: str,
    weather_risk: Dict[str, Any],
    weather_risk_by_corridor: Dict[str, Any],
    multi_corridor_kpis: Dict[str, Any],
    resource_constraints: Dict[str, Any],
    scenario_analysis: str,
    prior_plan: str,
    audit_feedback: str,
    violations: List[str],
) -> str:
    violations_str = "\n".join(f"- {v}" for v in violations)
    return llm.invoke(PLANNER_REVISION_PROMPT.format_messages(
        business_context=business_context,
        ops_insights=ops_insights,
        weather_risk=weather_risk,
        weather_risk_by_corridor=weather_risk_by_corridor,
        multi_corridor_kpis=multi_corridor_kpis,
        resource_constraints=resource_constraints,
        scenario_analysis=scenario_analysis,
        prior_plan=prior_plan,
        audit_feedback=audit_feedback,
        violations=violations_str,
    )).content


def run_report_agent(
    business_context: str,
    kpis: Dict[str, Any],
    multi_corridor_kpis: Dict[str, Any],
    anomaly_highlights: str,
    weather_risk: Dict[str, Any],
    weather_risk_by_corridor: Dict[str, Any],
    resource_constraints: Dict[str, Any],
    dispatch_plan: str,
) -> str:
    return llm.invoke(REPORT_PROMPT.format_messages(
        business_context=business_context,
        kpis=kpis,
        multi_corridor_kpis=multi_corridor_kpis,
        anomaly_highlights=anomaly_highlights,
        weather_risk=weather_risk,
        weather_risk_by_corridor=weather_risk_by_corridor,
        resource_constraints=resource_constraints,
        dispatch_plan=dispatch_plan,
    )).content
