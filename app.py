import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm
import yfinance as yf

# --- Page Config ---
st.set_page_config(page_title="Short Put Pro", layout="wide")

st.title("📈 Short Put Analyzer (Live Data)")

# --- Sidebar: Live Market Data ---
st.sidebar.header("1. Search Market")
ticker_input = st.sidebar.text_input("Enter Ticker (e.g., TSLA, AAPL, SPY)", value="SPY").upper()

@st.cache_data(ttl=300) # Refreshes every 5 minutes
def get_stock_data(symbol):
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info['last_price']
        name = ticker.info.get('longName', symbol)
        return price, name
    except:
        return 100.0, "Unknown"

live_price, co_name = get_stock_data(ticker_input)
st.sidebar.subheader(f"{co_name}")
st.sidebar.write(f"Current Price: **${live_price:.2f}**")

# --- Sidebar: Trade Inputs ---
st.sidebar.header("2. Trade Parameters")
S = st.sidebar.number_input("Underlying Price ($)", value=float(live_price))
K = st.sidebar.number_input("Strike Price ($)", value=float(live_price * 0.95))
premium = st.sidebar.number_input("Premium Received ($)", value=1.50)
T_days = st.sidebar.number_input("Days to Expiry", value=30, min_value=1)
iv_input = st.sidebar.slider("Implied Volatility (%)", 10.0, 150.0, 30.0)

# --- Math Logic (Black-Scholes) ---
r = 0.045 # 4.5% Risk-free rate
sigma = iv_input / 100
T = T_days / 365.0

d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
d2 = d1 - sigma * np.sqrt(T)

# Greeks & Metrics
prob_profit = norm.cdf(d2) * 100
breakeven = K - premium
delta = -(norm.cdf(d1) - 1)
# Theta (Daily)
theta = -((-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365)

# --- Dashboard Layout ---
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Prob. of Profit", f"{prob_profit:.1f}%")
m2.metric("Breakeven", f"${breakeven:.2f}")
m3.metric("Delta", f"{delta:.3f}")
m4.metric("Daily Theta (Decay)", f"${theta*100:.2f}")

# --- Risk Table ---
st.subheader("What if the stock moves tomorrow?")
st.write("Estimated P&L based on price swings:")
shocks = [-10, -5, -2, 0, 2, 5, 10]
cols = st.columns(len(shocks))

for i, s in enumerate(shocks):
    price_change = S * (1 + s/100)
    pnl = (price_change - S) * delta * 100 # Multiplied by 100 for 1 contract
    color = "inverse" if pnl < 0 else "normal"
    cols[i].metric(f"{s}% Move", f"${price_change:.1f}", f"${pnl:.0f}", delta_color=color)

# --- Payoff Chart ---
st.divider()
x = np.linspace(S * 0.8, S * 1.2, 100)
y = [ (premium - max(0, K - val)) * 100 for val in x]

fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(x, y, color='#00FF00', linewidth=2)
ax.axhline(0, color='white', alpha=0.3)
ax.axvline(S, color='yellow', linestyle='--', label='Current Price')
ax.fill_between(x, y, 0, where=(np.array(y) > 0), facecolor='green', alpha=0.2)
ax.fill_between(x, y, 0, where=(np.array(y) < 0), facecolor='red', alpha=0.2)

ax.set_facecolor('#0E1117')
fig.patch.set_facecolor('#0E1117')
ax.tick_params(colors='white')
ax.set_xlabel("Stock Price at Expiration", color='white')
ax.set_ylabel("Profit / Loss ($)", color='white')
st.pyplot(fig)
