import streamlit as st
import numpy as np
from scipy.stats import norm
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="Weekly Put Picker", layout="centered")

st.title("⚡ Weekly Short Put Dash")
st.write("Fastest view of the 2 safest OTM strikes for this week.")

# --- Sidebar: Ticker Search ---
ticker_symbol = st.sidebar.text_input("Enter Ticker", value="SPY").upper()

@st.cache_data(ttl=300)
def get_weekly_data(symbol):
    try:
        t = yf.Ticker(symbol)
        price = t.fast_info['last_price']
        # Get only the nearest expiration
        nearest_exp = t.options[0] 
        opts = t.option_chain(nearest_exp)
        puts = opts.puts
        
        # Filter for the 2 strikes just below current price (OTM)
        otm_puts = puts[puts['strike'] <= price].sort_values(by='strike', ascending=False).head(2)
        return t, price, nearest_exp, otm_puts
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None, None, None, None

ticker_obj, live_price, exp_date, strike_df = get_weekly_data(ticker_symbol)

if ticker_obj and not strike_df.empty:
    st.subheader(f"{ticker_symbol} @ ${live_price:.2f}")
    st.info(f"📅 **Expires:** {exp_date} (This Week)")

    # --- Display Top 2 Strikes ---
    for index, row in strike_df.iterrows():
        K = row['strike']
        iv = row['impliedVolatility']
        premium = (row['bid'] + row['ask']) / 2 if row['bid'] > 0 else row['lastPrice']
        
        # Quick Math for Probability
        days_to_go = (datetime.strptime(exp_date, '%Y-%m-%d') - datetime.now()).days
        T = max(days_to_go, 1) / 365.0
        r = 0.045
        d2 = (np.log(live_price / K) + (r - 0.5 * iv**2) * T) / (iv * np.sqrt(T))
        prob_otm = norm.cdf(d2) * 100
        
        # Layout for each strike
        with st.container():
            col1, col2, col3 = st.columns([1, 1, 1])
            col1.metric(f"Strike Price", f"${K}")
            col2.metric("Premium (Mid)", f"${premium:.2f}")
            col3.metric("Prob. Worthless", f"{prob_otm:.1f}%")
            
            # Simple Risk Bar
            st.progress(int(prob_otm))
            st.markdown(f"**IV:** {iv*100:.1f}% | **Breakeven:** ${K-premium:.2f}")
            st.divider()

else:
    st.warning("Could not find weekly options for this ticker. Try a major stock like AAPL or TSLA.")

# --- Quick Calculation Table ---
if not strike_df.empty:
    st.subheader("Comparison Table")
    summary = strike_df[['strike', 'lastPrice', 'impliedVolatility']].copy()
    summary.columns = ['Strike', 'Last Price', 'Live IV']
    st.table(summary)

st.caption("Data provided via yfinance. Probability calculated using Black-Scholes.")
