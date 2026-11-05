# Local input contract

Historical inputs are excluded from version control because the price provider and the redistribution terms of each source remain unresolved. Producers, match checks and caveats for every input are in [the data source audit](../docs/data-sources.md).

| File | Required columns |
|---|---|
| corn_price.xlsx | Date, Value |
| soybean_price.xlsx | Date, Value |
| drought_data.csv | Name, MapDate, DSCI |
| exploratory_features.csv | Date, Corn_Condition, Soy_Condition, Corn_Stock_Ratio, Bean_Stock_Ratio, Fuel_alcohol_use, Percent, fertilizer_price($/mt), WTI_Price, BDI, Dollar_Index |

Price Date values are Excel serial days using origin 1899-12-30. MapDate is YYYYMMDD and represents a Tuesday. All other dates use ISO YYYY-MM-DD. The combined CSV supplies exploratory features whose release timestamps are unverified. Column notes from the audit:

- `fertilizer_price($/mt)` is the World Bank Pink Sheet **urea** price (monthly, USD/metric ton), not a composite fertilizer index.
- `Dollar_Index` splices two FRED series with different definitions and base periods (DTWEXB for 2007–2019, DTWEXBGS from 2020). It is not DXY, and the 2020 boundary includes the series change.
- `Fuel_alcohol_use` and `Percent` come from USDA ERS quarterly data in corn **marketing-year** quarters (Q1 = Sep–Nov, Q2 = Dec–Feb, Q3 = Mar–May, Q4 = Jun–Aug); the coursework preprocessing aligned them as calendar quarters.
- `WTI_Price` is the EIA WTI Cushing spot price (FRED DCOILWTICO), not a futures price.

The source fingerprints and anomaly audit are recorded in the annual report. To use alternate datasets, preserve the schema and validate their dates and price definitions first. Full experiment scripts assume coverage of the documented training and validation years.
