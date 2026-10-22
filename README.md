# Support & Resistance – AB Formula (Streamlit)

Daily chart for any stock, index or mutual fund with up to 3 support and 3 resistance
horizontal lines, recalculated on the 1st trading day of every month.

## Formula
- Pie Factor = (previous month's closing price ÷ 3.14) ÷ 10
- R1/R2/R3 = close + 1/2/3 × Pie Factor
- S1/S2/S3 = close − 1/2/3 × Pie Factor

## Run locally
```
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (GitHub + Streamlit Community Cloud)
1. Create a new GitHub repo and push `app.py`, `requirements.txt`, `README.md`.
2. Go to share.streamlit.io, click **New app**, pick the repo, branch `main`, main file `app.py`.
3. Deploy.

## Symbols (Yahoo Finance)
- NSE stocks: `RELIANCE.NS`, BSE: `500325.BO`
- Indices: `^NSEI`, `^NSEBANK`, `^BSESN`
- Mutual funds: Yahoo fund code, e.g. `0P0000XVAA.BO` (NAV-only, shown as a line chart)
