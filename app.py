import streamlit as st
import requests
import numpy as np
from scipy.stats import norm
from datetime import datetime

# --- CONFIG ---
# PASTE YOUR KEY HERE
API_KEY = "d6ndtshr01qodk5vcbt0d6ndtshr01qodk5vcbtg"

st.set_page_config(page_title="Weekly Put Dash", layout="centered")

# --- Title & Sidebar ---
st.title("⚡ Weekly Short Put Dash")
st.markdown("Automated 1-Week Probability Analysis")

ticker = st.sidebar.text_input("Enter Ticker (e.g. TSLA, NVDA)", value="SPY").upper()

# --- 1. Fetch Price from Finnhub ---
@st.cache_data(ttl=60)
def fetch_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={API_KEY}"
        data = requests.get(url).json()
        return float(data['c']) # 'c' is the current price
    except Exception as e:
        return None

# --- 2. Logic & UI ---
current_price = fetch_price(ticker)

if current_price and current_price > 0:
    st.subheader(f"{ticker} Current Price: **${current_price:.2f}**")
    
    # We define the 2 most common "Weekly" targets: 2% and 5% OTM
    strikes = [round(current_price * 0.98, 1), round(current_price * 0.95, 1)]
    
    st.write("### 🎯 Top 2 Weekly Targets")
    st.divider()

    for K in strikes:
        # Probability Modeling (Standard Weekly Parameters)
        # Assuming 7 days to expiry (T), 4.5% rate (r), and 30% Volatility (sigma)
        T = 7 / 365
        r = 0.045
        sigma = 0.30 
        
        # Black-Scholes for Probability of OTM (Profit)
        d2 = (np.log(current_price / K) + (r - 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        prob_otm = norm.cdf(d2) * 100
        
        # Estimated Premium (Based on intrinsic distance)
        est_premium = (current_price - K) * 0.45 if current_price > K else 0.05
        
        # Layout
        with st.container():
            col1, col2, col3 = st.columns(3)
            col1.metric("Strike Price", f"${K}")
            col2.metric("Est. Premium", f"${est_premium:.2f}")
            col3.metric("Prob. of Profit", f"{prob_otm:.1f}%")
            
            st.progress(int(prob_otm))
            st.caption(f"Breakeven: ${K - est_premium:.2f} | Capital Required: ${K*100:,.0f}")
            st.divider()

else:
    st.error("⚠️ Error: Could not connect to Finnhub.")
    st.info("Check your API Key in the code and make sure the ticker is valid.")

st.caption("Data: Finnhub.io | Analysis: Black-Scholes Probability Model")
