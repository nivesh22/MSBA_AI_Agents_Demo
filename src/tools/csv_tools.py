from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np

# --- Canonical item master (Appendix A, SeeWeeS Playbook v0.2) ---
CANONICAL_ITEMS: Dict[int, Dict[str, str]] = {
    10021: {"canonical_item_id": "RMD-MULTI", "canonical_item_name": "Remdesivir", "medicine_type": "Antiviral",          "temp_control": "Cold (2-8C)",           "product_class": "Antiviral"},
    10022: {"canonical_item_id": "INS-LIS",   "canonical_item_name": "Insulin Lispro",               "medicine_type": "Hormone",              "temp_control": "Cold (2-8C)",           "product_class": "Endocrine"},
    10023: {"canonical_item_id": "INS-ASP",   "canonical_item_name": "Insulin Aspart",               "medicine_type": "Hormone",              "temp_control": "Cold (2-8C)",           "product_class": "Endocrine"},
    10035: {"canonical_item_id": "PMB-KEY",   "canonical_item_name": "Pembrolizumab",                "medicine_type": "Monoclonal Antibody",  "temp_control": "Cold (2-8C)",           "product_class": "Oncology Biologic"},
    10040: {"canonical_item_id": "EPI-AI",    "canonical_item_name": "Epinephrine Auto-Injector",    "medicine_type": "Emergency Drug",       "temp_control": "Room Temp (20-25C)",    "product_class": "Emergency"},
    10050: {"canonical_item_id": "HEP-SOD",   "canonical_item_name": "Heparin Sodium",               "medicine_type": "Anticoagulant",        "temp_control": "Room Temp (20-25C)",    "product_class": "Anticoagulant"},
    10060: {"canonical_item_id": "MOR-SUL",   "canonical_item_name": "Morphine Sulfate",             "medicine_type": "Opioid Analgesic",     "temp_control": "Controlled Storage",    "product_class": "Controlled"},
    10070: {"canonical_item_id": "ALB-INH",   "canonical_item_name": "Albuterol Inhaler",            "medicine_type": "Bronchodilator",       "temp_control": "Room Temp (20-25C)",    "product_class": "Respiratory"},
    10071: {"canonical_item_id": "LEV-INH",   "canonical_item_name": "Levalbuterol Inhaler",         "medicine_type": "Bronchodilator",       "temp_control": "Room Temp (20-25C)",    "product_class": "Respiratory"},
    99999: {"canonical_item_id": "EXP-ONC-CT","canonical_item_name": "Experimental Oncology Drug",  "medicine_type": "Clinical Trial Drug",  "temp_control": "Strict Cold Chain (-20C)","product_class": "Clinical Trial"},
}

# Legacy item_id → canonical item_id (Appendix A.3)
LEGACY_IDS: Dict[int, int] = {
    10020: 10021,
    20021: 10021,
    1070:  10070,
}

# item_name alias → canonical item_id (Appendix A.2, lowercased)
ALIAS_NAMES: Dict[str, int] = {
    "remdesivir 100 mg":         10021,
    "remdesivir 200 mg":         10021,
    "pembrolizumab (keytruda)":  10035,
    "epipen auto injector":      10040,
    "heparin na":                10050,
    "morphine sulphate":         10060,
    "albuterol inhaler 90mcg":   10070,
}

# Canonical item_name values per item_id (exact canonical names only — lowercased).
# DQ-03 fires when item_id is valid but name is NOT in this set.
# Aliases from Appendix A.2 are intentionally excluded: they confirm the mismatch, not clear it.
ACCEPTED_NAMES: Dict[int, set] = {
    10021: {"remdesivir 100mg", "remdesivir 200mg"},  # two strength variants share item_id 10021
    10022: {"insulin lispro"},
    10023: {"insulin aspart"},
    10035: {"pembrolizumab"},
    10040: {"epinephrine auto-injector"},
    10050: {"heparin sodium"},
    10060: {"morphine sulfate"},
    10070: {"albuterol inhaler"},
    10071: {"levalbuterol inhaler"},
    99999: {"experimental oncology drug", "experimental oncology drug (clinical trial)"},
}

COLD_CHAIN_CLASSES = {"Cold (2-8C)", "Strict Cold Chain (-20C)"}
CORRIDOR_SLA      = {"C1_I95_NJ_BOS": "Tier 1", "C2_NJ_PHL": "Tier 2"}
SLA_PENALTY       = {"Tier 1": 100, "Tier 2": 40}
COLD_CHAIN_PENALTY = 80
TRUCK_CAPACITY     = 10
PACKING_BUFFER     = 1.10


