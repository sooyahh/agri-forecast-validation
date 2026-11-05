# Local input contract

Historical inputs are excluded from version control because provenance and redistribution terms remain unresolved.

| File | Required columns |
|---|---|
| corn_price.xlsx | Date, Value |
| soybean_price.xlsx | Date, Value |
| drought_data.csv | Name, MapDate, DSCI |
| final_features_for_DL (2).csv | Date, Corn_Condition, Soy_Condition, Corn_Stock_Ratio, Bean_Stock_Ratio, Fuel_alcohol_use, Percent, fertilizer_price($/mt), WTI_Price, BDI, Dollar_Index |

Price Date values are Excel serial days using origin 1899-12-30. MapDate is YYYYMMDD and represents a Tuesday. All other dates use ISO YYYY-MM-DD. The combined CSV supplies exploratory features whose release timestamps are unverified.

The source fingerprints and anomaly audit are recorded in the annual report. To use alternate datasets, preserve the schema and validate their dates and price definitions first. Full experiment scripts assume coverage of the documented training and validation years.
