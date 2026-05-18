"""Run the pipeline and save reports to sample_docs/."""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()
import os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
from tracing import init_langsmith_tracing
init_langsmith_tracing()
from graph import build_graph

app = build_graph()

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(ROOT, "data", "SeeWeeS Specialty Dispatch Playbook.pdf")
CSV_PATH = os.path.join(ROOT, "data", "Incoming_shipment_03_06.csv")

# --- Run 1: baseline (no scenario) ---
print("Running baseline pipeline...")
state_baseline = {
    "pdf_path": PDF_PATH,
    "csv_path": CSV_PATH,
}
final_baseline = app.invoke(state_baseline)

# --- Run 2: with demand spike scenario ---
print("Running what-if scenario pipeline...")
state_scenario = {
    "pdf_path": PDF_PATH,
    "csv_path": CSV_PATH,
    "scenario": {
        "type": "demand_spike",
        "magnitude": 0.20,
        "description": "20% increase in Remdesivir demand from Boston-MGH due to outbreak.",
    },
}
final_scenario = app.invoke(state_scenario)

# --- Save both reports ---
out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_docs")
os.makedirs(out_dir, exist_ok=True)

date_str = datetime.date.today().isoformat()

baseline_path = os.path.join(out_dir, f"dispatch_report_baseline_{date_str}.html")
scenario_path = os.path.join(out_dir, f"dispatch_report_demand_spike_{date_str}.html")

with open(baseline_path, "w") as f:
    f.write(final_baseline.get("report_html", ""))
print(f"Saved: {baseline_path}")

with open(scenario_path, "w") as f:
    f.write(final_scenario.get("report_html", ""))
print(f"Saved: {scenario_path}")
