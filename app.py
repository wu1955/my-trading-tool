import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Seite konfigurieren
st.set_page_config(page_title="Profi-Quant-Arena", layout="wide")

# --- 1. SEITENLEISTE: Alle Parameter ---
with st.sidebar:
    st.header("🔬 Strategie-Zentrale")
    symbols_str = st.text_input("Aktien (z.B. AAPL, NVDA, TSLA)", value="AAPL, NVDA")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("📏 EMA-System")
    ema_f = st.number_input("Kurze EMA (Standard 10)", value=10)
    ema_m = st.number_input("Mittlere EMA (Standard 20)", value=20)
    ema_l = st.number_input("Lange EMA (Standard 200)", value=200)

    st.subheader("⏱️ Exit-Management")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Stopp nutzen", value=True)
    
    st.subheader("📊 Filter-Faktoren")
    v_rel = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    beta_lim = st.slider("Max. Beta", 0.5, 3.0, 1.5)
    perf_3m_min = st.slider("3M Performance Min (%)", -50, 50, 0)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2021-01-01"))

# --- 2. BACKTEST-KERN (Inkl. EMA, 3M Perf & Beta) ---
def run_full_backtest(symbol, df_all, mkt_close):
    try:
        # Daten für das spezifische Symbol extrahieren
        if len(symbols) > 1:
            df = pd.DataFrame({
                'Close': df_all['Close'][symbol],
                'Volume': df_all['Volume'][symbol]
            }).copy()
        else:
            df = pd.DataFrame({
                'Close': df_all['Close'],
                'Volume': df_all['Volume']
            }).copy()
        
        # EMA Berechnungen
        df['EMA_F'] = df['Close'].ewm(span=ema_f, adjust=False).mean()
        df['EMA_M'] = df['Close'].ewm(span=ema_m, adjust=False).mean()
        df['EMA_L'] = df['Close'].ewm(span=ema_l, adjust=False).mean()
        
        # Volumen & Performance
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
        
        # Beta
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # --- SIGNAL-LOGIK ---
        # Bedingung: Preis > EMA10 > EMA20 UND Preis > EMA200 UND Filter erfüllt
        df['Trigger'] = (
            (df['Close'] > df['EMA_F']) & (df['EMA_F'] > df['EMA_M']) & 
            (df['Close'] > df['EMA_L']) & (df['Rel_Vol'] > v_rel) & 
            (df['Beta'] < beta_lim) & (df['Perf_3M'] > perf_3m_min)
        ).astype(int)

        # Simulation Haltedauer & Stopps
        signals = np.zeros(len(df))
        exit_reasons = [""] * len(df)
        in_pos = False; days = 0
        
        for i in range(len(df)):
            if in_pos:
                time_exit = days >= max_hold
                sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA_M'].iloc[i]) # Stopp bei EMA20
                if time_exit or sl_exit:
                    in_pos = False; days = 0
                    exit_reasons[i] = "Zeitlimit" if time_exit else "EMA-Stopp"
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

# --- 3. HAUPTPROGRAMM ---
try:
    if symbols:
        with st.spinner('Analysiere Marktdaten...'):
            all_tickers = list(set(symbols + ["^GSPC"]))
            data = yf.download(all_tickers, start=start_date)
            
            if not data.empty:
                mkt_close = data['Close']["^GSPC"] if len(all_tickers) > 1 else yf.download("^GSPC", start=start_date)['Close']
                
                results_map = {}
                ranking_data = []
                
                for s in symbols:
                    res_df = run_full_backtest(s, data, mkt_close)
                    if res_df is not None:
                        results_map[s] = res_df
                        total_ret = (res_df['Cum_Strategy'].iloc[-1] - 1) * 100
                        ranking_data.append({"Aktie": s, "Rendite %": round(total_ret, 2), "Endwert": round(res_df['Cum_Strategy'].iloc[-1], 3)})

                # --- CHART ---
                st.title("🏆 Strategie-Arena")
                fig = go.Figure()
                for s, res_df in results_map.items():
                    fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Cum_Strategy'], name=s))
                
                mkt_cum = (1 + mkt_close.pct_change().fillna(0)).cumprod()
                fig.add_trace(go.Scatter(x=mkt_cum.index, y=mkt_cum, name="S&P 500 (Benchmark)", line=dict(dash='dot', color='gray')))
                fig.update_layout(template="plotly_white", height=500, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

                # --- RANKING ---
                st.subheader("📊 Performance-Ranking")
                rank_df = pd.DataFrame(ranking_data).sort_values(by="Endwert", ascending=False)
                st.table(rank_df)

                # --- LOGBUCH ---
                st.write("---")
                selected_s = st.selectbox("Detailliertes Logbuch anzeigen für:", symbols)
                d_df = results_map[selected_s]
                
                d_df['Entry'] = ((d_df['Signal'] == 1) & (d_df['Signal'].shift(1) == 0)).astype(int)
                d_df['Exit'] = ((d_df['Signal'] == 0) & (d_df['Signal'].shift(1) == 1)).astype(int)
                
                b_dates = d_df[d_df['Entry'] == 1].index
                e_dates = d_df[d_df['Exit'] == 1].index
                
                logs = []
                for i in range(min(len(b_dates), len(e_dates))):
                    b_p = d_df.loc[b_dates[i], 'Close']
                    e_p = d_df.loc[e_dates[i], 'Close']
                    logs.append({
                        "Kaufdatum": b_dates[i].date(),
                        "Verkaufsdatum": e_dates[i].date(),
                        "Kaufpreis": f"${b_p:.2f}",
                        "Verkaufspreis": f"${e_p:.2f}",
                        "Rendite": f"{(e_p/b_p-1)*100:.2f}%",
                        "Grund": d_df.loc[e_dates[i], 'Exit_Reason']
                    })
                
                st.subheader(f"📜 Handels-Logbuch: {selected_s}")
                if logs:
                    st.table(pd.DataFrame(logs))
                else:
                    st.info("Keine abgeschlossenen Trades im gewählten Zeitraum.")
    else:
        st.info("Bitte geben Sie mindestens ein Aktiensymbol in der Seitenleiste ein.")

except Exception as e:
    st.error(f"Fehler bei der Ausführung: {e}")
