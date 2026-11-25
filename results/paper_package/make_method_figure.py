#!/usr/bin/env python3
"""Method/architecture figure F0 (SVG + PDF + PNG), deterministic. Called by make_all.py; can also run alone:
    OPENBLAS_NUM_THREADS=1 nice -n 19 venv/bin/python results/paper_package/make_method_figure.py"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")

INK, MUTED = "#1f1f1f", "#555555"
FILL = {"sense": "#E8F1FA", "shared": "#EEEEEE", "ours": "#FFF1DC", "opt": "#F4F4F4", "plant": "#E6F4EE"}
EDGE = {"sense": "#0072B2", "shared": "#7F7F7F", "ours": "#D55E00", "opt": "#7F7F7F", "plant": "#009E73"}


def box(ax, x, y, w, h, title, lines, kind, dashed=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=FILL[kind], ec=EDGE[kind],
                                lw=1.4, ls=(0, (4, 2)) if dashed else "-"))
    ax.text(x + w / 2, y + h - 0.13, title, ha="center", va="top", fontsize=8.4, fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.42, "\n".join(lines), ha="center", va="top", fontsize=7.0, color=MUTED, linespacing=1.4)


def arrow(ax, p, q, text=None, off=(0, 0.08), rad=0.0, dashed=False):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", lw=1.0, color=INK, shrinkA=2, shrinkB=2,
                                                    connectionstyle=f"arc3,rad={rad}", ls="--" if dashed else "-"))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center", va="bottom", fontsize=5.8, color=MUTED)


def main():
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.hashsalt": "govoice-f0", "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(10.6, 5.0))
    ax.set_xlim(0, 15.6); ax.set_ylim(0, 7.3); ax.axis("off")
    # row 1: sensing -> tracker -> planner -> shaper -> robot
    box(ax, 0.1, 4.2, 2.3, 2.9, "Sensing", ["2-D LiDAR scan, 10 Hz", "+ depth camera", "(±43°, 0.3–4 m)", "occupancy grid", "+ global A* path"], "sense")
    box(ax, 3.0, 4.2, 2.9, 2.9, "Tracker v3 (shared)", ["clusters minus static map", "per-point motion evidence", "CV Kalman filter",
                                                        "centroid shift 0.64 r", "stopped person kept ≤ 6 s,", "tracks held when occluded"], "shared")
    box(ax, 6.5, 3.6, 4.6, 3.5, "Risk-aware MPPI (C1, ours)", ["K = 600 Gaussian samples + 96 evasive",
                                                                 "primitives (16 dir. × 3 turns; full or 1.2 s)",
                                                                 "rollouts T = 24 × 0.1 s through RespModel",
                                                                 "cost = path/goal + static + graded collision",
                                                                 "+ geo risk  Σ_j max_t e^(−t/1.2) φ(d_j(t))",
                                                                 "(2-disc body vs. CV-predicted person)",
                                                                 "temperature λ = 0.3 (Q15(S) − min S)",
                                                                 "u = Σ_k w_k u_k,  w_k ∝ exp(−S_k/λ)"], "ours")
    box(ax, 11.75, 4.6, 1.95, 2.5, "~cs shaper", ["optional,", "deployment only:", "cap |wz| when", "strafing/reversing;", "rate limits vy, wz"], "opt", dashed=True)
    box(ax, 14.2, 4.2, 1.3, 2.9, "Robot", ["CHAMP", "(Gazebo)", "Isaac Lab", "policy", "Go2", "SportClient"], "plant")
    # row 2
    box(ax, 6.5, 0.3, 4.6, 2.7, "RespModel (shared, online)", ["per axis: v = s·tanh(g·u/s) + first-order lag",
                                                                "grid posterior over (g, s) from",
                                                                "(command, measured velocity) pairs",
                                                                "forward / reverse / lateral / yaw",
                                                                "reads no simulator parameters"], "shared")
    box(ax, 0.1, 0.3, 5.8, 2.7, "Evaluation tiers", ["fastsim: virtual clock, unmodified planner code,", "3 dynamics regimes × 2 crowd models",
                                                       "Gazebo/CHAMP: separate pre-registered family", "Isaac Lab: independent body (learned policy)",
                                                       "real Go2: not yet run"], "opt")
    arrow(ax, (2.4, 5.65), (3.0, 5.65), "points", off=(0, 0.1))
    arrow(ax, (5.9, 5.65), (6.5, 5.65), "tracks", off=(0, 0.1))
    arrow(ax, (11.1, 5.85), (11.75, 5.85), "u", off=(0, 0.1))
    arrow(ax, (13.7, 5.85), (14.2, 5.85), "cmd", off=(0, 0.1))
    ax.text(13.95, 5.45, "10 Hz", ha="center", fontsize=5.8, color=MUTED)
    arrow(ax, (14.85, 4.2), (11.1, 1.65), rad=-0.18)
    ax.text(14.0, 2.15, "odometry:\nmeasured velocity", ha="center", fontsize=5.8, color=MUTED)
    arrow(ax, (8.8, 3.0), (8.8, 3.6))
    ax.text(9.0, 3.2, "dynamics model for rollouts", ha="left", va="center", fontsize=5.8, color=MUTED)
    for i, (k, lab) in enumerate((("ours", "specific to C1"), ("shared", "shared with all tuned baselines"), ("opt", "optional / context"))):
        ax.add_patch(FancyBboxPatch((11.75, 1.25 - i * 0.45), 0.32, 0.25, boxstyle="round,pad=0.01,rounding_size=0.04", fc=FILL[k], ec=EDGE[k], lw=1.0))
        ax.text(12.2, 1.375 - i * 0.45, lab, va="center", fontsize=6.0, color=INK)
    os.makedirs(FIG, exist_ok=True)
    fig.savefig(os.path.join(FIG, "F0_architecture.svg"), bbox_inches="tight", metadata={"Date": None, "Creator": None})
    fig.savefig(os.path.join(FIG, "F0_architecture.pdf"), bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None, "Producer": None, "Creator": None})
    fig.savefig(os.path.join(FIG, "F0_architecture.png"), bbox_inches="tight", dpi=300, metadata={"Software": None})
    plt.close(fig)


if __name__ == "__main__":
    main()