def _resolve_item(item_id_raw, item_name_raw) -> Tuple[Optional[int], str, str]:
    """Map raw item_id / item_name to a canonical item_id via D3→D5→D4 precedence."""
    try:
        item_id = int(float(str(item_id_raw).strip()))
    except (ValueError, TypeError):
        return None, "UNRESOLVED_CONFLICT", "invalid_item_id_format"

    name = str(item_name_raw).strip().lower()

    if item_id in CANONICAL_ITEMS:
        return item_id, "EXACT_MATCH", "exact_match"

    if item_id in LEGACY_IDS:
        return LEGACY_IDS[item_id], "LEGACY_ID_MAP", "legacy_id_map"

    if name in ALIAS_NAMES:
        return ALIAS_NAMES[name], "ALIAS_MATCH", "alias_match"

    return None, "UNRESOLVED_CONFLICT", "excluded_unresolved"


def _trucks_needed(valid_rows: pd.DataFrame) -> Dict[str, int]:
    """Compute standard and temp-controlled trucks required for a set of valid dispatch rows."""
    total = len(valid_rows)
    if total == 0:
        return {"truck_standard": 0, "truck_temp_controlled": 0, "driver": 0}

    cold_mask = valid_rows["temp_control"].isin(COLD_CHAIN_CLASSES) if "temp_control" in valid_rows.columns else pd.Series(False, index=valid_rows.index)
    cold = int(cold_mask.sum())
    std  = total - cold

    t_temp = math.ceil(cold * PACKING_BUFFER / TRUCK_CAPACITY) if cold > 0 else 0
    t_std  = math.ceil(std  * PACKING_BUFFER / TRUCK_CAPACITY) if std  > 0 else 0
    return {"truck_standard": t_std, "truck_temp_controlled": t_temp, "driver": t_std + t_temp}


def load_resource_constraints(resources_path: str) -> Dict[str, Any]:
    df = pd.read_csv(resources_path)
    out: Dict[str, Any] = {}
    for _, row in df.iterrows():
        day   = str(row["day"])
        rtype = str(row["resource_type"])
        if day not in out:
            out[day] = {}
        out[day][rtype] = int(row["available_count"])
    return out


@dataclass
class CsvAnalysisResult:
    summary: Dict[str, Any]
    kpis: Dict[str, Any]
    multi_corridor_kpis: Dict[str, Any]
    resource_constraints: Dict[str, Any]
    anomalies: pd.DataFrame
    cleaned_shape: Tuple[int, int]
    numeric_cols: List[str]
    cross_ref_findings: List[Dict[str, Any]] = field(default_factory=list)


