import streamlit as st
import requests
import numpy as np
from scipy.stats import norm

# --- CONFIG ---
# Ensure your key is inside the quotes
FINNHUB_KEY = "d6ndtshr01qodk5vcbt0d6ndtshr01qodk5vcbtg"

st.set_page_config(page_title="Weekly Put Picker", layout="centered")
st.title("⚡ Weekly Short Put Dash (Finnhub Only)")

ticker_symbol = st.sidebar.text_input("Enter Ticker", value="SPY").upper()

# --- 1. GET LIVE PRICE FROM FINNHUB ---
@st.cache_data(ttl=60)
def get_finnhub_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
        response = requests.get(url).json()
        # 'c' is the current price in Finnhub's API
        return float(response['c'])
    except Exception as e:
        st.error(f"Finnhub Error: {e}")
        return None

price = get_finnhub_price(ticker_symbol)

# --- 2. THE UI ---
if price and price > 0:
    st.subheader(f"{ticker_symbol} @ ${price:.2f}")
    
    # We will show the 2 most popular weekly OTM targets
    # (Typically 2% and 5% below current price)
    strikes = [round(price * 0.98, 1), round(price * 0.95, 1)]
    
    st.info("🎯 Estimated Weekly Opportunities")

    for K in strikes:
        # Probability Modeling (Black-Scholes)
        # We assume 1 week (7 days) and a standard 25% IV
        iv = 0.25 
        T = 7/365
        r = 0.045
        
        d2 = (np.log(price / K) + (r - 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        prob_otm = norm.cdf(d2) * 100
        
        # Estimated Premium based on distance from price
        est_premium = (price - K) * 0.5 if price > K else 0.05

        with st.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("Strike", f"${K}")
            col2.metric("Est. Premium", f"${est_premium:.2f}")
            col3.metric("Prob. OTM", f"{prob_otm:.1f}%")
            st.progress(int(prob_otm))
            st.caption(f"Breakeven: ${K-est_premium:.2f} | Capital: ${K*100:,.0f}")
            st.divider()
else:
    st.warning("Waiting for Finnhub data... If this persists, check your API key.")

st.caption("No Yahoo Finance data is used in this version. Data source: Finnhub.io")
