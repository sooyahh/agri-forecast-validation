# Data source audit

Audit date: 2026-11-05. Each statement below holds only for the comparison range given. A file's producer, the site it was downloaded from, and whether the local file is identical to an official release are treated as separate questions. Release timestamps, historical vintages and redistribution terms were not reconstructed unless stated.

## Summary

| Input | Producer | Status |
|---|---|---|
| Corn and soybean price spreadsheets | Unidentified | Partial matches only |
| Drought index (DSCI) | U.S. Drought Monitor | All 6,078 rows match the official API |
| Combined exploratory feature file | Built by the coursework preprocessing script | Derived; upstream sources below |

The drought index is the only non-price input used for model selection and trading, and it is fully traceable. The price series remain unidentified, so returns stay simulated and raw files are not published.

## Files read by the code

### Corn and soybean prices (`corn_price.xlsx`, `soybean_price.xlsx`)

`Date` is an Excel serial day and `Value` is a price. Candidates checked: Macrotrends historical price pages, a public archive of Macrotrends-format CSVs, and Yahoo Finance continuous futures closes (`ZC=F`, `ZS=F`) divided by 100.

| Series | Public Macrotrends-format archive | Yahoo Finance close / 100 |
|---|---|---|
| Corn | 905 of 3,229 overlapping days equal | 1,659 of 4,879 days equal (`ZC=F`) |
| Soybean | 845 of 3,227 overlapping days equal | 1,043 of 4,878 days equal (`ZS=F`) |

No candidate matches the full file. Provider, contract months, roll method and price adjustments remain unidentified.

