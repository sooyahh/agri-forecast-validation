"""Change future data, refit all models, and compare forecasts before the change."""
import argparse
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import forecast
from run import ROOT
from trading import check_ledger


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data",type=Path,default=ROOT/"data")
    args=parser.parse_args()
    out=ROOT/"results"
    original=pd.read_csv(out/"predictions.csv.gz",parse_dates=["origin","date"])
    cut=pd.Timestamp("2025-01-01")
    quotes=forecast.prices(args.data)
    future=quotes.index>=cut
    assert future.any()
    quotes.loc[future,"Corn"]*=1.35
    quotes.loc[future,"Soy"]*=0.72
    quotes["Ratio"]=quotes.Soy/quotes.Corn
    extract=forecast.features

    def altered_features(folder, price_frame):
        x,sets=extract(folder,price_frame)
        x.loc[x.index>=cut, sets["exploratory"]]=x.loc[x.index>=cut,sets["exploratory"]]*1.1
        return x,sets

    with patch.object(forecast,"prices",return_value=quotes), patch.object(forecast,"features",side_effect=altered_features):
        changed,_=forecast.run(args.data)
    keys=["origin","date","target","variant","model"]
    before=original.loc[original.origin<cut].set_index(keys).sort_index()
    after=changed.loc[changed.origin<cut].set_index(keys).sort_index()
    pd.testing.assert_index_equal(before.index,after.index)
    np.testing.assert_allclose(before.pred,after.pred,rtol=1e-9,atol=1e-10)
    assert not np.allclose(original.loc[original.origin>=cut,"pred"], changed.loc[changed.origin>=cut,"pred"])
    check_ledger()
    message=f"PASS: {len(before):,} earlier forecasts unchanged after perturbing prices and features from {cut.date()}; all forecast dates aligned; hand-calculated fills, reversal costs and terminal equity matched."
    (out/"verification.txt").write_text(message+"\n",encoding="utf-8")
    print(message)


if __name__=="__main__":
    main()
