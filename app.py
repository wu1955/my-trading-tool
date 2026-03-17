import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Seite konfigurieren
st.set_page_config(page_title="Quant-Terminal Pro (Final)", layout="wide")

# --- 1. SEITENLEISTE ---
with st.sidebar:
    st.header("🔬 Strategie-Zentrale")
    symbols_str = st.text_input("Aktien (z.B. AAPL, NVDA, 600519.SS)", value="AAPL, NVDA")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("📏 EMA-Trend-Filter")
    f_check = st.checkbox("Preis > EMA10", value=True)
    m_check = st.checkbox("Preis > EMA20", value=True)
    l_check = st.checkbox("Preis > EMA200", value=True)
    
    st.subheader("📊 Filter-Faktoren")
    v_rel_limit = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    beta_limit = st.slider("Max. Beta (US)", 0.5, 4.0, 2.0)
    perf_3m_min = st.slider("3M Performance Min (%)", -50, 50, 0) # <--- WIEDER DA!
    
    st.subheader("⏱️ Exit-Management")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Stopp (Verkauf)", value=True)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2021-01-01"))

# --- 2. BACKTEST-KERN ---
def run_backtest(symbol, df_raw, mkt_ret):
    try:
        if isinstance(df_raw.columns, pd.MultiIndex):
            df = df_raw.xs(symbol, axis=1, level=1).dropna(subset=['Close']).copy()
        else:
            df = df_raw[['Close', 'Volume']].dropna().copy()
        
        if len(df) < 200: return None

        # Indikatoren
        df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100 # <--- BERECHNUNG
        
        ret = df['Close'].pct_change()
        common = ret.index.intersection(mkt_ret.index)
        if len(common) > 60:
            df['Beta'] = (ret.loc[common].rolling(60).cov(mkt_ret.loc[common]) / 
                          mkt_ret.loc[common].rolling(60).var()).reindex(df.index, method='ffill').fillna(0)
        else:
            df['Beta'] = 0.0

        # Kauf-Trigger inkl. 3M Performance
        trigger = pd.Series([True] * len(df), index=df.index)
        if f_check: trigger &= (df['Close'] > df['EMA10'])
        if m_check: trigger &= (df['Close'] > df['EMA20'])
        if l_check: trigger &= (df['Close'] > df['EMA200'])
        trigger &= (df['Rel_Vol'] > v_rel_limit)
        trigger &= (df['Perf_3M'] > perf_3m_min) # <--- LOGIK-FILTER
        if beta_limit > 0: trigger &= ((df['Beta'] < beta_limit) | (df['Beta'] == 0))
        df['Trigger'] = trigger.astype(int)

        # Simulation
        signals = np.zeros(len(df)); exit_reasons = [""] * len(df)
        in_pos = False; days = 0
        for i in range(len(df)):
            if in_pos:
                time_exit = days >= max_hold
                sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA20'].iloc[i])
                if time_exit or sl_exit:
                    in_pos = False; days = 0
                    exit_reasons[i] = "Zeit" if time_exit else "EMA20-Stopp"
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

# --- 3. DARSTELLUNG ---
try:
    if symbols:
        with st.spinner('Analysiere Strategien...'):
            all_data = yf.download(symbols + ["^GSPC"], start=start_date)
            mkt_ret = all_data['Close']["^GSPC"].pct_change()
            
            results_map = {}
            for s in symbols:
                res = run_backtest(s, all_data, mkt_ret)
                if res is not None: results_map[s] = res

        if results_map:
            # A. Arena
            st.title("🏆 Die Strategie-Arena")
            fig_arena = go.Figure()
            for s, res_df in results_map.items():
                fig_arena.add_trace(go.Scatter(x=res_df.index, y=res_df['Cum_Strategy'], name=s))
            fig_arena.update_layout(template="plotly_white", height=400, title="Rendite-Vergleich")
            st.plotly_chart(fig_arena, use_container_width=True)

            # B. Detail-Analyse
            st.write("---")
            selected_s = st.selectbox("🎯 Detail-Analyse wählen (Logbuch & Orange Kurve):", list(results_map.keys()))
            d_df = results_map[selected_s]
            
            fig_detail = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                       subplot_titles=('Preis & EMAs', f'Strategie-Rendite {selected_s} (Orange)'),
                                       row_heights=[0.6, 0.4])
            fig_detail.add_trace(go.Scatter(x=d_df.index, y=d_df['Close'], name='Preis', line=dict(color='black', width=1)), row=1, col=1)
            fig_detail.add_trace(go.Scatter(x=d_df.index, y=d_df['EMA10'], name='EMA10', line=dict(color='blue')), row=1, col=1)
            fig_detail.add_trace(go.Scatter(x=d_df.index, y=d_df['EMA200'], name='EMA200', line=dict(color='red')), row=1, col=1)
            fig_detail.add_trace(go.Scatter(x=d_df.index, y=d_df['Cum_Strategy'], name='Rendite', line=dict(color='#FF8C00', width=3)), row=2, col=1)
            fig_detail.update_layout(template="plotly_white", height=700)
            st.plotly_chart(fig_detail, use_container_width=True)

            # C. Logbuch & Export
            d_df['Entry'] = ((d_df['Signal'] == 1) & (d_df['Signal'].shift(1) == 0)).astype(int)
            d_df['Exit'] = ((d_df['Signal'] == 0) & (d_df['Signal'].shift(1) == 1)).astype(int)
            b_dates = d_df[d_df['Entry'] == 1].index
            e_dates = d_df[d_df['Exit'] == 1].index
            
            logs = []
            for i in range(min(len(b_dates), len(e_dates))):
                logs.append({
                    "Kauf": b_dates[i].date(), "Verkauf": e_dates[i].date(),
                    "Kaufpreis": round(d_df.loc[b_dates[i], 'Close'], 2),
                    "Verkaufspreis": round(d_df.loc[e_dates[i], 'Close'], 2),
                    "Ergebnis %": round((d_df.loc[e_dates[i], 'Close']/d_df.loc[b_dates[i], 'Close']-1)*100, 2),
                    "Grund": d_df.loc[e_dates[i], 'Exit_Reason']
                })
            
            st.subheader(f"📜 Handels-Logbuch: {selected_s}")
            logs_df = pd.DataFrame(logs)
            if not logs_df.empty:
                st.table(logs_df)
                csv = logs_df.to_csv(index=False).encode('utf-8')
                st.download_button(f"📥 Download {selected_s} Logbuch", csv, f"{selected_s}_trades.csv", "text/csv")
            else:
                st.info("Keine abgeschlossenen Trades gefunden.")

except Exception as e:
    st.error(f"Fehler: {e}")
