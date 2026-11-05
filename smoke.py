"""Deterministic synthetic checks; no historical input files required."""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from forecast import prices, features, LOOKBACK
from trading import check_ledger


def main():
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        dates = pd.bdate_range("2019-01-01", periods=120)
        serial = (dates-pd.Timestamp("1899-12-30")).days
        for filename, start in [("corn_price.xlsx",4),("soybean_price.xlsx",10)]:
            pd.DataFrame({"Date":serial,"Value":start*np.exp(np.arange(120)*.0002)}).to_excel(folder/filename,index=False)
        maps = pd.date_range("2018-12-25",periods=30,freq="W-TUE")
        pd.DataFrame({"Name":"Synthetic","MapDate":maps.strftime("%Y%m%d"),"DSCI":np.arange(30)}).to_csv(folder/"drought_data.csv",index=False)
        extra = ["Corn_Condition","Soy_Condition","Corn_Stock_Ratio","Bean_Stock_Ratio",
                 "Fuel_alcohol_use","Percent","fertilizer_price($/mt)","WTI_Price","BDI","Dollar_Index"]
        merged = pd.DataFrame({name:1. for name in extra},index=dates)
        merged.index.name="Date"
        merged.to_csv(folder/"final_features_for_DL (2).csv")
        q=prices(folder)
        x,sets=features(folder,q)
        future=q.copy()
        future.loc[dates[80]:,["Corn","Soy"]]*=2
        future["Ratio"]=future.Soy/future.Corn
        changed,_=features(folder,future)
        pd.testing.assert_frame_equal(x.loc[:dates[79]],changed.loc[:dates[79]])
        assert len(q)==120 and q.index.is_unique
        assert x.DSCI.loc["2019-01-01"]==0
        assert x[sets["published"]].dropna().shape[0]>=LOOKBACK
        check_ledger()
    print("PASS: synthetic calendar, causal inputs, delayed drought and hand-calculated trade accounting")


if __name__=="__main__":
    main()
