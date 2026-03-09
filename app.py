import streamlit as st
import numpy as np
from scipy.stats import norm
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="Weekly Put Picker", layout="centered")

st.title("⚡ Weekly Short Put Dash")

# --- Sidebar: Ticker Search ---
ticker_symbol = st.sidebar.text_input("Enter Ticker", value="SPY").upper()

# --- FIX: Custom Header to bypass Rate Limiting ---
@st.cache_data(ttl=600) # Increased cache to 10 mins to reduce requests
def get_weekly_data(symbol):
    try:
        # We use a session with a 'User-Agent' header to look like a browser
        import requests
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        
        t = yf.Ticker(symbol, session=session)
        
        # Check if we actually got data back
        if not t.options:
            return None, None, "No Options Found", None
            
        price = t.fast_info['last_price']
        nearest_exp = t.options[0] 
        opts = t.option_chain(nearest_exp)
        puts = opts.puts
        
        # Filter for 2 strikes just below current price
        otm_puts = puts[puts['strike'] <= price].sort_values(by='strike', ascending=False).head(2)
        return t, price, nearest_exp, otm_puts
    except Exception as e:
        return None, None, f"Error: {str(e)}", None

# Run the fetcher
ticker_obj, live_price, exp_date, strike_df = get_weekly_data(ticker_symbol)

# --- Safety Rail: Check if data exists before building the UI ---
if ticker_obj is None or live_price is None:
    st.error("📉 **Yahoo Finance is currently rate-limiting this app.**")
    st.info("Wait 60 seconds and try again, or try a different ticker. This happens because many users share the same server IP.")
    if st.button("🔄 Try Refreshing Now"):
        st.rerun()
elif strike_df is not None and not strike_df.empty:
    st.subheader(f"{ticker_symbol} @ ${live_price:.2f}")
    st.info(f"📅 **Expires:** {exp_date} (Nearest)")

    for index, row in strike_df.iterrows():
        K = row['strike']
        iv = row['impliedVolatility']
        # Fallback if bid/ask is missing
        premium = (row['bid'] + row['ask']) / 2 if row['bid'] > 0 else row['lastPrice']
        
        # Days to expiry math
        try:
            days_to_go = (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days
            T = max(days_to_go, 1) / 365.0
            r = 0.045
            d2 = (np.log(live_price / K) + (r - 0.5 * iv**2) * T) / (iv * np.sqrt(T))
            prob_otm = norm.cdf(d2) * 100
        except:
            prob_otm = 0

        with st.container():
            col1, col2, col3 = st.columns([1, 1, 1])
            col1.metric("Strike", f"${K}")
            col2.metric("Premium", f"${premium:.2f}")
            col3.metric("Prob. OTM", f"{prob_otm:.1f}%")
            st.progress(min(max(int(prob_otm), 0), 100))
            st.caption(f"IV: {iv*100:.1f}% | Breakeven: ${K-premium:.2f}")
            st.divider()
else:
    st.warning("No OTM put data found for this week.")
