import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Seite konfigurieren
st.set_page_config(page_title="Profi-Aktien-Arena", layout="wide")

# --- 1. SEITENLEISTE: Alle Faktoren ---
with st.sidebar:
    st.header("🔬 Strategie-Parameter")
    symbols_str = st.text_input("Aktiensymbole (z.B. AAPL, NVDA, TSLA)", value="AAPL, NVDA")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("⏱️ Exit-Management")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Breakout Stopp", value=True)
    
    st.subheader("📊 Filter-Faktoren")
    v_rel = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    beta_lim = st.slider("Max. Beta", 0.5, 3.0, 1.5)
    perf_3m_min = st.slider("3M Performance Minimum (%)", -50, 50, 0)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2022-01-01"))

# --- 2. BACKTEST-FUNKTION (Inkl. 3M Performance & Beta) ---
def run_full_backtest(symbol, df_all, mkt_close):
    try:
        df = pd.DataFrame({
            'Close': df_all['Close'][symbol],
            'Volume': df_all['Volume'][symbol]
        }).copy()
        
        # Indikatoren
        df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
        
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # Signal-Logik (Inkl. 3M Performance)
        df['Trigger'] = ((df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
                         (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel) & 
                         (df['Beta'] < beta_lim) & (df['Perf_3M'] > perf_3m_min)).astype(int)

        signals = np.zeros(len(df))
        exit_reasons = [""] * len(df)
        in_pos = False; days = 0
        for i in range(len(df)):
            if in_pos:
                time_exit = days >= max_hold
                sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA20'].iloc[i])
                if time_exit or sl_exit:
                    in_pos = False; days = 0
                    exit_reasons[i] = "Zeitlimit" if time_exit else "EMA20-Stopp"
                else:
                    signals[i] = 1; days += 1
            elif df['Trigger'].iloc[i] == 1:
                in_pos = True; signals[i] = 1; days = 1
        
        df['Signal'] = signals
        df['Exit_Reason'] = exit_reasons
        df['Strategy_Ret'] = (ret * pd.Series(signals).shift(1).values).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Ret']).cumprod()
        return df
    except Exception as e:
        return None

# --- 3. HAUPTTEIL ---
try:
    with st.spinner('Marktdaten werden geladen...'):
        all_tickers = symbols + ["^GSPC"]
        data = yf.download(all_tickers, start=start_date)
        
        if not data.empty:
            mkt_close = data['Close']["^GSPC"]
            results_map = {}
            ranking_list = []
            
            for s in symbols:
                res_df = run_full_backtest(s, data, mkt_close)
                if res_df is not None:
                    results_map[s] = res_df
                    final_return = (res_df['Cum_Strategy'].iloc[-1] - 1) * 100
                    ranking_list.append({"Aktie": s, "Rendite %": round(final_return, 2), "Endwert": round(res_df['Cum_Strategy'].iloc[-1], 2)})

            # --- ARENA CHART ---
            st.title("🏆 Die Strategie-Arena")
            fig = go.Figure()
            for s, res_df in results_map.items():
                fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Cum_Strategy'], name=s))
            
            mkt_cum = (1 + mkt_close.pct_change().fillna(0)).cumprod()
            fig.add_trace(go.Scatter(x=mkt_cum.index, y=mkt_cum, name="S&P 500 (Markt)", line=dict(dash='dot', color='gray')))
            fig.update_layout(template="plotly_white", height=500, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # --- RANKING TABELLE ---
            st.subheader("📊 Performance-Ranking")
            rank_df = pd.DataFrame(ranking_list).sort_values(by="Endwert", ascending=False)
            st.table(rank_df)

            # --- DETAILLIERTES LOGBUCH ---
            if symbols:
                st.write("---")
                selected_s = st.selectbox("Detailliertes Logbuch wählen:", symbols)
                detail_df = results_map[selected_s]
                
                detail_df['Entry'] = ((detail_df['Signal'] == 1) & (detail_df['Signal'].shift(1) == 0)).astype(int)
                detail_df['Exit'] = ((detail_df['Signal'] == 0) & (detail_df['Signal'].shift(1) == 1)).astype(int)
                
                b_dates = detail_df[detail_df['Entry'] == 1].index
                e_dates = detail_df[detail_df['Exit'] == 1].index
                
                logs = []
                for i in range(min(len(b_dates), len(e_dates))):
                    b_p = detail_df.loc[b_dates[i], 'Close']
                    e_p = detail_df.loc[e_dates[i], 'Close']
                    logs.append({
                        "Kauf am": b_dates[i].date(),
                        "Verkauf am": e_dates[i].date(),
                        "Kaufpreis": f"${b_p:.2f}",
                        "Verkaufspreis": f"${e_p:.2f}",
                        "Ergebnis": f"{(e_p/b_p-1)*100:.2f}%",
                        "Grund": detail_df.loc[e_dates[i], 'Exit_Reason']
                    })
                
                st.subheader(f"📜 Handels-Logbuch: {selected_s}")
                if logs:
                    st.table(pd.DataFrame(logs))
                else:
                    st.info("Keine abgeschlossenen Trades gefunden.")

except Exception as e:
    st.error(f"Ein Fehler ist aufgetreten: {e}")
