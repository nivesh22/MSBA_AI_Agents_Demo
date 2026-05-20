"""Generate architecture and agent flow diagrams for the MSBA Multi-Agent System."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe
import numpy as np

# ── colour palette ──────────────────────────────────────────────────────────
BLUE_DARK   = "#1B3A6B"
BLUE_MID    = "#2E6CB8"
BLUE_LIGHT  = "#D0E4F7"
GREEN_DARK  = "#1A5C3A"
GREEN_MID   = "#2E9A5A"
GREEN_LIGHT = "#C8EDD8"
ORANGE_DARK = "#7A3800"
ORANGE_MID  = "#D46A00"
ORANGE_LIGHT= "#FFE8CC"
PURPLE_DARK = "#4A1870"
PURPLE_MID  = "#8B3FBE"
PURPLE_LIGHT= "#EAD4F7"
RED_DARK    = "#7A1818"
RED_MID     = "#C83232"
RED_LIGHT   = "#F7D0D0"
GREY_DARK   = "#333333"
GREY_MID    = "#888888"
GREY_LIGHT  = "#F2F2F2"
WHITE       = "#FFFFFF"
BLACK       = "#111111"


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 1 — Full System Architecture (graph topology + audit loop)
# ═══════════════════════════════════════════════════════════════════════════
def draw_architecture():
    fig, ax = plt.subplots(figsize=(20, 13))
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 13)
    ax.axis("off")
    fig.patch.set_facecolor(GREY_LIGHT)
    ax.set_facecolor(GREY_LIGHT)

    # ── helper: rounded box ──────────────────────────────────────────────
    def node(ax, cx, cy, w, h, label, sublabel, fill, border, text_col=WHITE,
             fontsize=9.5, bold=True):
        box = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                             boxstyle="round,pad=0.12",
                             facecolor=fill, edgecolor=border, linewidth=2.2,
                             zorder=3)
        ax.add_patch(box)
        weight = "bold" if bold else "normal"
        ax.text(cx, cy + 0.07, label, ha="center", va="center",
                fontsize=fontsize, fontweight=weight, color=text_col, zorder=4)
        if sublabel:
            ax.text(cx, cy - 0.38, sublabel, ha="center", va="center",
                    fontsize=7.5, color=text_col, alpha=0.88, zorder=4,
                    style="italic")

    def arrow(ax, x0, y0, x1, y1, color=GREY_DARK, lw=1.8,
              arrowsize=14, style="->", label="", label_col=GREY_DARK):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle=style,
                                   color=color, lw=lw,
                                   mutation_scale=arrowsize),
                    zorder=2)
        if label:
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            ax.text(mx + 0.05, my + 0.15, label, fontsize=7.5,
                    color=label_col, ha="center", zorder=5)

    # ── title ────────────────────────────────────────────────────────────
    ax.text(10, 12.5, "SeeWeeS Ops — Multi-Agent System Architecture",
            ha="center", va="center", fontsize=16, fontweight="bold",
            color=BLUE_DARK, zorder=5)
    ax.text(10, 12.05, "LangGraph pipeline with Self-Correction Audit Loop · What-if Scenario Simulation · Deep-Dive Trend Analysis",
            ha="center", va="center", fontsize=9, color=GREY_MID, zorder=5)

    # ── main pipeline nodes (left → right, y = 7.5) ──────────────────────
    NW, NH = 2.8, 1.05   # node width / height

    # Row 1: linear pipeline
    Y1 = 8.8
    nodes_row1 = [
        (2.0,  Y1, "pdf_context",  "ContextAgent",    BLUE_MID,    BLUE_DARK),
        (5.2,  Y1, "csv_analysis", "OpsDataAgent",    GREEN_MID,   GREEN_DARK),
        (8.4,  Y1, "scenario",     "ScenarioAgent",   ORANGE_MID,  ORANGE_DARK),
        (11.6, Y1, "weather",      "WeatherAgent",    BLUE_MID,    BLUE_DARK),
        (14.8, Y1, "planner",      "PlannerAgent",    PURPLE_MID,  PURPLE_DARK),
    ]

    for cx, cy, lbl, sub, fill, border in nodes_row1:
        node(ax, cx, cy, NW, NH, lbl, sub, fill, border)

    # Row 2: audit cycle
    Y2 = 5.8
    node(ax, 14.8, Y2, NW, NH, "audit",            "AuditAgent",          RED_MID,    RED_DARK)
    node(ax, 10.5, Y2, NW, NH, "planner_revision", "PlannerRevisionAgent", PURPLE_MID, PURPLE_DARK)

    # Row 3: output
    Y3 = 3.0
    node(ax, 14.8, Y3, NW, NH, "report", "ReportAgent", GREEN_MID,  GREEN_DARK)
    node(ax, 17.8, Y3, 2.2, NH, "email",  "EmailAgent",  GREY_MID,   GREY_DARK)

    # START / END bubbles
    def bubble(ax, cx, cy, txt, col):
        circ = plt.Circle((cx, cy), 0.45, facecolor=col, edgecolor=BLACK,
                           linewidth=1.8, zorder=3)
        ax.add_patch(circ)
        ax.text(cx, cy, txt, ha="center", va="center", fontsize=8,
                fontweight="bold", color=WHITE, zorder=4)

    bubble(ax, 0.5,  Y1, "START", GREY_DARK)
    bubble(ax, 19.5, Y3, "END",   BLACK)

    # ── Row 1 arrows (horizontal) ────────────────────────────────────────
    for i in range(len(nodes_row1) - 1):
        x0 = nodes_row1[i][0]   + NW/2
        x1 = nodes_row1[i+1][0] - NW/2
        arrow(ax, x0, Y1, x1, Y1, GREY_DARK, lw=2)

    arrow(ax, 0.95, Y1, 2.0 - NW/2, Y1, GREY_DARK, lw=2)  # START → pdf_context

    # planner → audit (down)
    arrow(ax, 14.8, Y1 - NH/2, 14.8, Y2 + NH/2, RED_DARK, lw=2.2)

    # audit → report (down)
    arrow(ax, 14.8, Y2 - NH/2, 14.8, Y3 + NH/2, GREEN_DARK, lw=2.2,
          label="compliant OR\niter ≥ 3", label_col=GREEN_DARK)

    # audit → planner_revision (left)
    arrow(ax, 14.8 - NW/2, Y2, 10.5 + NW/2, Y2, RED_DARK, lw=2.2,
          label="violations\nfound", label_col=RED_DARK)

    # planner_revision → audit (up-right curve — simulate with two segments)
    arrow(ax, 10.5, Y2 + NH/2, 14.8 - NW/2, Y2 + NH/2 - 0.05,
          PURPLE_DARK, lw=2, style="-")
    arrow(ax, 14.8 - NW/2, Y2 + NH/2 - 0.05, 14.8 - NW/2 + 0.01, Y2 + NH/2,
          PURPLE_DARK, lw=2)

    # report → email
    arrow(ax, 14.8 + NW/2, Y3, 17.8 - 1.1, Y3, GREEN_DARK, lw=2)
    # email → END
    arrow(ax, 17.8 + 1.1, Y3, 19.05, Y3, GREY_DARK, lw=2)

    # ── Enhancement labels (coloured badges) ─────────────────────────────
    def badge(ax, cx, cy, txt, fill, border):
        bp = FancyBboxPatch((cx - 1.1, cy - 0.22), 2.2, 0.44,
                            boxstyle="round,pad=0.07",
                            facecolor=fill, edgecolor=border, linewidth=1.5,
                            zorder=5, alpha=0.92)
        ax.add_patch(bp)
        ax.text(cx, cy, txt, ha="center", va="center", fontsize=7.8,
                fontweight="bold", color=border, zorder=6)

    badge(ax, 5.2,  Y1 - 1.05, "Enhancement 3 · Deep-Dive KPIs",  GREEN_LIGHT,  GREEN_DARK)
    badge(ax, 8.4,  Y1 - 1.05, "Enhancement 2 · Scenario Sim",    ORANGE_LIGHT, ORANGE_DARK)
    badge(ax, 12.65, Y2 + 0.0, "Enhancement 1 · Audit Loop",       RED_LIGHT,    RED_DARK)

    # ── Legend ───────────────────────────────────────────────────────────
    legend_x, legend_y = 0.5, 5.5
    legend_items = [
        (BLUE_MID,   BLUE_DARK,   "PDF / Weather agents"),
        (GREEN_MID,  GREEN_DARK,  "Data analysis / Report agents"),
        (ORANGE_MID, ORANGE_DARK, "Scenario agent (Enhancement 2)"),
        (PURPLE_MID, PURPLE_DARK, "Planner agents"),
        (RED_MID,    RED_DARK,    "Audit agent (Enhancement 1)"),
        (GREY_MID,   GREY_DARK,   "Email / System nodes"),
    ]
    ax.text(legend_x + 1.0, legend_y + 0.5, "Legend", fontsize=9,
            fontweight="bold", color=GREY_DARK)
    for i, (fill, border, lbl) in enumerate(legend_items):
        rx, ry = legend_x, legend_y - i * 0.48
        rect = FancyBboxPatch((rx, ry - 0.16), 0.55, 0.32,
                              boxstyle="round,pad=0.05",
                              facecolor=fill, edgecolor=border, linewidth=1.5,
                              zorder=4)
        ax.add_patch(rect)
        ax.text(rx + 0.7, ry, lbl, va="center", fontsize=8, color=GREY_DARK)

    # ── Audit loop annotation box ─────────────────────────────────────────
    loop_rect = FancyBboxPatch((9.0, 4.9), 7.3, 4.5,
                               boxstyle="round,pad=0.15",
                               facecolor="none", edgecolor=RED_MID,
                               linewidth=2, linestyle="--", zorder=1, alpha=0.7)
    ax.add_patch(loop_rect)
    ax.text(12.65, 9.55, "Self-Correction Loop  (max 3 iterations)",
            ha="center", va="center", fontsize=8.5, color=RED_DARK,
            fontweight="bold", zorder=5)

    # ── State flow annotation ─────────────────────────────────────────────
    ax.text(10, 1.9,
            "State flows through AppState TypedDict  ·  "
            "Hardcoded corridor waypoints (no RAG)  ·  "
            "Item master hardcoded (DQ-01..04)  ·  "
            "audit_iteration bounded at 3",
            ha="center", va="center", fontsize=8.5, color=GREY_MID,
            style="italic")

    plt.tight_layout()
    out = "architecture.png"
    plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=GREY_LIGHT)
    plt.close()
    print(f"Saved: {out}")


# ═══════════════════════════════════════════════════════════════════════════
# DIAGRAM 2 — Agent Data Flow (what each agent receives and emits)
# ═══════════════════════════════════════════════════════════════════════════
def draw_agent_flow():
    fig, ax = plt.subplots(figsize=(22, 14))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 14)
    ax.axis("off")
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    # ── title ────────────────────────────────────────────────────────────
    ax.text(11, 13.4, "SeeWeeS Ops — Agent Data Flow",
            ha="center", va="center", fontsize=16, fontweight="bold",
            color=BLUE_DARK)
    ax.text(11, 12.95,
            "Inputs (left side) · Agent (centre box) · Outputs (right side)",
            ha="center", va="center", fontsize=9, color=GREY_MID)

    AGENTS = [
        # (y_centre, name, role_colour, border_colour, inputs[], outputs[])
        (11.8, "ContextAgent\n(pdf_context)",    BLUE_MID,    BLUE_DARK,
         ["Markdown playbook (direct read)", "OR: PDF path → ChromaDB RAG"],
         ["business_context (text)"]),

        (9.5,  "OpsDataAgent\n(csv_analysis)",   GREEN_MID,   GREEN_DARK,
         ["csv_path (14-day multi-corridor)", "resources_path (trucks/drivers)",
          "Item master tables (hardcoded)"],
         ["csv_kpis", "multi_corridor_kpis",
          "resource_constraints", "cross_ref_findings (DQ-01..04)",
          "ops_insights (text)"]),

        (7.0,  "ScenarioAgent\n(scenario)",       ORANGE_MID,  ORANGE_DARK,
         ["csv_kpis", "scenario dict\n(type / magnitude / description)"],
         ["scenario_analysis (text)", "(empty if no scenario)"]),

        (4.8,  "WeatherAgent\n(weather)",         BLUE_MID,    BLUE_DARK,
         ["CORRIDOR_WAYPOINTS (C1: 5 pts, C2: 4 pts)",
          "Open-Meteo API — 2-day forecast per waypoint"],
         ["weather_risk (global summary)",
          "weather_risk_by_corridor\n(Day0/Day1/48h per corridor)"]),

        (2.7,  "PlannerAgent\n(planner)",         PURPLE_MID,  PURPLE_DARK,
         ["business_context", "ops_insights",
          "weather_risk_by_corridor", "multi_corridor_kpis",
          "resource_constraints", "scenario_analysis"],
         ["dispatch_plan (text)"]),
    ]

    AGENTS2 = [
        (11.8, "AuditAgent\n(audit)",             RED_MID,     RED_DARK,
         ["business_context", "dispatch_plan"],
         ['{"compliant": bool,', ' "violations": [...],',
          ' "feedback": str}', "audit_iteration++"]),

        (9.3,  "PlannerRevisionAgent\n(planner_revision)", PURPLE_MID, PURPLE_DARK,
         ["business_context", "ops_insights",
          "weather_risk_by_corridor", "multi_corridor_kpis",
          "resource_constraints", "prior dispatch_plan",
          "audit violations + feedback"],
         ["revised dispatch_plan"]),

        (6.9,  "ReportAgent\n(report)",           GREEN_MID,   GREEN_DARK,
         ["business_context", "csv_kpis", "multi_corridor_kpis",
          "weather_risk_by_corridor", "resource_constraints",
          "dispatch_plan"],
         ["report_html (8-section HTML)"]),

        (4.5,  "EmailAgent\n(email)",             GREY_MID,    GREY_DARK,
         ["report_html", "SMTP env vars",
          "REPORT_EMAIL_TO"],
         ["(sends email or skips if\n REPORT_EMAIL_TO unset)"]),
    ]

    def agent_row(ax, y, name, fill, border, inputs, outputs, col_offset=0):
        CX = 5.5 + col_offset
        AW, AH = 3.4, 1.3

        # Agent box
        box = FancyBboxPatch((CX - AW/2, y - AH/2), AW, AH,
                             boxstyle="round,pad=0.14",
                             facecolor=fill, edgecolor=border,
                             linewidth=2.5, zorder=3)
        ax.add_patch(box)
        ax.text(CX, y, name, ha="center", va="center",
                fontsize=9, fontweight="bold", color=WHITE, zorder=4,
                linespacing=1.4)

        # Inputs (left)
        IX = CX - AW/2 - 0.15
        for k, inp in enumerate(inputs):
            iy = y + (len(inputs) - 1) * 0.28 / 2 - k * 0.28
            ax.annotate("", xy=(IX, iy), xytext=(IX - 2.0, iy),
                        arrowprops=dict(arrowstyle="->", color=border,
                                        lw=1.4, mutation_scale=11), zorder=2)
            ax.text(IX - 2.15, iy, inp, ha="right", va="center",
                    fontsize=7.8, color=GREY_DARK)

        # Outputs (right)
        OX = CX + AW/2 + 0.15
        for k, out in enumerate(outputs):
            oy = y + (len(outputs) - 1) * 0.28 / 2 - k * 0.28
            ax.annotate("", xy=(OX + 2.0, oy), xytext=(OX, oy),
                        arrowprops=dict(arrowstyle="->", color=border,
                                        lw=1.4, mutation_scale=11), zorder=2)
            ax.text(OX + 2.15, oy, out, ha="left", va="center",
                    fontsize=7.8, color=GREY_DARK)

    # Left column (pipeline agents)
    for y, name, fill, border, inputs, outputs in AGENTS:
        agent_row(ax, y, name, fill, border, inputs, outputs, col_offset=0)

    # Right column (audit + output agents)
    for y, name, fill, border, inputs, outputs in AGENTS2:
        agent_row(ax, y, name, fill, border, inputs, outputs, col_offset=11)

    # Column divider
    ax.axvline(x=11.0, color=GREY_MID, lw=1, linestyle="--", alpha=0.4)
    ax.text(5.5, 13.4, "Main Pipeline", ha="center", fontsize=11,
            fontweight="bold", color=GREY_DARK)
    ax.text(16.5, 13.4, "Audit Loop + Output", ha="center", fontsize=11,
            fontweight="bold", color=GREY_DARK)

    # Enhancement badges
    def badge(ax, cx, cy, txt, fill, border):
        bp = FancyBboxPatch((cx - 1.4, cy - 0.21), 2.8, 0.42,
                            boxstyle="round,pad=0.06",
                            facecolor=fill, edgecolor=border,
                            linewidth=1.5, zorder=5, alpha=0.9)
        ax.add_patch(bp)
        ax.text(cx, cy, txt, ha="center", va="center", fontsize=7.5,
                fontweight="bold", color=border, zorder=6)

    badge(ax, 5.5, 9.5  - 0.95, "Enhancement 3",  GREEN_LIGHT,  GREEN_DARK)
    badge(ax, 5.5, 7.0  - 0.85, "Enhancement 2",  ORANGE_LIGHT, ORANGE_DARK)
    badge(ax, 16.5, 11.8 - 0.85, "Enhancement 1",  RED_LIGHT,    RED_DARK)

    # AppState label
    ax.text(11.0, 1.3,
            "All state flows through AppState TypedDict — nodes read and write keys; "
            "LangGraph merges partial updates.",
            ha="center", va="center", fontsize=8.5, color=GREY_MID,
            style="italic")

    plt.tight_layout()
    out = "agent_flow.png"
    plt.savefig(out, dpi=160, bbox_inches="tight", facecolor="#FAFAFA")
    plt.close()
    print(f"Saved: {out}")


if __name__ == "__main__":
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    draw_architecture()
    draw_agent_flow()
    print("Done. Both diagrams saved to diagrams/")
