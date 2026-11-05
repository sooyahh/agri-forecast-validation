"""Close-to-close simulation with drifted weights and two-leg fees."""
import numpy as np
import pandas as pd


def simulate(quotes, desired, fee):
    # desired is already aligned to the execution date (prediction's target date).
    # Initial wealth = 1; signed asset notionals allow a short leg.
    holdings = np.zeros(2)
    wealth = 1.
    last_side = 0
    rows = []
    returns = quotes[["Soy","Corn"]].pct_change().fillna(0).to_numpy()
    for i, (date, side) in enumerate(desired.items()):
        if i == len(desired)-1:
            side = 0  # liquidate at final close
        pnl = holdings * returns[i]
        drifted = holdings + pnl
        old = wealth
        before = wealth + pnl.sum()
        weights = np.array([0.5*side, -0.5*side])
        after = before
        for _ in range(8):
            after = before - fee * np.abs(weights*after-drifted).sum()
        holdings = weights * after
        delta = holdings - drifted
        cost = np.abs(delta).sum()*fee
        wealth = before - cost
        rows.append(dict(date=date,side=side,entry=int(side!=0 and side!=last_side),
                         soy_trade=delta[0],corn_trade=delta[1],cost=cost,turnover=np.abs(delta).sum()/old,
                         gross_pnl=pnl.sum(),net_return=wealth/old-1,equity=wealth))
        last_side = side
    return pd.DataFrame(rows)


def mean_reversion(frame):
    # At origin t, yesterday's one-step forecast for t has already settled.
    actual = frame.base
    gap = actual - frame.pred.shift()
    past = gap.shift().rolling(60)
    z = (gap-past.mean()) / past.std(ddof=0).replace(0,np.nan)
    side = 0
    out = []
    for v in z:
        if pd.isna(v) or abs(v)<0.5:
            side=0
        elif v>1.5:
            side=-1
        elif v< -1.5:
            side=1
        out.append(side)
    return np.array(out)


def strategies(pred, quotes):
    ledgers=[]
    summaries=[]
    ratio = pred.loc[(pred.target=="Ratio") & (pred.variant!="exploratory")]
    sma = ratio.loc[(ratio.variant=="price") & (ratio.model=="Persistence")].copy()
    sma["model"] = "SMA60"
    sma["pred"] = quotes.Ratio.rolling(60).mean().reindex(sma.origin).to_numpy()
    ratio = pd.concat([ratio,sma],ignore_index=True)
    for (variant,model),frame in ratio.groupby(["variant","model"]):
        frame = frame.sort_values("date").set_index("date")
        is_test = frame.split.eq("test")
        if not (frame.origin.iloc[1:].to_numpy()==frame.index[:-1].to_numpy()).all():
            raise ValueError("Non-contiguous signals; check observed dates")
        test = frame.loc[is_test]
        q = quotes.loc[test.index]
        for multiplier in [1,2]:
            fee=0.0015*multiplier
            # Equal-weight pair approximates half the forecast relative ratio change.
            edge = 0.5*(frame.pred/frame.base-1)
            for rule,side in [("direction", np.where(edge.abs()>2*fee,np.sign(edge),0)),
                              ("mean_reversion", mean_reversion(frame))]:
                if model=="SMA60" and rule=="direction":
                    continue
                positions = pd.Series(side,index=frame.index).loc[test.index]
                ledger=simulate(q,positions,fee)
                labels=dict(variant=variant,model=model,rule=rule,cost_multiple=multiplier)
                ledger=ledger.assign(origin=test.origin.to_numpy(),**labels)
                equity=np.r_[1.,ledger.equity.to_numpy()]
                daily=ledger.net_return
                summaries.append(dict(**labels,net=equity[-1]-1,mdd=(equity/np.maximum.accumulate(equity)-1).min(),
                    sharpe=np.sqrt(252)*daily.mean()/daily.std() if daily.std()>0 else np.nan,
                    turnover=ledger.turnover.sum(),entries=int(ledger.entry.sum()),cost=ledger.cost.sum()))
                ledgers.append(ledger)
    return pd.concat(ledgers,ignore_index=True),pd.DataFrame(summaries)


def check_ledger():
    # At first fill the initial long soy notional is exactly half the post-fee NAV.
    idx=pd.date_range("2020-01-01",periods=4)
    q=pd.DataFrame(dict(Soy=[5.,10.,11.,11.],Corn=[8.,8.,8.,8.]),index=idx)
    l=simulate(q,pd.Series([0,1,-1,0],index=idx),0.01)
    entry=1/1.01
    # Direct reversal: old absolute notional grows to 1.05*entry.
    reversal=1.05*entry*(1-0.01)/1.01
    np.testing.assert_allclose(l.equity,[1,entry,reversal,0.99*reversal])
    np.testing.assert_allclose(l.gross_pnl,[0,0,0.05*entry,0])
