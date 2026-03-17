import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io

# Seite konfigurieren
st.set_page_config(page_title="Quant-Backtester mit Excel-Export", layout="wide")

# --- 1. SEITENLEISTE ---
with st.sidebar:
    st.header("🔬 Strategie-Zentrale")
    symbols_str = st.text_input("Aktien (z.B. AAPL, NVDA, 600519.SS)", value="AAPL, NVDA")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("📏 EMA-System")
    ema_f = st.number_input("Kurze EMA", value=10)
    ema_m = st.number_input("Mittlere EMA (Stopp)", value=20)
    ema_l = st.number_input("Lange EMA", value=200)

    st.subheader("⏱️ Exit-Regeln")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Stopp nutzen", value=True)
    
    st.subheader("📊 Risiko-Filter")
    beta_lim = st.slider("Max. Erlaubtes Beta (US)", 0.5, 4.0, 1.5)
    v_rel = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    perf_3m_min = st.slider("3M Performance Min (%)", -50, 50, 0)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2021-01-01"))

# --- 2. BACKTEST-KERN ---
def run_full_backtest(symbol, df_all, mkt_close):
    try:
        if isinstance(df_all.columns, pd.MultiIndex):
            df = pd.DataFrame({'Close': df_all['Close'][symbol], 'Volume': df_all['Volume'][symbol]}).dropna()
        else:
            df = pd.DataFrame({'Close': df_all['Close'], 'Volume': df_all['Volume']}).dropna()
        
        if df.empty or len(df) < 200: return None

        df['EMA_F'] = df['Close'].ewm(span=ema_f, adjust=False).mean()
        df['EMA_M'] = df['Close'].ewm(span=ema_m, adjust=False).mean()
        df['EMA_L'] = df['Close'].ewm(span=ema_l, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
        
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        common_idx = ret.index.intersection(mkt_ret.index)
        if len(common_idx) > 60:
            rolling_cov = ret.loc[common_idx].rolling(60).cov(mkt_ret.loc[common_idx])
            rolling_var = mkt_ret.loc[common_idx].rolling(60).var()
            df['Beta'] = (rolling_cov / rolling_var).reindex(df.index, method='ffill')
        else:
            df['Beta'] = 0.0

        beta_condition = (df['Beta'] < beta_lim) | (df['Beta'] == 0)
        df['Trigger'] = ((df['Close'] > df['EMA_F']) & (df['EMA_F'] > df['EMA_M']) & 
                         (df['Close'] > df['EMA_L']) & (df['Rel_Vol'] > v_rel) & 
                         (df['Perf_3M'] > perf_3m_min) & beta_condition).astype(int)

        signals = np.zeros(len(df)); exit_reasons = [""] * len(df)
        in_pos = False; days = 0
        for i in range(len(df)):
            if in_pos:
                time_exit = days >= max_hold
                sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA_M'].iloc[i])
                if time_exit or sl_exit:
                    in_pos = False; days = 0
                    exit_reasons[i] = "Zeit" if time_exit else "EMA-Stopp"
                else:
                    signals[i] = 1; days += 1
            elif df['Trigger'].iloc[i] == 1:
                in_pos = True; signals[i] = 1; days = 1
        
        df['Signal'] = signals
        df['Exit_Reason'] = exit_reasons
        df['Strategy_Ret'] = (ret * pd.Series(signals, index=df.index).shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Ret']).cumprod()
        return df
    except: return None

# --- 3. HAUPTPROGRAMM ---
try:
    if symbols:
        with st.spinner('Daten werden verarbeitet...'):
            all_needed = list(set(symbols + ["^GSPC"]))
            data = yf.download(all_needed, start=start_date)
            
            if not data.empty:
                mkt_close = data['Close']["^GSPC"] if "^GSPC" in data['Close'] else yf.download("^GSPC", start=start_date)['Close']
                results_map = {}; ranking_data = []
                
                for s in symbols:
                    res_df = run_full_backtest(s, data, mkt_close)
                    if res_df is not None:
                        results_map[s] = res_df
                        ret_pct = (res_df['Cum_Strategy'].iloc[-1] - 1) * 100
                        ranking_data.append({"Aktie": s, "Rendite %": round(ret_pct, 2), "Endwert": round(res_df['Cum_Strategy'].iloc[-1], 3)})

                # CHART & RANKING
                st.title("🏆 Strategie-Arena")
                if results_map:
                    fig = go.Figure()
                    for s, res_df in results_map.items():
                        fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Cum_Strategy'], name=s))
                    st.plotly_chart(fig, use_container_width=True)

                    rank_df = pd.DataFrame(ranking_data).sort_values(by="Endwert", ascending=False)
                    st.table(rank_df)
                    
                    st.write("---")
                    selected_s = st.selectbox("Logbuch & Export für:", list(results_map.keys()))
                    d_df = results_map[selected_s]
                    
                    # LOGBUCH GENERIEREN
                    d_df['Entry'] = ((d_df['Signal'] == 1) & (d_df['Signal'].shift(1) == 0)).astype(int)
                    d_df['Exit'] = ((d_df['Signal'] == 0) & (d_df['Signal'].shift(1) == 1)).astype(int)
                    b_dates = d_df[d_df['Entry'] == 1].index
                    e_dates = d_df[d_df['Exit'] == 1].index
                    
                    logs_df = pd.DataFrame([
                        {
                            "Aktie": selected_s,
                            "Kaufdatum": b_dates[i].date(), 
                            "Verkaufsdatum": e_dates[i].date(),
                            "Kaufpreis": round(d_df.loc[b_dates[i], 'Close'], 2),
                            "Verkaufspreis": round(d_df.loc[e_dates[i], 'Close'], 2),
                            "Rendite %": round((d_df.loc[e_dates[i], 'Close']/d_df.loc[b_dates[i], 'Close']-1)*100, 2),
                            "Grund": d_df.loc[e_dates[i], 'Exit_Reason']
                        } for i in range(min(len(b_dates), len(e_dates)))
                    ])

                    st.subheader(f"📜 Handels-Logbuch: {selected_s}")
                    st.table(logs_df)

                    # --- EXPORT FUNKTION ---
                    if not logs_df.empty:
                        csv = logs_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label=f"📥 Download Logbuch ({selected_s}) als CSV",
                            data=csv,
                            file_name=f'Handelslog_{selected_s}.csv',
                            mime='text/csv',
                        )
except Exception as e:
    st.error(f"Fehler: {e}")
