import streamlit as st
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockLatestQuoteRequest
import numpy as np
from scipy.stats import norm
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIG & BRANDING ---
st.set_page_config(page_title="Lucky Lab", page_icon="🧪", layout="wide")

# Custom CSS for a cleaner "Lab" look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    h1 { color: #1e3a8a; font-family: 'Helvetica Neue', sans-serif; }
    </style>
    """, unsafe_content_label=True)

st.title("🧪 Lucky Lab: Options Quant")

# --- 2. KEYS ---
try:
    API_KEY = st.secrets["ALPACA_KEY"]
    SECRET_KEY = st.secrets["ALPACA_SECRET"]
    stock_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    opt_client = OptionHistoricalDataClient(API_KEY, SECRET_KEY)
except:
    st.warning("⚠️ Lucky Lab is offline. Please add your ALPACA_KEY and ALPACA_SECRET to Streamlit Secrets.")
    st.stop()

# --- 3. TABS ---
tab1, tab2 = st.tabs(["🔍 Strategy Optimizer", "📓 Trade Journal"])

with tab1:
    st.subheader("Naked Put Scanner (90% Prob. Safety)")
    c1, c2 = st.columns([1, 3])
    ticker = c1.text_input("Enter Ticker", value="SPY").upper()
    
    if c1.button("🔬 Run Lab Analysis"):
        try:
            # Get Price
            price = stock_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=ticker))[ticker].ask_price
            st.write(f"**Current {ticker} Price:** `${price:.2f}`")

            # Logic for Nearest Friday
            expiry = datetime.now() + timedelta(days=(4 - datetime.now().weekday() + 7) % 7 or 7)
            
            # Fetch Chain
            chain = opt_client.get_option_chain(OptionChainRequest(underlying_symbol=ticker, expiration_date=expiry.date()))
            
            results = []
            for strike, data in chain.items():
                if data.type == 'put' and data.strike < price:
                    # Quick Safety Proxy (Black-Scholes Delta approx)
                    iv = data.implied_volatility or 0.20
                    t = max((expiry.date() - datetime.now().date()).days, 1) / 365
                    d2 = (np.log(price/data.strike) + (0.045 - 0.5*iv**2)*t) / (iv*np.sqrt(t))
                    prob_otm = norm.cdf(d2) * 100
                    
                    if prob_otm > 90 and (data.volume or 0) > 5:
                        premium = (data.bid_price + data.ask_price) / 2
                        margin = max((0.20*price - (price-data.strike) + premium)*100, (0.10*data.strike)*100)
                        ann_roc = (premium*100/margin) * (365/max(t*365, 1)) * 100
                        
                        results.append({
                            "Strike": f"${data.strike}", "Safety": f"{prob_otm:.1f}%",
                            "Premium": f"${premium:.2f}", "Ann. ROC": f"{ann_roc:.1f}%",
                            "Margin Req": f"${margin:.0f}"
                        })

            if results:
                st.table(pd.DataFrame(results).sort_values("Ann. ROC", ascending=False).head(5))
            else:
                st.info("No strikes match the 90% safety threshold today.")
        except Exception as e:
            st.error(f"Analysis failed: {e}")

with tab2:
    st.subheader("The Ledger")
    if 'journal' not in st.session_state:
        st.session_state.journal = pd.DataFrame(columns=["Date", "Ticker", "Strike", "Premium", "Qty", "P/L ($)"])

    edited = st.data_editor(st.session_state.journal, num_rows="dynamic", use_container_width=True)
    st.session_state.journal = edited

    if not edited.empty:
        df = edited.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Profit", f"${df['P/L ($)'].sum():,.2f}")
        m2.metric("Weekly", f"${df[df['Date'] > (datetime.now()-timedelta(days=7))]['P/L ($)'].sum():,.2f}")
        m3.metric("Monthly", f"${df[df['Date'].dt.month == datetime.now().month]['P/L ($)'].sum():,.2f}")
