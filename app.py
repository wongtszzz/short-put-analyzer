import streamlit as st
from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import OptionChainRequest, StockLatestQuoteRequest, OptionBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame
import numpy as np
from scipy.stats import norm
import pandas as pd
from datetime import datetime, timedelta

# --- 1. CONFIG & BRANDING ---
st.set_page_config(page_title="Lucky Lab", page_icon="🧪", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e1e4e8; }
    h1 { color: #1e3a8a; font-family: 'Helvetica Neue', sans-serif; }
    [data-testid="stExpander"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e1e4e8; }
    </style>
""", unsafe_allow_html=True)

st.title("🧪 Lucky Lab: Options Quant")

# --- 2. AUTHENTICATION & CLIENTS ---
@st.cache_resource
def get_clients():
    try:
        key = st.secrets["ALPACA_KEY"]
        secret = st.secrets["ALPACA_SECRET"]
        return StockHistoricalDataClient(key, secret), OptionHistoricalDataClient(key, secret)
    except:
        return None, None

stock_client, opt_client = get_clients()

if not stock_client:
    st.error("⚠️ Alpaca Keys Missing in Streamlit Secrets.")
    st.stop()

# --- 3. CREATE TABS ---
tab1, tab2 = st.tabs(["🔍 Strategy Optimizer", "📓 Lucky Ledger"])

# --- TAB 1: STRATEGY OPTIMIZER ---
with tab1:
    st.subheader("Naked Put Scanner")
    col_a, col_b, col_c = st.columns([1, 1, 1])
    ticker_scan = col_a.text_input("Ticker Symbol", value="SPY", key="scan_ticker_input").upper()
    safety_threshold = col_b.slider("Minimum Safety %", 70, 99, 90)
    min_vol = col_c.number_input("Min Volume", value=0)

    if st.button("🔬 Run Lab Analysis"):
        with st.spinner(f"Analyzing {ticker_scan}..."):
            try:
                price_data = stock_client.get_stock_latest_quote(StockLatestQuoteRequest(symbol_or_symbols=ticker_scan, feed=DataFeed.IEX))
                current_price = price_data[ticker_scan].ask_price
                st.metric(f"{ticker_scan} Live Ask", f"${current_price:.2f}")

                today = datetime.now()
                expiry = today + timedelta(days=(4 - today.weekday() + 7) % 7 or 7)
                chain = opt_client.get_option_chain(OptionChainRequest(underlying_symbol=ticker_scan, expiration_date=expiry.date()))
                
                results = []
                for symbol, data in chain.items():
                    strike_from_sym = float(symbol[-8:]) / 1000
                    if "P" in symbol and strike_from_sym < current_price:
                        iv = getattr(data, 'implied_volatility', 0.18) or 0.18
                        t_years = max((expiry - today).days, 1) / 365
                        d2 = (np.log(current_price/strike_from_sym) + (0.042 - 0.5*iv**2)*t_years) / (iv*np.sqrt(t_years))
                        prob_otm = norm.cdf(d2) * 100
                        
                        if prob_otm >= safety_threshold and (getattr(data, 'volume', 0) or 0) >= min_vol:
                            mid = (data.bid_price + data.ask_price) / 2
                            results.append({
                                "Strike": round(strike_from_sym, 1),
                                "Safety %": round(prob_otm, 1),
                                "Premium": f"${mid:.2f}",
                                "Volume": getattr(data, 'volume', 0)
                            })
                st.dataframe(pd.DataFrame(results).sort_values("Strike", ascending=False), use_container_width=True)
            except Exception as e:
                st.error(f"Scanner Error: {e}")

# --- TAB 2: LUCKY LEDGER ---
with tab2:
    st.subheader("📓 The Lucky Ledger")

    # 2026 IBKR TIERED CONSTANTS
    OCC_FEE = 0.025
    ORF_FEE = 0.023
    MIN_ORDER_FEE = 1.00

    desired_cols = ["Ticker", "Type", "Strike", "Expiry", "Premium", "Qty", "Commission", "Total Profit"]
    
    if 'journal_data' not in st.session_state:
        st.session_state.journal_data = pd.DataFrame(columns=desired_cols)

    # 1. TOP METRICS
    profits = pd.to_numeric(st.session_state.journal_data["Total Profit"], errors='coerce').fillna(0)
    st.metric("Net Profit (After Fees)", f"${profits.sum():,.2f}")
    st.divider()

    # 2. ENTRY FORM
    with st.expander("➕ Log New Trade", expanded=True):
        c1, c2, c3 = st.columns(3)
        t_input = c1.text_input("Ticker", value="SPY").upper()
        strat = c2.selectbox("Strategy", ["Short Put", "Short Call"])
        qty = c3.number_input("Qty", min_value=1, value=1)

        c4, c5 = st.columns(2)
        exp_date = c4.date_input("Expiry Date", value=datetime.now().date())
        strike = c5.number_input("Strike", value=0.0, step=0.5)
        
        if st.button("🚀 Fetch & Commit"):
            try:
                # 1. Price Logic
                flag = "P" if strat == "Short Put" else "C"
                sym = f"{t_input}{exp_date.strftime('%y%m%d')}{flag}{int(strike*1000):08d}"
                
                # Fetching Mid-Price
                chain = opt_client.get_option_chain(OptionChainRequest(underlying_symbol=t_input, expiration_date=exp_date))
                if sym not in chain:
                    st.error(f"Contract {sym} not found.")
                else:
                    data = chain[sym]
                    mid_price = (data.bid_price + data.ask_price) / 2
                    if mid_price == 0: mid_price = getattr(data, 'last_price', 0.01)
                    
                    # 2. Commission Logic (2026 Tiered)
                    if mid_price >= 0.10: base = 0.65
                    elif mid_price >= 0.05: base = 0.50
                    else: base = 0.25
                    
                    total_per_contract = base + OCC_FEE + ORF_FEE
                    order_comm = max(MIN_ORDER_FEE, total_per_contract * qty)
                    
                    # 3. Calculations
                    cash_premium = round(mid_price * 100, 2)
                    net_profit = (cash_premium * qty) - order_comm
                    
                    new_row = {
                        "Ticker": t_input, "Type": strat, "Strike": strike, 
                        "Expiry": exp_date.strftime("%Y-%m-%d"),
                        "Premium": cash_premium, "Qty": int(qty),
                        "Commission": round(order_comm, 2),
                        "Total Profit": round(net_profit, 2)
                    }
                    st.session_state.journal_data = pd.concat([st.session_state.journal_data, pd.DataFrame([new_row])], ignore_index=True)
                    st.rerun()
            except Exception as e:
                st.error(f"Execution Error: {e}")

    # 3. HISTORY
    st.write("### Trade History")
    st.session_state.journal_data = st.data_editor(st.session_state.journal_data, num_rows="dynamic", use_container_width=True)

    if st.button("🗑️ Reset Ledger"):
        st.session_state.journal_data = pd.DataFrame(columns=desired_cols)
        st.rerun()