def analyze_csv(csv_path: str, retriever=None, resources_path: str = None) -> CsvAnalysisResult:
    df = pd.read_csv(csv_path)
    original_shape = df.shape
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(how="all").copy()

    # --- Item master reconciliation ---
    resolved_ids, confidences, reason_codes, temp_controls, dq03_flags = [], [], [], [], []
    for _, row in df.iterrows():
        rid, conf, reason = _resolve_item(row.get("item_id"), row.get("item_name", ""))
        resolved_ids.append(rid)
        confidences.append(conf)
        reason_codes.append(reason)
        temp_controls.append(CANONICAL_ITEMS[rid]["temp_control"] if rid and rid in CANONICAL_ITEMS else None)
        # DQ-03: valid item_id but item_name not in accepted set
        name_lower = str(row.get("item_name", "")).strip().lower()
        is_dq03 = (rid is not None and conf == "EXACT_MATCH"
                   and rid in ACCEPTED_NAMES and name_lower not in ACCEPTED_NAMES[rid])
        dq03_flags.append(is_dq03)

    df["resolved_item_id"]    = resolved_ids
    df["reconcile_confidence"] = confidences
    df["reason_code"]          = reason_codes
    df["temp_control"]         = temp_controls
    df["dq03_name_mismatch"]   = dq03_flags

    # DQ flags
    missing_uid_mask  = df["unique_item_id"].isna() | (df["unique_item_id"].astype(str).str.strip() == "")
    invalid_item_mask = df["resolved_item_id"].isna()
    valid_uid_series  = df.loc[~missing_uid_mask, "unique_item_id"].astype(str).str.strip()
    dup_uids          = set(valid_uid_series[valid_uid_series.duplicated()])
    dup_uid_mask      = (~missing_uid_mask) & df["unique_item_id"].astype(str).str.strip().isin(dup_uids)

    excluded_mask = missing_uid_mask | invalid_item_mask
    valid_df      = df[~excluded_mask].copy()

    # Cross-ref findings: excluded + DQ-flagged rows
    dq_flag_mask = excluded_mask | dup_uid_mask | df["dq03_name_mismatch"] | df["reconcile_confidence"].isin({"LEGACY_ID_MAP", "ALIAS_MATCH"})
    cross_ref_findings: List[Dict[str, Any]] = []
    for _, row in df[dq_flag_mask].head(20).iterrows():
        cross_ref_findings.append({
            "shipment_date":        str(row.get("shipment_date", "")),
            "planning_day":         str(row.get("planning_day", "")),
            "corridor_id":          str(row.get("corridor_id", "")),
            "item_id":              str(row.get("item_id", "")),
            "item_name":            str(row.get("item_name", "")),
            "unique_item_id":       str(row.get("unique_item_id", "")),
            "dispatch_location":    str(row.get("dispatch_location", "")),
            "reconcile_confidence": str(row.get("reconcile_confidence", "")),
            "reason_code":          str(row.get("reason_code", "")),
            "dq03_name_mismatch":   bool(row.get("dq03_name_mismatch", False)),
        })

    # --- Split into planning window vs history ---
    planning_df    = df[df["is_planning_window"] == 1].copy()
    planning_valid = valid_df[valid_df["is_planning_window"] == 1].copy()
    history_valid  = valid_df[valid_df["is_planning_window"] == 0].copy()

    # --- Global KPIs (backward-compatible) ---
    kpis: Dict[str, Any] = {
        "total_shipments":           int(df.shape[0]),
        "planning_window_shipments": int(planning_df.shape[0]),
        "planning_window_valid":     int(planning_valid.shape[0]),
        "planning_window_excluded":  int(planning_df.shape[0]) - int(planning_valid.shape[0]),
        "missing_id_count":          int(missing_uid_mask.sum()),
        "missing_id_rate_pct":       round(missing_uid_mask.mean() * 100, 2),
        "invalid_item_count":        int(invalid_item_mask.sum()),
        "duplicate_uid_count":       int(dup_uid_mask.sum()),
        "experimental_items_flagged":int((df["item_id"].astype(str) == "99999").sum()),
    }
    if "item_name" in df.columns:
        kpis["unique_item_types"] = int(df["item_name"].nunique())
        kpis["top_5_items"]       = df["item_name"].value_counts().head(5).to_dict()
    if "dispatch_location" in df.columns and "item_name" in df.columns:
        kpis["items_by_hospital"] = df.groupby("dispatch_location")["item_name"].count().to_dict()

    # --- Multi-corridor KPIs ---
    corridors = sorted(df["corridor_id"].dropna().unique().tolist()) if "corridor_id" in df.columns else []
    multi_corridor_kpis: Dict[str, Any] = {"corridors": {}, "resource_allocation": {}}

    for corridor in corridors:
        c_plan_valid = planning_valid[planning_valid["corridor_id"] == corridor]
        c_hist_valid = history_valid[history_valid["corridor_id"] == corridor]
        sla_tier     = CORRIDOR_SLA.get(corridor, "Tier 2")

        per_day: Dict[str, Any] = {}
        for day_label in ["Day0", "Day1"]:
            day_valid   = c_plan_valid[c_plan_valid["planning_day"] == day_label]
            day_all     = planning_df[(planning_df["corridor_id"] == corridor) & (planning_df["planning_day"] == day_label)]
            trucks      = _trucks_needed(day_valid)
            cold_count  = int(day_valid["temp_control"].isin(COLD_CHAIN_CLASSES).sum()) if "temp_control" in day_valid.columns else 0

            per_day[day_label] = {
                "total_valid":           int(len(day_valid)),
                "excluded":              int(len(day_all)) - int(len(day_valid)),
                "temp_controlled_units": cold_count,
                "sla_tier":              sla_tier,
                "trucks_needed":         trucks,
                "top_items":             day_valid["item_name"].value_counts().head(5).to_dict() if "item_name" in day_valid.columns else {},
            }

        hist_dates = int(c_hist_valid["shipment_date"].nunique()) if "shipment_date" in c_hist_valid.columns and len(c_hist_valid) > 0 else 1
        hist_avg   = round(len(c_hist_valid) / max(hist_dates, 1), 1)

        multi_corridor_kpis["corridors"][corridor] = {
            "sla_tier":                   sla_tier,
            "planning_window":            per_day,
            "historical_avg_units_per_day": hist_avg,
            "historical_total_valid":     int(len(c_hist_valid)),
        }

    # --- Resource allocation ---
    resource_constraints: Dict[str, Any] = {}
    if resources_path:
        try:
            resource_constraints = load_resource_constraints(resources_path)
        except Exception as e:
            resource_constraints = {"error": str(e)}

    if resource_constraints and corridors:
        alloc: Dict[str, Any] = {}
        for day_label in ["Day0", "Day1"]:
            avail  = resource_constraints.get(day_label, {})
            needed: Dict[str, Dict[str, int]] = {}
            for corridor in corridors:
                c_day = planning_valid[(planning_valid["corridor_id"] == corridor) & (planning_valid["planning_day"] == day_label)]
                needed[corridor] = _trucks_needed(c_day)

            total_std    = sum(v.get("truck_standard", 0) for v in needed.values())
            total_temp   = sum(v.get("truck_temp_controlled", 0) for v in needed.values())
            total_driver = sum(v.get("driver", 0) for v in needed.values())

            shortfall_std    = max(0, total_std    - avail.get("truck_standard", 999))
            shortfall_temp   = max(0, total_temp   - avail.get("truck_temp_controlled", 999))
            shortfall_driver = max(0, total_driver - avail.get("driver", 999))

            # Penalty estimate from cold-chain shortfall (worst-case: Tier 1 cold units affected first)
            penalty_by_corridor: Dict[str, int] = {}
            units_unserved = shortfall_temp * max(1, int(TRUCK_CAPACITY / PACKING_BUFFER))
            for corridor in sorted(corridors, key=lambda c: -SLA_PENALTY.get(CORRIDOR_SLA.get(c, "Tier 2"), 0)):
                if units_unserved <= 0:
                    break
                c_day  = planning_valid[(planning_valid["corridor_id"] == corridor) & (planning_valid["planning_day"] == day_label)]
                cold   = int(c_day["temp_control"].isin(COLD_CHAIN_CLASSES).sum()) if "temp_control" in c_day.columns else 0
                hit    = min(cold, units_unserved)
                if hit > 0:
                    sla    = CORRIDOR_SLA.get(corridor, "Tier 2")
                    penalty_by_corridor[corridor] = hit * (SLA_PENALTY[sla] + COLD_CHAIN_PENALTY)
                    units_unserved -= hit

            alloc[day_label] = {
                "available":              avail,
                "needed_by_corridor":     needed,
                "total_needed":           {"truck_standard": total_std, "truck_temp_controlled": total_temp, "driver": total_driver},
                "shortfall":              {"truck_standard": shortfall_std, "truck_temp_controlled": shortfall_temp, "driver": shortfall_driver},
                "estimated_penalty_by_corridor": penalty_by_corridor,
                "total_estimated_penalty":       sum(penalty_by_corridor.values()),
            }
        multi_corridor_kpis["resource_allocation"] = alloc

    summary = {
        "rows_original":          int(original_shape[0]),
        "planning_window_rows":   int(planning_df.shape[0]),
        "history_rows":           int(len(history_valid)),
        "corridors":              corridors,
        "column_dtypes":          {c: str(t) for c, t in df.dtypes.items()},
        "columns":                list(df.columns),
        "dq_summary": {
            "dq01_missing_uid":      int(missing_uid_mask.sum()),
            "dq02_invalid_item_id":  int(invalid_item_mask.sum()),
            "dq03_name_mismatch":    int(df["dq03_name_mismatch"].sum()),
            "dq04_duplicate_uid":    int(dup_uid_mask.sum()),
            "legacy_id_resolved":    int((df["reconcile_confidence"] == "LEGACY_ID_MAP").sum()),
            "alias_resolved":        int((df["reconcile_confidence"] == "ALIAS_MATCH").sum()),
            "total_excluded":        int(excluded_mask.sum()),
        },
    }

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    return CsvAnalysisResult(
        summary=summary,
        kpis=kpis,
        multi_corridor_kpis=multi_corridor_kpis,
        resource_constraints=resource_constraints,
        anomalies=pd.DataFrame(),
        cleaned_shape=df.shape,
        numeric_cols=numeric_cols,
        cross_ref_findings=cross_ref_findings,
    )
