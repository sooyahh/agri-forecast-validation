"""One-step forecasts on the intersection of observed price dates."""

from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor

TARGETS = ["Corn", "Soy", "Ratio"]
LOOKBACK = 12


def prices(folder):
    series = []
    for filename, label in zip(["corn_price.xlsx", "soybean_price.xlsx"], TARGETS):
        frame = pd.read_excel(folder / filename)
        date = pd.to_datetime(frame.Date, unit="D", origin="1899-12-30")
        if date.duplicated().any():
            raise ValueError(f"Duplicate quote date in {filename}")
        series.append(pd.Series(frame.Value.to_numpy(), index=date, name=label))
    quotes = pd.concat(series, axis=1, join="inner").sort_index()
    quotes = quotes.loc[(quotes > 0).all(axis=1)].copy()
    quotes["Ratio"] = quotes.Soy / quotes.Corn
    return quotes


def features(folder, quotes):
    daily = np.log(quotes).diff()
    x = pd.concat(
        [
            daily,
            daily.rolling(5).mean().add_suffix("_mean5"),
            daily.rolling(20).std().add_suffix("_std20"),
        ],
        axis=1,
    )
    price_cols = list(x)
    raw = pd.read_csv(folder / "drought_data.csv")
    raw["map"] = pd.to_datetime(raw.MapDate.astype(str), format="%Y%m%d")
    if not raw["map"].dt.weekday.eq(1).all():
        raise ValueError("Unexpected drought date; check release convention")
    drought = raw.groupby("map").DSCI.mean()
    drought.index += pd.Timedelta(days=7)
    x["DSCI"] = drought.reindex(x.index, method="ffill")
    drought_cols = price_cols + ["DSCI"]
    merged = pd.read_csv(
        folder / "exploratory_features.csv", parse_dates=["Date"]
    ).set_index("Date")
    extra = [
        "Corn_Condition",
        "Soy_Condition",
        "Corn_Stock_Ratio",
        "Bean_Stock_Ratio",
        "Fuel_alcohol_use",
        "Percent",
        "fertilizer_price($/mt)",
        "WTI_Price",
        "BDI",
        "Dollar_Index",
    ]
    # Diagnostic only: old merged values have unknown release dates. Carry last value
    # through the end of the price sample and explicitly record the staleness.
    latest = merged[extra].reindex(x.index, method="ffill")
    x = x.join(latest)
    return x, {
        "price": price_cols,
        "published": drought_cols,
        "exploratory": drought_cols + extra,
    }


def make_gru(width):
    # torch is imported only when a GRU is built, so price/feature code runs without it.
    from torch import nn

    class GRU(nn.Module):
        def __init__(self, width):
            super().__init__()
            self.encoder = nn.GRU(width, 24, batch_first=True)
            self.head = nn.Sequential(
                nn.LayerNorm(24), nn.Dropout(0.15), nn.Linear(24, 1)
            )

        def forward(self, x):
            return self.head(self.encoder(x)[0][:, -1]).flatten()

    return GRU(width)


def train_gru(seq, change, base, train, val):
    import torch
    from torch import nn

    torch.manual_seed(42)
    # Normalize with training inputs only. Targets are log changes, scored in price units.
    scaler = StandardScaler().fit(seq[train].reshape(-1, seq.shape[-1]))
    inputs = torch.tensor(
        scaler.transform(seq.reshape(-1, seq.shape[-1])).reshape(seq.shape),
        dtype=torch.float32,
    )
    scale = change[train].std()
    y = torch.tensor(change / scale, dtype=torch.float32)
    model = make_gru(seq.shape[-1])
    opt = torch.optim.AdamW(model.parameters(), lr=0.001)
    best, best_epoch, weights = np.inf, 0, None
    for epoch in range(1, 26):
        model.train()
        for batch in np.array_split(
            np.random.default_rng(42 + epoch).permutation(np.flatnonzero(train)),
            int(np.ceil(train.sum() / 128)),
        ):
            opt.zero_grad()
            loss = nn.functional.smooth_l1_loss(model(inputs[batch]), y[batch])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_change = model(inputs[val]).numpy() * scale
            score = np.mean(
                base[val] * np.abs(np.exp(change[val]) - np.exp(val_change))
            )
        if score < best:
            best, best_epoch, weights = score, epoch, deepcopy(model.state_dict())
        elif epoch - best_epoch >= 4:
            break
    model.load_state_dict(weights)
    model.eval()
    with torch.no_grad():
        forecast = (
            np.concatenate([model(chunk).numpy() for chunk in inputs.split(512)])
            * scale
        )
    return forecast, best_epoch


def run(folder):
    import torch

    torch.set_num_threads(1)
    quotes = prices(folder)
    x, sets = features(folder, quotes)
    # Common sample is chosen by a trailing-only validity check across all variants.
    valid = x.notna().all(axis=1).rolling(LOOKBACK).sum().eq(LOOKBACK).to_numpy()
    ends = np.flatnonzero(valid[:-1])
    dates, targets = quotes.index[ends], quotes.index[ends + 1]
    train = targets.year <= 2020
    val = (targets.year >= 2021) & (targets.year <= 2022)
    split = np.select([train, val], ["train", "val"], default="test")
    records = []
    for variant, cols in sets.items():
        arr = x[cols].to_numpy()
        seq = arr[ends[:, None] + np.arange(1 - LOOKBACK, 1)]
        flat = seq.reshape(len(seq), -1)
        for target in TARGETS:
            base = quotes[target].to_numpy()[ends]
            actual = quotes[target].to_numpy()[ends + 1]
            change = np.log(actual / base)
            predicted = {"Persistence": np.zeros(len(base))}
            scaler = StandardScaler().fit(flat[train])
            ridge = Ridge(alpha=100).fit(scaler.transform(flat[train]), change[train])
            predicted["Ridge"] = ridge.predict(scaler.transform(flat))
            # Boosting uses today's trailing summaries, GRU and Ridge use full sequences.
            gb = GradientBoostingRegressor(
                n_estimators=70,
                max_depth=2,
                min_samples_leaf=30,
                learning_rate=0.04,
                random_state=42,
            )
            gb.fit(seq[train, -1], change[train])
            predicted["GradientBoosting"] = gb.predict(seq[:, -1])
            predicted["GRU"], epoch = train_gru(seq, change, base, train, val)
            for model, forecast in predicted.items():
                records.append(
                    pd.DataFrame(
                        dict(
                            origin=dates,
                            date=targets,
                            target=target,
                            variant=variant,
                            model=model,
                            split=split,
                            base=base,
                            actual=actual,
                            pred=base * np.exp(forecast),
                            best_epoch=epoch if model == "GRU" else 0,
                        )
                    )
                )
    return pd.concat(records, ignore_index=True), quotes
