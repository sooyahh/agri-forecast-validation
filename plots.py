"""Draw README figures from the committed aggregate results (no raw data needed).

Usage: python plots.py
Reads results/walk_metrics.csv and results/model_metrics.csv, writes
results/annual_validation.png and results/test_mae_vs_persistence.png.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results"

INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"price": "#2a78d6", "published": "#eb6834"}
SELECTED = "#2a78d6"
MODEL_NAMES = {"GB": "GB", "GRU": "GRU", "Ridge": "Ridge", "Zero": "Zero"}

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INK_2, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def selected_models(walk):
    """Recover the model chosen each year: its yearly MAE equals the Selected MAE."""
    base = walk.loc[(walk.cost_multiple == 1) & (walk.period != "all")]
    chosen = {}
    for year, frame in base.groupby("period"):
        mae = frame.set_index("model").mae
        candidates = mae.drop("Selected")
        match = candidates.index[np.isclose(candidates, mae["Selected"], rtol=0, atol=1e-15)]
        if len(match) != 1:
            raise ValueError(f"Cannot identify the selected model for {year}: {list(match)}")
        chosen[year] = match[0]
    return chosen


def annual_figure(walk):
    chosen = selected_models(walk)
    sel = walk.loc[(walk.model == "Selected") & (walk.cost_multiple == 1) & (walk.period != "all")].copy()
    sel = sel.sort_values("period")
    years = sel.period.astype(str).tolist()
    x = np.arange(len(years))
    gain, low, high = (sel[c].to_numpy() * 1e4 for c in ("mae_gain", "gain_low", "gain_high"))
    net = sel.net.to_numpy() * 100
    labels = [f"{y}\n{MODEL_NAMES[chosen[y]]}" for y in years]

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True, layout="constrained",
                                      gridspec_kw={"height_ratios": [3, 2]})
    for ax in (top, bottom):
        ax.axhline(0, color=INK_2, lw=1)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    top.errorbar(x, gain, yerr=[gain - low, high - gain], fmt="o", ms=7, color=SELECTED,
                 ecolor=SELECTED, elinewidth=2, capsize=0)
    for xi, model in zip(x, [chosen[y] for y in years]):
        if model == "Zero":
            top.annotate("no trade", (xi, 0), xytext=(0, 9), textcoords="offset points",
                         ha="center", fontsize=8, color=INK_2)
    top.set_ylabel("MAE gain vs zero forecast (bp)\nwith 95% block-bootstrap interval")
    top.set_title("Annual out-of-sample validation: model chosen on the previous year, applied to the next",
                  loc="left", fontsize=11)

    bottom.bar(x, net, width=0.5, color=SELECTED)
    for xi, value in zip(x, net):
        if abs(value) > 1e-9:
            bottom.annotate(f"{value:.2f}%", (xi, value), xytext=(0, -12), textcoords="offset points",
                            ha="center", fontsize=8, color=INK)
    bottom.set_ylabel("Simulated net return (%)\nbase cost 0.15% per leg")
    lim = max(0.5, abs(net).max() * 1.6)
    bottom.set_ylim(-lim, lim / 3)
    bottom.set_xticks(x, labels)
    bottom.set_xlabel("Evaluation year / model selected on the previous year (2026: Jan-May)", color=INK_2)

    fig.savefig(OUT / "annual_validation.png", dpi=150)
    plt.close(fig)


def accuracy_figure(metrics):
    test = metrics.loc[(metrics.split == "test") & (metrics.period == "all")
                       & (metrics.variant.isin(SERIES)) & (metrics.model != "Persistence")]
    models = ["GRU", "GradientBoosting", "Ridge"]
    names = {"GRU": "GRU", "GradientBoosting": "Gradient Boosting", "Ridge": "Ridge"}
    targets = [("Corn", "Corn"), ("Soy", "Soybean"), ("Ratio", "Soy/corn ratio")]
    low = min(test.improvement_pct.min() * 1.15, -0.5)

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.2), sharey=True, sharex=True, layout="constrained")
    offsets = {"price": -0.12, "published": 0.12}
    for ax, (target, title) in zip(axes, targets):
        frame = test.loc[test.target == target]
        ax.axvline(0, color=INK, lw=1.2)
        ax.grid(axis="x", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for variant, color in SERIES.items():
            values = frame.loc[frame.variant == variant].set_index("model").improvement_pct.reindex(models)
            ax.scatter(values, np.arange(len(models)) + offsets[variant], s=46, color=color,
                       edgecolor="white", linewidth=1.5, zorder=3, label=variant)
        ax.set_title(title, loc="left", fontsize=10)
        ax.set_xlim(low, 0.6)
        ax.text(0.08, -0.55, "persistence", fontsize=8, color=INK_2, va="top")
    axes[0].set_yticks(range(len(models)), [names[m] for m in models])
    axes[0].set_ylim(len(models) - 0.3, -0.7)
    axes[1].set_xlabel("Test MAE improvement vs persistence (%), 2023 - May 2026; right of 0 = better")
    handles, _ = axes[0].get_legend_handles_labels()
    fig.legend(handles, ["price inputs", "price + delayed drought index"], loc="outside upper right",
               ncol=2, frameon=False, fontsize=9)
    fig.suptitle("Next-observation price forecasts: no model beat persistence", x=0.01, ha="left",
                 fontsize=11, color=INK)
    fig.savefig(OUT / "test_mae_vs_persistence.png", dpi=150)
    plt.close(fig)


def main():
    annual_figure(pd.read_csv(OUT / "walk_metrics.csv"))
    accuracy_figure(pd.read_csv(OUT / "model_metrics.csv"))
    print("Wrote results/annual_validation.png and results/test_mae_vs_persistence.png")


if __name__ == "__main__":
    main()