- Macrotrends: [corn](https://www.macrotrends.net/2532/corn-prices-historical-chart-data.html), [soybean](https://www.macrotrends.net/2531/soybean-prices-historical-chart-data.html)
- Archive: [corn](https://github.com/ztizzlegaming/agricultural-time-series/blob/master/code/corn-prices-historical-chart-data.csv), [soybean](https://github.com/ztizzlegaming/agricultural-time-series/blob/master/code/soybean-prices-historical-chart-data.csv)
- Yahoo Finance: [ZC=F](https://finance.yahoo.com/quote/ZC=F/history/), [ZS=F](https://finance.yahoo.com/quote/ZS=F/history/)

### Drought index (`drought_data.csv`)

- **Series:** Drought Severity and Coverage Index (DSCI), weekly, U.S. Drought Monitor.
- **States:** Illinois, Indiana, Iowa, Minnesota, Nebraska, Ohio (FIPS 17, 18, 19, 27, 31, 39).
- **Check:** all 6,078 `Name × MapDate` rows match the official USDM data service, for example `https://usdmdataservices.unl.edu/api/StateStatistics/GetDSCI?aoi=17&startdate=12/26/2006&enddate=5/26/2026&statisticsType=1`.
- **Timing:** `MapDate` is the observation date, not the release date. The code uses each value only seven days after its `MapDate`.
- **References:** [download page](https://droughtmonitor.unl.edu/DmData/DataDownload.aspx), [DSCI definition](https://droughtmonitor.unl.edu/About/AbouttheData/DSCI.aspx), [web service specification](https://droughtmonitor.unl.edu/DmData/DataDownload/WebServiceInfo.aspx).

### Combined exploratory feature file

This file was built by the coursework preprocessing script, which merges the sources below with date alignment and forward filling. The later version adds the fuel-alcohol columns. It does not correspond to any single external release, and its release timing cannot be verified. The project therefore uses it only for diagnostic comparisons, never for model selection or trading.

## Upstream sources of the exploratory features

| Local source file | Producer and series | Check result | Caveat |
|---|---|---|---|
| `WTI.csv` | U.S. EIA, WTI Cushing spot price, daily, USD/barrel ([FRED DCOILWTICO](https://fred.stlouisfed.org/series/DCOILWTICO)) | All 4,804 same-date valid observations match | Spot price, not futures |
| `dollar_index.csv` | Federal Reserve Board, nominal broad dollar index via FRED: [DTWEXB](https://fred.stlouisfed.org/series/DTWEXB) for 2007–2019, [DTWEXBGS](https://fred.stlouisfed.org/series/DTWEXBGS) for 2020-01-02 to 2026-05-15 | 3,255 and 1,593 valid values match | Two series with different definitions and base periods (Jan 1997 = 100, goods only; Jan 2006 = 100) are spliced. Not DXY; the 2020 boundary mixes in the series change |
| `BDI.csv` | Baltic Exchange, Baltic Dry Index ([official information](https://www.balticexchange.com/en/data-services/market-information0/dry-services.html)) | 551 of 552 common dates, 2007-01-02 to 2009-03-13, match a [third-party archive](https://raw.githubusercontent.com/ajoposor/Baltic-Dry-Index/master/Old_Data_Baltic_Dry_Index_1985-2009-03-13.csv); the exception is 2007-10-25 (10,994 local vs 10,984) | Download site and the period after 2009-03 unverified |
| `fertilizer.csv` | World Bank Commodity Price Data (Pink Sheet), urea, monthly, USD/metric ton ([product page](https://www.worldbank.org/en/research/commodity-markets)) | All 232 months match the [latest monthly file](https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx) at its 0.1-dollar display precision (max difference $0.05); 216 overlapping months match an [earlier higher-precision file](https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx) within $0.005 | Urea price, not a composite fertilizer index; download path (direct or redistributed) unverified |
| `corn_stock.csv` | USDA ERS, [Feed Grains Database](https://ers.usda.gov/data-products/feed-grains-database) / Yearbook | 79,440 of 79,641 rows key-match the [latest official CSV](https://www.ers.usda.gov/media/5766/feed-grains-yearbook-tables-all-years.csv?v=71628); 74,801 of those match within 1e-7, 4,639 differ, 201 have no matching key | Product identified, but not the same vintage; differences are not assumed to be revisions |
| `bean_stock.csv` | USDA ERS, [Oil Crops Yearbook](https://www.ers.usda.gov/data-products/oil-crops-yearbook) | SHA-256 identical to the [official CSV](https://www.ers.usda.gov/media/5218/all-tables-oil-crops-yearbook.csv?v=20641) (30,935 rows) | — |
| `ethanol_corn.csv` | USDA ERS, [U.S. Bioenergy Statistics](https://www.ers.usda.gov/data-products/us-bioenergy-statistics) | Columns and table numbers/titles match the documentation; 12,458 of 15,129 rows key-match the [latest official CSV](https://www.ers.usda.gov/media/6478/us-bioenergy-statistics.csv?v=72839), 6,494 within 1e-7, 11,222 after integer rounding | Content differences remain beyond precision; the official page states that table 5 was dropped from the 2026-10-20 release |
| `Fuel_alcohol_use_data.csv` | Extracted from table 5 of `ethanol_corn.csv` (Corn; "Fuel alcohol use" and "Fuel alcohol share of total use") | All 74 usage rows and 74 share rows match the local source | Quarters are corn marketing-year quarters (Q1 = Sep–Nov, Q2 = Dec–Feb, Q3 = Mar–May, Q4 = Jun–Aug), not calendar quarters; the earlier calendar-quarter alignment needs review |
| Crop condition files (state level) | USDA NASS [Quick Stats](https://quickstats.nass.usda.gov/), Crop Progress: corn and soybean condition, PCT GOOD / PCT EXCELLENT | Spot check, Illinois week ending 2025-05-25: corn 55 + 12 = 67, soybean 53 + 9 = 62, matching the [official report](https://www.nass.usda.gov/Statistics_by_State/Illinois/Publications/Crop_Progress_%26_Condition/2025/20250527-IL-Crop-Progress.pdf) | Full re-download through the Quick Stats API (key required) not done |
| `CORN_SOY_Condition_Index.csv` | Derived: PCT GOOD + PCT EXCELLENT per week ending × state × commodity | All 4,761 rows match a recomputation from the local state files | Internal consistency only, not a full external re-check |

## What this means for the results

- **Trading inputs:** the selected strategy uses price history and the delayed drought index. The drought input is fully verified; the price input is the open issue, which is why returns are reported as simulated NAV changes.
- **Exploratory inputs:** the spliced dollar index, the urea-only fertilizer price, marketing-year quarters, non-matching vintages and unknown release dates all support keeping these variables out of model selection and trading. Exploratory results should not be read as evidence about these variables' predictive value.
- **Publishing raw data:** redistribution terms have not been reviewed source by source, so no raw files are included in this repository.
