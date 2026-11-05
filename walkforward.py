"""Annual expanding-window forecast of the actual two-leg holding return."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor

import plots
from forecast import prices, features, train_gru, LOOKBACK
from trading import simulate, check_ledger, BASE_FEE, ENTRY_FEE_MULTIPLE

ROOT = Path(__file__).resolve().parent
BOOTSTRAP_BLOCK = 20  # circular block length in observations
BOOTSTRAP_DRAWS = 2000  # bootstrap resamples per interval


def folds(q, folder):
    x, sets = features(folder, q)
    arr = x[sets["published"]].to_numpy()
    ends = np.arange(LOOKBACK - 1, len(q) - 2)
    seq = arr[ends[:, None] + np.arange(1 - LOOKBACK, 1)]
    valid = np.isfinite(seq).all(axis=(1, 2))
    ends, seq = ends[valid], seq[valid]
    origin, entry, exit_date = (q.index[ends + k] for k in (0, 1, 2))
    legs = q[["Soy", "Corn"]].pct_change().to_numpy()[ends + 2]
    actual = 0.5 * (legs[:, 0] - legs[:, 1])
    flat = seq.reshape(len(seq), -1)
    outputs = []
    for year in range(2018, exit_date[-1].year + 1):
        test = exit_date.year == year
        val = (exit_date.year == year - 1) & (exit_date < origin[test].min())
        train = (exit_date.year < year - 1) & (exit_date < origin[val].min())
        assert (
            exit_date[train].max()
            < origin[val].min()
            < exit_date[val].max()
            < origin[test].min()
        )
        preds = {"Zero": np.zeros(len(seq))}
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=100)).fit(
            flat[train], actual[train]
        )
        preds["Ridge"] = ridge.predict(flat)
        gb = GradientBoostingRegressor(
            n_estimators=70,
            max_depth=2,
            min_samples_leaf=30,
            learning_rate=0.04,
            random_state=42,
        )
        gb.fit(seq[train, -1], actual[train])
        preds["GB"] = gb.predict(seq[:, -1])
        log_pred, epoch = train_gru(
            seq, np.log1p(actual), np.ones(len(seq)), train, val
        )
        preds["GRU"] = np.expm1(log_pred)
        choice = min(
            preds, key=lambda name: np.mean(abs(preds[name][val] - actual[val]))
        )
        preds["Selected"] = preds[choice]
        for model, p in preds.items():
            outputs.append(
                pd.DataFrame(
                    dict(
                        year=year,
                        signal=origin[test],
                        entry=entry[test],
                        exit=exit_date[test],
                        actual=actual[test],
                        prediction=p[test],
                        model=model,
                        selected=choice,
                        train_end=exit_date[train].max(),
                        val_end=exit_date[val].max(),
                        gru_epoch=epoch,
                    )
                )
            )
    return pd.concat(outputs, ignore_index=True)


def intervals(ret, advantage, block=BOOTSTRAP_BLOCK):
    # Paired circular block bootstrap preserves within-block dependence.
    rng = np.random.default_rng(42)
    n = len(ret)
    starts = rng.integers(n, size=(BOOTSTRAP_DRAWS, int(np.ceil(n / block))))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(BOOTSTRAP_DRAWS, -1)[
        :, :n
    ]
    gains = np.expm1(np.log1p(ret)[idx].sum(axis=1))
    return [
        *np.quantile(gains, [0.025, 0.975]),
        *np.quantile(advantage[idx].mean(axis=1), [0.025, 0.975]),
    ]


def evaluate(pred, q, out):
    records, ledgers = [], []
    for model, f in pred.groupby("model"):
        f = f.sort_values("exit")
        dates = pd.DatetimeIndex([f.entry.iloc[0], *f.exit])
        assert np.array_equal(dates[:-1], f.entry) and dates.is_unique
        for mult in (1, 2):
            fee = BASE_FEE * mult
            position = np.where(
                f.prediction.abs() > ENTRY_FEE_MULTIPLE * fee, np.sign(f.prediction), 0
            )
            ledger = simulate(
                q.loc[dates], pd.Series(np.r_[position, 0], index=dates), fee
            )
            # Today's price movement belongs to yesterday's post-cost position.
            expected_pnl = (
                ledger.equity.to_numpy()[:-1] * position * f.actual.to_numpy()
            )
            np.testing.assert_allclose(
                ledger.gross_pnl.iloc[1:], expected_pnl, atol=1e-12
            )
            ledger["signal_for_fill"] = list(f.signal) + [pd.NaT]
            ledger = ledger.assign(model=model, cost_multiple=mult)
            ledgers.append(ledger)
            advantage = (f.actual.abs() - (f.actual - f.prediction).abs()).to_numpy()
            daily = ledger.net_return.to_numpy()[1:].copy()
            daily[0] = (1 + ledger.net_return.iloc[0]) * (1 + daily[0]) - 1
            for period in ["all", *f.year.unique()]:
                mask = (
                    np.ones(len(f), dtype=bool)
                    if period == "all"
                    else (f.year == period).to_numpy()
                )
                r = daily[mask]
                equity = np.r_[1, np.cumprod(1 + r)]
                lo, hi, a, b = intervals(r, advantage[mask])
                records.append(
                    dict(
                        model=model,
                        cost_multiple=mult,
                        period=period,
                        n=len(r),
                        mae=np.mean(abs(f.actual - f.prediction)[mask]),
                        mae_gain=advantage[mask].mean(),
                        gain_low=a,
                        gain_high=b,
                        net=equity[-1] - 1,
                        net_low=lo,
                        net_high=hi,
                        mdd=min(equity / np.maximum.accumulate(equity) - 1),
                    )
                )
    pd.concat(ledgers).to_csv(out / "walk_ledger.csv.gz", index=False)
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--weekdays-only",
        action="store_true",
        help="Repeat all folds after excluding weekend observations",
    )
    args = parser.parse_args()
    torch.set_num_threads(1)
    check_ledger()
    q = prices(args.data)
    weekend_count = int((q.index.weekday >= 5).sum())
    flat_count = int(q[["Soy", "Corn"]].diff().eq(0).all(axis=1).sum())
    if args.weekdays_only:
        q = q.loc[q.index.weekday < 5]
    pred = folds(q, args.data)
    out = ROOT / "results"
    if args.weekdays_only:
        out = out / "weekdays_only"
    out.mkdir(exist_ok=True, parents=True)
    pred.to_csv(out / "walk_predictions.csv.gz", index=False)
    score = evaluate(pred, q, out)
    score.to_csv(out / "walk_metrics.csv", index=False)
    summary = score.loc[(score.period == "all") & (score.model == "Selected")]
    lines = [
        "# 체결 이후 수익률을 예측한 연도별 검증",
        "",
        "오늘 마감에 다음 관측일의 체결을 결정하고, 그다음 관측일까지 보유한다. 목표값은 보유 구간 대두 수익률의 절반에서 옥수수 수익률의 절반을 뺀 값이다. 가격 이력과 공개 시점을 늦춘 가뭄 지수로 이를 예측한다.",
        "",
        "2018년부터 매년 전년 검증 MAE로 0 예측·Ridge·GB·GRU 중 하나를 선택하고 다음 해에 고정한다. 학습·검증 경계에는 목표가 다음 구간의 최초 신호 전에 확정된 행만 사용한다. 비용은 양쪽 포지션 변동액에 부과하며 연도 경계에서도 자본과 보유액을 이어간다.",
        "",
        "|비용|누적 모의수익률|95% 구간|최대낙폭|0 예측 대비 MAE 개선 (bp)|95% 구간 (bp)|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in summary.itertuples():
        lines.append(
            f"|{r.cost_multiple}배|{r.net:.2%}|{r.net_low:.2%} ~ {r.net_high:.2%}|{r.mdd:.2%}|{r.mae_gain * 1e4:.2f}|{r.gain_low * 1e4:.2f} ~ {r.gain_high * 1e4:.2f}|"
        )
    lines += [
        "",
        "모델 선택까지 포함한 실제 연도별 결과",
        "",
        "|평가연도|선택 모델|관측 수|MAE 개선 (bp)|누적수익률|",
        "|---|---|---:|---:|---:|",
    ]
    for r in score.loc[
        (score.period != "all")
        & (score.model == "Selected")
        & (score.cost_multiple == 1)
    ].itertuples():
        chosen = pred.loc[pred.year == r.period, "selected"].iloc[0]
        lines.append(f"|{r.period}|{chosen}|{r.n}|{r.mae_gain * 1e4:.2f}|{r.net:.2%}|")
    lines += [
        "",
        f"구간은 같은 날의 기준모형과 모델 오차를 짝지어 {BOOTSTRAP_BLOCK}관측일 원형 블록을 {BOOTSTRAP_DRAWS:,}회 재표집한 백분위 구간이다. 손익 구간은 실현된 비용 차감 수익열을 같은 방식으로 재표집했다. 모델 재학습·데이터 출처 불확실성은 구간 밖에 있다. 마지막 연도는 부분 연도이며 앞서 본 기간을 활용한 회고 검증이다.",
        "",
        "## 가격 원자료 추적",
        "",
        "두 엑셀은 Sheet1의 Date와 Value만 제공한다. 문서 속성에는 공급자·종목 코드·단위·계약 월물·롤 및 가격 조정 규칙이 없다. 아래 지문은 이번 연구 입력을 식별한다. 실제 선물 계약 수익률로 해석하려면 공급자 원본이나 계약별 자료가 추가로 필요하다.",
        "",
    ]
    for name in ("corn_price.xlsx", "soybean_price.xlsx"):
        lines.append(
            f"- {name} SHA-256: {hashlib.sha256((args.data / name).read_bytes()).hexdigest()}"
        )
    jumps = q.pct_change().abs()
    lines += ["", "가장 큰 관측 가격 변동(절댓값)은 다음과 같다. 원인은 미확정이다."]
    lines.append(
        f"원본 양수 공통 가격 중 주말 날짜가 {weekend_count}개이고, 두 가격 모두 직전 관측값과 같은 날짜는 {flat_count}개다. 현재 달력은 {'주말 제외' if args.weekdays_only else '원본 공통 날짜'}다. 날짜를 실제 거래소 세션과 일치시키려면 공급자 정보가 필요하다."
    )
    for name in ("Soy", "Corn"):
        date = jumps[name].idxmax()
        lines.append(f"- {name}: {date.date()} · {jumps.loc[date, name]:.2%}")
    ledger = pd.read_csv(out / "walk_ledger.csv.gz")
    counts = ledger.loc[ledger.model == "Selected"].groupby("cost_multiple").entry.sum()
    lines += [
        "",
        f"선택 전략의 기본 비용 진입은 {counts[1]}회, 비용 2배 진입은 {counts[2]}회다. 거래 횟수가 적을수록 손익 재표집 구간의 해석이 제한된다.",
    ]
    (out / "순차검증.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    plots.annual_figure(pd.read_csv(out / "walk_metrics.csv"), out)


if __name__ == "__main__":
    main()
