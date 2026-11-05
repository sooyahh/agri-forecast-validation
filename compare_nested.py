"""Compare the original annual selection with --nested-selection outputs."""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RUNS = {"all dates": (ROOT/"results"/"walk_metrics.csv", ROOT/"results"/"nested"/"walk_metrics.csv"),
        "weekdays only": (ROOT/"results"/"walk_metrics_weekdays.csv",
                          ROOT/"results"/"nested"/"weekdays_only"/"walk_metrics.csv")}


def selected(metrics):
    m = pd.read_csv(metrics)
    m = m.loc[m.model == "Selected"].copy()
    m["period"] = m.period.astype(str)
    return m


def choices(score):
    # Per-year chosen model is the base model whose 1x metrics equal Selected's (MAE and net).
    m = pd.read_csv(score)
    m["period"] = m.period.astype(str)
    out = {}
    for period, g in m.loc[(m.cost_multiple == 1) & (m.period != "all")].groupby("period"):
        sel = g.loc[g.model == "Selected"].iloc[0]
        base = g.loc[(g.model != "Selected") & (abs(g.mae - sel.mae) < 1e-15) & (abs(g.net - sel.net) < 1e-15)]
        out[period] = "/".join(base.model) or "?"
    return out


def entries(folder):
    ledger = pd.read_csv(folder/"walk_ledger.csv.gz")
    return ledger.loc[ledger.model == "Selected"].groupby("cost_multiple").entry.sum()


def table(label, old_path, new_path, old_ledger_dir, new_ledger_dir):
    old, new = selected(old_path), selected(new_path)
    old_pick, new_pick = choices(old_path), choices(new_path)
    lines = [f"### {label}", "",
             "|Year|Selected (orig → nested)|MAE gain bp, orig [95%]|MAE gain bp, nested [95%]|Return 1x orig → nested|Return 2x orig → nested|",
             "|---|---|---:|---:|---:|---:|"]
    years = [p for p in old.period.unique() if p != "all"]
    for y in years + ["all"]:
        o1 = old.loc[(old.period == y) & (old.cost_multiple == 1)].iloc[0]
        n1 = new.loc[(new.period == y) & (new.cost_multiple == 1)].iloc[0]
        o2 = old.loc[(old.period == y) & (old.cost_multiple == 2)].iloc[0]
        n2 = new.loc[(new.period == y) & (new.cost_multiple == 2)].iloc[0]
        pick = "—" if y == "all" else f"{old_pick[y]} → {new_pick[y]}" + (" ⚑" if old_pick[y] != new_pick[y] else "")
        name = "**All (cumulative)**" if y == "all" else y
        lines.append(f"|{name}|{pick}|{o1.mae_gain*1e4:.2f} [{o1.gain_low*1e4:.2f}, {o1.gain_high*1e4:.2f}]"
                     f"|{n1.mae_gain*1e4:.2f} [{n1.gain_low*1e4:.2f}, {n1.gain_high*1e4:.2f}]"
                     f"|{o1.net:.2%} → {n1.net:.2%}|{o2.net:.2%} → {n2.net:.2%}|")
    oe, ne = entries(old_ledger_dir), entries(new_ledger_dir)
    lines += ["", f"Entries (1x / 2x cost): original {oe[1]} / {oe[2]}, nested {ne[1]} / {ne[2]}.", ""]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orig-ledgers", type=Path, default=ROOT/"results",
                        help="Folder holding the original local walk_ledger.csv.gz (and weekdays_only/)")
    args = parser.parse_args()
    lines = ["## Original vs nested selection (Selected strategy)", "",
             "⚑ = selected model changed. MAE gain is vs the zero forecast; intervals are the paired 20-day circular block bootstrap. "
             "Selection does not depend on cost, so MAE columns are identical for 1x and 2x.", ""]
    ledgers = {"all dates": (args.orig_ledgers, ROOT/"results"/"nested"),
               "weekdays only": (args.orig_ledgers/"weekdays_only", ROOT/"results"/"nested"/"weekdays_only")}
    for label, (old, new) in RUNS.items():
        lines += table(label, old, new, *ledgers[label])
    text = "\n".join(lines) + "\n"
    (ROOT/"results"/"nested"/"comparison.md").write_text(text, encoding="utf8")
    print(text)


if __name__ == "__main__":
    main()
