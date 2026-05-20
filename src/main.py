from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()  # must be before importing graph/agents
from tracing import init_langsmith_tracing
init_langsmith_tracing()  # must be before importing graph/agents
from graph import build_graph


if __name__ == "__main__":

    app = build_graph()

    state = {
        "pdf_path":       "data/SeeWeeS Specialty Dispatch Playbook.md",
        "csv_path":       "data/Incoming_shipments_14d_multi_corridor.csv",
        "resources_path": "data/Resource_availability_48h.csv",

        # Enhancement 2: What-if Scenario Simulation
        # Uncomment and edit to activate scenario analysis:
        # "scenario": {
        #     "type": "demand_spike",
        #     "magnitude": 0.20,
        #     "description": "20% increase in Remdesivir demand from Boston-MGH due to outbreak.",
        # },
    }

    final = app.invoke(state)

    report_html = final.get("report_html", "")
    print("\n=== REPORT (first 2000 chars) ===\n")
    print(report_html[:2000])
