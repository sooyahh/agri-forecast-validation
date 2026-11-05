# Agricultural Forecast Validation

**Do corn and soybean price forecasts beat a persistence baseline, and does any predictive edge survive delayed execution and assumed trading costs?**

**Origin:** Ajou University · **Financial Deep Learning** · **Spring 2026 (first semester)** · group course project  
**This repository:** A subsequent, portfolio-oriented extension focused on time-series validation, information timing, simulated two-leg accounting, and reproducibility.

> **Main takeaway:** More complex forecasting models did not consistently beat persistence. Under annual out-of-sample model selection, the simulated strategy had very few entries and a negative net result. The contribution of this study is its validation and failure analysis—not a claim of a profitable or executable futures strategy.

## Project evolution and contribution

| Stage | Scope |
|---|---|
| **Original coursework (Spring 2026)** | Group assignment in Financial Deep Learning at Ajou University, studying corn and soybean forecasts and related strategy comparisons. |
| **Subsequent repository extension** | Reworked the evaluation around observed-date alignment, information availability, annual model selection, an execution-delayed return proxy, transaction-cost scenarios, uncertainty estimates, and reproducibility checks. |

The original assignment was **team work**. The follow-up implementation and validation documented here were developed with **AI coding assistance** and checked against executable tests and recorded outputs. This distinction describes the project's history; it does not imply that the original group assignment was individual work.

## What was tested

1. **Price prediction:** Compare persistence, Ridge, Gradient Boosting, and GRU for next-observation corn, soybean, and soy/corn ratio prices.
2. **Information timing:** Use historical price features and a conservatively delayed drought index; treat variables without verifiable release dates as diagnostic only.
3. **Simulation after model selection:** Select models using earlier periods, predict a two-leg holding-return proxy, delay assumed fills until the next observed close, and account for assumed rebalancing costs.
4. **Robustness and uncertainty:** Check a weekdays-only calendar, doubled-cost scenario, and paired block-bootstrap error intervals.

## Findings

**Forecast accuracy:** In the 2023–May 2026 price-forecast test window, persistence had the lowest test MAE for corn, soybeans, and their price ratio. A model that appears more sophisticated does not necessarily provide a usable predictive improvement.

**Model selection and simulated trading:** The annual validation-selected strategy had **−2.17% simulated net return** under the base cost assumption, with only **3 entries**. Doubling the assumed cost and its linked entry threshold resulted in **no entries**. These are outcomes of a constructed price-series simulation, **not verified futures-trading returns**.

**Uncertainty:** Relative to predicting zero two-leg holding return, the selected forecasts had a paired-bootstrap MAE advantage of **−0.10 bp** (95% interval **[−0.33, +0.13] bp**). This does not establish a reliable forecasting advantage; the interval does not incorporate model-refitting uncertainty.

| Additional check | Observed result |
|---|---|
| Exclude 7 weekend observations, retrain and reselect | **−0.82% simulated net return** for the selected strategy |
| Original single-split study: best directional strategy *chosen after viewing the test results* | **+3.34% simulated net return** (post-hoc comparison, not an unbiased selected-strategy estimate) |

The original single-split study and the annual extension **use different prediction targets and evaluation periods**. Their returns must not be interpreted as a controlled before/after improvement.

![Forecast accuracy relative to persistence](results/accuracy.png)

## Financial interpretation: a research simulation, not an executable futures strategy

The supplied price spreadsheets provide dates and values but do **not** document the provider, instrument/contract identifiers, units, continuous-contract construction, roll rules, price adjustments, or redistribution terms. Therefore, observed price changes cannot be confidently mapped to returns on identifiable tradable futures positions. Some observations occur on weekends or repeat earlier quotes.

The backtest assumes a hypothetical equal-gross-weight soy-long/corn-short pair (with the sign reversed for short signals), next-observation-close execution, rebalancing and terminal liquidation. The **0.15% base fee per traded notional amount** is a scenario assumption, not an observed execution cost. Actual fills, bid–ask spreads, slippage, contract rolls, margin, financing and borrow/position constraints are not reconstructed.

**Interpretation boundary:** Reported percentages describe the model's **simulated NAV changes on the supplied quote series** under those assumptions. They are **not realized P&L, investable futures returns, or evidence of profitability**. The historical test period had already been examined during the coursework, so this extension is retrospective rather than a fresh untouched out-of-sample claim. Three entries are too few to support a stable profitability inference.

**Open data limitation:** Source provenance and contract construction remain unresolved. These should be verified before making instrument-level financial claims; no provider or contract specification is assumed here.

## Methodology

- **Observed dates** — intersect the two source price files and retain positive prices on shared dates.
- **Information timing** — use trailing features; delay drought data by seven days after its Tuesday observation date. Inputs with unverified release dates are *exploratory diagnostics*, not trading inputs.
- **Forecast evaluation** — fit scalers on training inputs, select GRU checkpoints using validation MAE, and compare models on common target dates.
- **Execution-aligned proxy** — generate a signal after close at time `t`; assume execution at the following observed close. Predict the equal-weight pair's return over the *subsequent* close-to-close period.
- **Annual validation** — for each test year from 2018, train using prior years, select using the previous year, and evaluate on that year. Purge labels overlapping the next partition's first signal.
- **Simulated accounting** — equal gross leg weights, drift-aware rebalancing, assumed costs on both legs, and terminal liquidation.
- **Uncertainty** — paired circular blocks of 20 observations, 2,000 resamples. Intervals condition on the fitted models and observed quote series.

## Run

Tested on Windows with Python 3.11.9 and CPU PyTorch.

```bash
python -m venv .venv
# Activate the virtual environment, then:
python -m pip install -r requirements.txt
python smoke.py
```

`smoke.py` creates deterministic synthetic inputs in a temporary directory and checks the price calendar, causal features, sequence preparation and trading arithmetic. **Passing this smoke check does not reproduce the historical performance tables.**

For the historical experiments, place locally held source files in `data/` following [the input contract](data/README.md), then run:

```bash
python run.py
python verify.py
python walkforward.py
python walkforward.py --weekdays-only
```

Scripts write outputs under `results/`. For another input location, pass `--data PATH`. The full Windows/Python 3.11 dependency snapshot is `requirements-win311.lock`. Original historical data and row-level prediction ledgers are kept local due to unresolved provenance and redistribution terms, so cloning this repository alone does **not** reproduce historical results.

## Results and supporting documentation

- [Annual validation report — Korean](docs/순차검증.md)
- [Original price and strategy evaluation — Korean](docs/보고서.md)
- [Detailed methodology — Korean](docs/methodology.ko.md)
- [Independent-environment reproduction record — Korean](docs/reproducibility.ko.txt)
- [Annual metrics](results/walk_metrics.csv) and [weekdays-only sensitivity](results/walk_metrics_weekdays.csv)
- [Single-split forecast and strategy comparison](results/forecast_vs_strategy.csv)
