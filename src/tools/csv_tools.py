from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple, List
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest


@dataclass
class CsvAnalysisResult:
    summary: Dict[str, Any]
    kpis: Dict[str, Any]
    anomalies: pd.DataFrame
    cleaned_shape: Tuple[int, int]
    numeric_cols: List[str]
    cross_ref_findings: List[Dict[str, Any]] = field(default_factory=list)


def analyze_csv(csv_path: str, retriever=None) -> CsvAnalysisResult:
    df = pd.read_csv(csv_path)
    original_shape = df.shape

    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(how="all").copy()

    # Try to parse any column that looks like a date
    for c in df.columns:
        if "date" in c.lower() or "time" in c.lower():
            try:
                df[c] = pd.to_datetime(df[c], errors="ignore")
            except Exception:
                pass

    summary = {
        "rows_original": int(original_shape[0]),
        "cols_original": int(original_shape[1]),
        "rows_after_drop_empty": int(df.shape[0]),
        "missingness_top": df.isna().mean().sort_values(ascending=False).head(10).to_dict(),
        "column_dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "columns": list(df.columns),
    }

    kpis: Dict[str, Any] = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    # Pharma dispatch domain KPIs
    kpis["total_shipments"] = int(df.shape[0])
    if "item_name" in df.columns:
        kpis["unique_item_types"] = int(df["item_name"].nunique())
        kpis["top_5_items"] = df["item_name"].value_counts().head(5).to_dict()
    if "unique_item_id" in df.columns:
        missing_mask = df["unique_item_id"].isna() | (df["unique_item_id"].astype(str).str.strip() == "")
        kpis["missing_id_rate_pct"] = round(missing_mask.mean() * 100, 2)
        kpis["missing_id_count"] = int(missing_mask.sum())
    if "dispatch_location" in df.columns:
        kpis["dispatch_locations"] = int(df["dispatch_location"].nunique())
        kpis["items_by_hospital"] = df.groupby("dispatch_location")["item_name"].count().to_dict() if "item_name" in df.columns else {}
    if "item_id" in df.columns:
        kpis["experimental_items_flagged"] = int((df["item_id"].astype(str).str.startswith("9")).sum())

    # PDF cross-reference for items with missing unique_item_id
    cross_ref_findings: List[Dict[str, Any]] = []
    if retriever is not None and "unique_item_id" in df.columns:
        missing_rows = df[missing_mask] if "unique_item_id" in df.columns else pd.DataFrame()
        for _, row in missing_rows.head(8).iterrows():
            item_name = str(row.get("item_name", "unknown"))
            docs = retriever.invoke(f"Item Master Appendix: {item_name}")
            snippet = docs[0].page_content[:400] if docs else "No match found in PDF."
            cross_ref_findings.append({
                "item_id": str(row.get("item_id", "")),
                "item_name": item_name,
                "dispatch_location": str(row.get("dispatch_location", "")),
                "pdf_cross_ref": snippet,
            })

    # Anomalies on numeric cols
    anomalies = pd.DataFrame()
    if len(numeric_cols) >= 2 and df.shape[0] >= 20:
        X = df[numeric_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).values
        model = IsolationForest(
            n_estimators=200,
            contamination=0.03,
            random_state=42,
        )
        preds = model.fit_predict(X)
        scores = model.decision_function(X)

        df_anom = df.copy()
        df_anom["is_anomaly"] = (preds == -1)
        df_anom["anomaly_score"] = scores

        anomalies = df_anom[df_anom["is_anomaly"]].sort_values("anomaly_score").head(25)

    return CsvAnalysisResult(
        summary=summary,
        kpis=kpis,
        anomalies=anomalies,
        cleaned_shape=df.shape,
        numeric_cols=numeric_cols,
        cross_ref_findings=cross_ref_findings,
    )
