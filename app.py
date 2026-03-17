import streamlit as st
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
import numpy as np
from scipy.stats import norm
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIG & BRANDING ---
st.set_page_config(page_title="Lucky Lab", page_icon="🧪", layout="wide")

st.html("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; }
    h1 { color: #1e3a8a; font-family: 'Helvetica Neue', sans-serif; }
    </style>
""")

st.title("🧪 Lucky Lab: Options Quant")

# --- 2. AUTHENTICATION ---
try:
    API_KEY = st.secrets["ALPACA_KEY"]
    SECRET_KEY = st.secrets["ALPACA_SECRET"]
    stock_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)
    opt_client = OptionHistoricalDataClient(API_KEY, SECRET_KEY)
except Exception as e:
    st.error("⚠️ Lucky Lab Keys Missing. Add ALPACA_KEY and ALPACA_SECRET to Streamlit Secrets.")
    st.stop()

# --- 3. TABS ---
tab1, tab2 = st.tabs(["🔍 Strategy Optimizer", "📓 Trade Journal"])

with tab1:
    st.subheader("Naked Put Scanner")
    
    # User Inputs
    col_a, col_b, col_c = st.columns([1, 1, 1])
    ticker = col_a.text_input("Ticker Symbol", value="SPY").upper()
    safety_threshold = col_b.slider("Minimum Safety %", 70, 99, 90)
    min_vol = col_c.number_input("Min Volume", value=0) # Set to 0 to see everything

    if st.button("🔬 Run Lab Analysis"):
        with st.spinner(f"Analyzing {ticker}..."):
            try:
                # 1. Get Live Price
                # Using DataFeed.IEX for free/paper users
                price_req = StockLatestQuoteRequest(symbol_or_symbols=ticker, feed=DataFeed.IEX)
                price_data = stock_client.get_stock_latest_quote(price_req)
                current_price = price_data[ticker].ask_price
                
                st.metric(f"{ticker} Live Ask", f"${current_price:.2f}")

                # 2. Get Nearest Friday Expiry
                today = datetime.now()
                days_to_fri = (4 - today.weekday() + 7) % 7 or 7
                expiry = today + timedelta(days=days_to_fri)
                
                # 3. Fetch Option Chain
                chain_req = OptionChainRequest(underlying_symbol=ticker, expiration_date=expiry.date())
                chain = opt_client.get_option_chain(chain_req)
                
                results = []
                # Common financial constants for 2026
                risk_free_rate = 0.042 
                t_years = max(days_to_fri, 1) / 365
                
                for strike, data in chain.items():
                    # Only look at Puts that are cheaper than current price (OTM)
                    if data.type == 'put' and data.strike < current_price:
                        
                        # Math: Probability of Profit (Safety)
                        iv = data.implied_volatility or 0.18 # Fallback IV
                        d2 = (np.log(current_price/data.strike) + (risk_free_rate - 0.5*iv**2)*t_years) / (iv*np.sqrt(t_years))
                        prob_otm = norm.cdf(d2) * 100
                        
                        # Filter based on your slider
                        if prob_otm >= safety_threshold and (data.volume or 0) >= min_vol:
                            mid_price = (data.bid_price + data.ask_price) / 2
                            
                            # Margin requirement estimate
                            m_req = max((0.20*current_price - (current_price-data.strike) + mid_price)*100, (0.10*data.strike)*100)
                            ann_roc = (mid_price*100/m_req) * (365/days_to_fri) * 100
                            
                            results.append({
                                "Strike": data.strike,
                                "Safety %": round(prob_otm, 1),
                                "Premium": f"${mid_price:.2f}",
                                "Ann. ROC %": round(ann_roc, 1),
                                "Volume": data.volume,
                                "Margin Req": int(m_req)
                            })

                if results:
                    df_res = pd.DataFrame(results).sort_values("Ann. ROC %", ascending=False)
                    st.write(f"### Top Picks for {expiry.date()}")
                    st.dataframe(df_res, use_container_width=True)
                else:
                    st.warning(f"No puts found for {ticker} at {safety_threshold}% safety. Try lowering the threshold or checking a more volatile stock like NVDA.")

            except Exception as e:
                st.error(f"Lab Error: {e}")

with tab2:
    st.subheader("The Ledger")
    # (Journal code remains same as previous)
    if 'journal' not in st.session_state:
        st.session_state.journal = pd.DataFrame(columns=["Date", "Ticker", "Strike", "Premium", "Qty", "P/L ($)"])
    edited = st.data_editor(st.session_state.journal, num_rows="dynamic", use_container_width=True)
    st.session_state.journal = edited
