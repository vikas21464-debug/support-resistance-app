import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Support & Resistance (AB Formula)",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Force a clean light look with dark, readable text everywhere
st.markdown(
    """
    <style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
    .stApp, [data-testid="stHeader"] { background-color: #ffffff; }
    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label, .stApp li,
    .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"] *,
    .stApp [data-testid="stMetricLabel"] *, .stApp [data-testid="stMetricValue"] *,
    .stApp [data-testid="stCaptionContainer"], .stApp summary, .stApp summary * {
        color: #111111 !important;
    }
    .stApp input, .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="input"] {
        background-color: #f3f4f6 !important; color: #111111 !important;
    }
    .stApp [data-baseweb="select"] * { color: #111111 !important; }
    div[data-baseweb="popover"] li, div[data-baseweb="popover"] ul {
        background-color: #ffffff !important; color: #111111 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 Support & Resistance")
st.caption(
    "Monthly support and resistance levels (R1–R3, S1–S3) drawn on the daily chart "
    "of any stock, index or mutual fund. Developed by Vikas Dhiman."
)


# ---------------------------------------------------------------- data helpers
@st.cache_data(ttl=3600, show_spinner="Downloading price data…")
def load_data(sym: str, start: dt.date) -> pd.DataFrame:
    df = yf.download(sym, start=start, auto_adjust=False, progress=False)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def compute_monthly_levels(df: pd.DataFrame, pi_value: float, divisor: float) -> pd.DataFrame:
    """One row per month: prev close, pie factor, R1-R3, S1-S3,
    effective from that month's first trading day."""
    month = df.index.to_period("M")
    month_close = df["Close"].groupby(month).last()
    first_day = df.index.to_series().groupby(month).min()
    last_day = df.index.to_series().groupby(month).max()

    out = pd.DataFrame({"start": first_day, "end": last_day})
    out["prev_close"] = month_close.shift(1)
    out = out.dropna(subset=["prev_close"])
    out["pie"] = out["prev_close"] / pi_value / divisor
    for i in (1, 2, 3):
        out[f"R{i}"] = out["prev_close"] + i * out["pie"]
        out[f"S{i}"] = out["prev_close"] - i * out["pie"]
    return out


# ---------------------------------------------------------------- menu (top of page)
m1, m2, m3 = st.columns([2, 1, 1])
symbol = m1.text_input(
    "Stock / Index / Mutual fund symbol",
    value="^NSEI",
    help="Yahoo Finance symbol. Examples: RELIANCE.NS, TCS.NS, ^NSEI, ^NSEBANK, "
    "^BSESN, AAPL. Mutual funds: Yahoo code such as 0P0000XVAA.BO",
).strip()
years_history = m2.selectbox("History to load", [1, 2, 3, 5, 10, 15], index=3,
                             format_func=lambda y: f"{y} year{'s' if y > 1 else ''}")
context_months = m3.selectbox("Months before selected month", [0, 1, 2, 3, 6, 12], index=2)

with st.expander("Formula settings"):
    f1, f2 = st.columns(2)
    pi_value = f1.number_input("First divisor", min_value=0.01, value=3.14,
                               step=0.01, format="%.2f")
    divisor = f2.number_input("Second divisor", min_value=1.0, value=10.0, step=1.0)
    show_labels = st.checkbox("Show price labels on lines", value=True)

if not symbol:
    st.stop()

today = dt.date.today()
start = (pd.Timestamp(today) - pd.DateOffset(years=years_history)).date()
data = load_data(symbol, start)

if data.empty:
    st.error(f"No data found for '{symbol}'. Check the Yahoo Finance symbol.")
    st.stop()

levels = compute_monthly_levels(data, pi_value, divisor)
if levels.empty:
    st.warning("Not enough history to compute levels.")
    st.stop()

month_labels = [p.strftime("%B %Y") for p in levels.index]  # oldest -> newest
selected_label = st.selectbox(
    "Select month (lines on the chart follow this month)",
    options=month_labels[::-1],  # newest first
    index=0,
)
sel_period = levels.index[month_labels.index(selected_label)]
sel = levels.loc[sel_period]

win_start = sel["start"] - pd.DateOffset(months=context_months)
view = data[(data.index >= win_start) & (data.index <= sel["end"])]

# ---------------------------------------------------------------- chart (price + S/R lines only)
fig = go.Figure()
has_ohlc = {"Open", "High", "Low"}.issubset(view.columns) and view["High"].notna().any()
if has_ohlc:
    fig.add_trace(
        go.Candlestick(
            x=view.index, open=view["Open"], high=view["High"],
            low=view["Low"], close=view["Close"], name="Price",
            increasing_line_color="#2ca02c", decreasing_line_color="#d62728",
            showlegend=False,
        )
    )
else:  # mutual funds usually only have NAV
    fig.add_trace(go.Scatter(x=view.index, y=view["Close"], mode="lines",
                             line=dict(color="#1f77b4"), showlegend=False))

COLORS = {"R": "#d62728", "S": "#2ca02c"}
x0, x1 = view.index.min(), view.index.max()

for kind in ("R", "S"):
    for i in (1, 2, 3):
        name = f"{kind}{i}"
        y = sel[name]
        fig.add_shape(
            type="line", x0=x0, x1=x1, y0=y, y1=y,
            line=dict(color=COLORS[kind], width=1.6),
        )
        if show_labels:
            fig.add_annotation(
                x=x1, y=y, text=f"{name}: {y:,.2f}", showarrow=False,
                xanchor="left", font=dict(color=COLORS[kind], size=12),
            )

fig.update_layout(
    template="plotly_white",
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    font=dict(color="#111111"),
    height=700, xaxis_rangeslider_visible=False,
    margin=dict(l=10, r=130, t=40, b=10),
    title=f"{symbol} – Daily chart | Levels for {selected_label}",
    hovermode="x",
)
# remove every extra line (grid, axis, zero and spike lines); keep only S/R lines
fig.update_xaxes(
    showgrid=False, zeroline=False, showline=False, showspikes=False,
    tickfont=dict(color="#000000", size=13, family="Arial Black, Arial, sans-serif"),
    tickformat="%d %b %Y",
    ticks="",
)
fig.update_yaxes(
    showgrid=False, zeroline=False, showline=False, showspikes=False,
    tickfont=dict(color="#000000", size=12),
)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------- level table
last_price = view["Close"].iloc[-1]
st.subheader(f"Levels for {selected_label} (from {sel['start']:%d %b %Y})")
c1, c2, c3 = st.columns(3)
c1.metric("Previous month close", f"{sel['prev_close']:,.2f}")
c2.metric("Pie Factor", f"{sel['pie']:,.2f}")
c3.metric(f"Close on {view.index[-1]:%d %b %Y}", f"{last_price:,.2f}")

lv = pd.DataFrame(
    {
        "Level": ["R3", "R2", "R1", "S1", "S2", "S3"],
        "Price": [sel["R3"], sel["R2"], sel["R1"], sel["S1"], sel["S2"], sel["S3"]],
    }
)
lv["Distance from last price %"] = (lv["Price"] / last_price - 1) * 100
st.dataframe(
    lv.style.format({"Price": "{:,.2f}", "Distance from last price %": "{:+.2f}%"}),
    hide_index=True, use_container_width=True,
)

with st.expander("Formula"):
    st.markdown(
        """
**On the 1st trading day of each month**

- Pie Factor = (Previous month close ÷ 3.14) ÷ 10
- R1 = Close + 1 × Pie, R2 = Close + 2 × Pie, R3 = Close + 3 × Pie
- S1 = Close − 1 × Pie, S2 = Close − 2 × Pie, S3 = Close − 3 × Pie

Levels stay fixed for the whole month.
"""
    )
st.caption("For educational purposes only. Not investment advice.")
