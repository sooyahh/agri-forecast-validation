"""Run from any directory: python run.py [--data PATH]."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from forecast import run, prices, TARGETS
from trading import strategies, check_ledger

ROOT = Path(__file__).resolve().parent


def score(pred):
    group = ["split", "target", "variant", "model", "period"]
    years = pred.assign(period=pred.date.dt.year.astype(str))
    all_rows = pd.concat([years, pred.assign(period="all")])
    all_rows["abs_error"] = (all_rows.pred - all_rows.actual).abs()
    all_rows["sq_error"] = all_rows.abs_error**2
    m = (
        all_rows.groupby(group)
        .agg(MAE=("abs_error", "mean"), MSE=("sq_error", "mean"), n=("actual", "size"))
        .reset_index()
    )
    m["RMSE"] = np.sqrt(m.pop("MSE"))
    keys = ["split", "target", "variant", "period"]
    base = m.loc[m.model == "Persistence", keys + ["MAE"]].rename(
        columns={"MAE": "baseline_MAE"}
    )
    m = m.merge(base, on=keys, validate="many_to_one")
    m["improvement_pct"] = 100 * (1 - m.MAE / m.baseline_MAE)
    return m


def finish(pred, quotes, out):
    check_ledger()
    for target, frame in pred.groupby("target"):
        counts = frame.groupby(["origin", "date"]).size()
        assert (
            counts.eq(12).all()
            and not frame.duplicated(["variant", "model", "date"]).any()
        )
        assert frame.origin.lt(frame.date).all()
        assert np.allclose(frame.actual, quotes.loc[frame.date, target].to_numpy())
    m = score(pred)
    m.to_csv(out / "model_metrics.csv", index=False)
    primary = m.loc[(m.period == "all") & (m.variant != "exploratory")]
    val = (
        primary.loc[primary.split == "val"]
        .sort_values(["MAE", "model", "variant"])
        .drop_duplicates("target")
    )
    val.to_csv(out / "validation_choices.csv", index=False)
    tests = primary.loc[primary.split == "test"].sort_values(
        ["MAE", "model", "variant"]
    )
    ledger, trade = strategies(pred, quotes)
    ledger.to_csv(out / "ledger.csv.gz", index=False)
    trade.to_csv(out / "strategy_metrics.csv", index=False)
    joined = trade.merge(
        tests.loc[
            tests.target == "Ratio",
            ["variant", "model", "MAE", "RMSE", "improvement_pct"],
        ],
        on=["variant", "model"],
        how="left",
        validate="many_to_one",
    )
    joined.to_csv(out / "forecast_vs_strategy.csv", index=False)
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), layout="constrained")
    for ax, target in zip(axes, TARGETS):
        t = tests.loc[tests.target == target]
        for variant, frame in t.groupby("variant"):
            ax.plot(
                frame.model.sort_values(),
                frame.set_index("model").sort_index().improvement_pct,
                "o-",
                label=variant,
            )
        ax.axhline(0, color="gray", lw=1)
        ax.set_title(target + " | test MAE improvement vs persistence (%)")
        ax.legend()
    fig.savefig(out / "accuracy.png", dpi=140)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4), layout="constrained")
    for (model, rule), frame in ledger.loc[
        (ledger.variant == "published") & (ledger.cost_multiple == 1)
    ].groupby(["model", "rule"]):
        ax.plot(frame.date, frame.equity, label=model + " / " + rule)
    ax.legend(fontsize=7, ncol=2)
    ax.set(title="Published inputs | net simulated wealth", ylabel="Initial wealth = 1")
    fig.savefig(out / "wealth.png", dpi=140)
    plt.close(fig)
    lines = [
        "# 옥수수와 대두의 다음 관측일 가격예측",
        "",
        f"원본에서 두 품목의 양수 가격이 함께 관측된 날은 {len(quotes):,}일이다. 공통 테스트 목표일은 {pred.loc[pred.split == 'test', 'date'].min():%Y-%m-%d}부터 {pred.date.max():%Y-%m-%d}까지 {pred.loc[pred.split == 'test', 'date'].nunique():,}일이다. 기존 과제에서 이미 살펴본 기간을 포함한다.",
        "",
        "## 가격예측 결과",
        "",
        "|목표|검증 MAE로 선택|테스트 MAE|기준 MAE|기준 대비 개선|테스트 사후 최저 MAE|",
        "|---|---|---:|---:|---:|---|",
    ]
    for target in TARGETS:
        chosen = val.loc[val.target == target].iloc[0]
        best = tests.loc[tests.target == target].iloc[0]
        r = tests.loc[
            (tests.target == target)
            & (tests.model == chosen.model)
            & (tests.variant == chosen.variant)
        ].iloc[0]
        lines.append(
            f"|{target}|{r.model} ({r.variant})|{r.MAE:.4f}|{r.baseline_MAE:.4f}|{r.improvement_pct:+.2f}%|{best.model} ({best.variant}), {best.MAE:.4f}|"
        )
    lines.extend(
        [
            "",
            "## 공개 가뭄 지수를 추가한 효과",
            "",
            "같은 테스트 날짜에서 입력만 바꾼 MAE다. ‘차이’가 음수이면 가뭄 지수를 추가한 쪽의 오차가 작다.",
            "",
            "|목표|모델|가격만|가격+가뭄|차이|",
            "|---|---|---:|---:|---:|",
        ]
    )
    for (target, model), pair in tests.loc[tests.model != "Persistence"].groupby(
        ["target", "model"]
    ):
        scores = pair.set_index("variant").MAE
        lines.append(
            f"|{target}|{model}|{scores.price:.5f}|{scores.published:.5f}|{scores.published - scores.price:+.5f}|"
        )
    lines.extend(["", "## 큰 오차가 난 날", ""])
    for target in TARGETS:
        c = val.loc[val.target == target].iloc[0]
        f = pred.loc[
            (pred.target == target)
            & (pred.variant == c.variant)
            & (pred.model == c.model)
            & (pred.split == "test")
        ]
        row = f.loc[(f.actual - f.pred).abs().idxmax()]
        lines.append(
            f"- {target} 최대 오차는 {row.date:%Y-%m-%d}. 전 관측값 {row.base:.4f}, 예측 {row.pred:.4f}, 실제 {row.actual:.4f}. 원자료의 급변 원인은 계약·롤 정보 없이 확정하기 어렵다."
        )
    lines.extend(
        [
            "",
            "## 가격비율 예측과 거래 성과",
            "",
            "|신호|입력·모델|비용 차감 누적수익률|MDD|Sharpe|진입 횟수|비용 2배 수익률|",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    best = tests.loc[tests.target == "Ratio"].iloc[0]
    for rule in ["direction", "mean_reversion"]:
        group = trade.loc[
            (trade.rule == rule) & (trade.cost_multiple == 1)
        ].sort_values("net", ascending=False)
        for label, r in [
            (
                "비율 MAE 최저",
                group.loc[
                    (group.variant == best.variant) & (group.model == best.model)
                ].iloc[0],
            ),
            ("해당 규칙 수익률 최고(사후)", group.iloc[0]),
        ]:
            double = trade.loc[
                (trade.rule == rule)
                & (trade.cost_multiple == 2)
                & (trade.variant == r.variant)
                & (trade.model == r.model)
            ].iloc[0]
            sharpe = f"{r.sharpe:.2f}" if pd.notna(r.sharpe) else "미정의"
            lines.append(
                f"|{label} / {rule}|{r.variant} · {r.model}|{r.net:.2%}|{r.mdd:.2%}|{sharpe}|{r.entries}|{double.net:.2%}|"
            )
    sma = trade.loc[(trade.model == "SMA60") & (trade.cost_multiple == 1)].iloc[0]
    lines.extend(
        [
            "",
            f"기존 60일 이동평균 신호를 같은 체결 규칙으로 평가한 결과는 누적 {sma.net:.2%}, MDD {sma.mdd:.2%}, 진입 {sma.entries}회였다.",
            "비율 MAE가 가장 낮은 현재값 기준모형은 예상 변화가 항상 0이라 방향 전략에서 거래하지 않는다. 방향 전략 표의 최대 수익률은 테스트를 본 뒤 집계한 값이다.",
        ]
    )
    lines.extend(
        [
            "",
            "예측 오차는 신호일에서 다음 종가까지의 가격 차이를 평가한다. 거래는 그 종가에서 체결하므로 이후 가격 변화만 손익이 된다. 방향 전략의 수익률에는 진입 문턱과 포지션 회전 비용도 반영된다. 거래 결과는 동일 가중 모의 가격계열 성과이며 계약 롤, 증거금, 차입 비용은 반영하지 않았다.",
            "",
            "모델별 전체·연도별 MAE와 RMSE, 기준 대비 개선율은 model_metrics.csv에, 거래 횟수·회전율·비용 민감도는 strategy_metrics.csv에 있다. exploratory는 발표 시점을 보장할 수 없는 자료를 사용한 진단용 비교이며 모델 선정 및 거래에서 제외했다.",
        ]
    )
    (out / "보고서.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    pred, quotes = run(args.data)
    pred.to_csv(out / "predictions.csv.gz", index=False)
    finish(pred, quotes, out)


if __name__ == "__main__":
    main()
