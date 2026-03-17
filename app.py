import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Seite konfigurieren
st.set_page_config(page_title="Aktien-Strategie-Arena", layout="wide")

# --- 1. SEITENLEISTE: Parameter ---
with st.sidebar:
    st.header("🔬 Strategie-Zentrale")
    symbols_str = st.text_input("Aktiensymbole (kommagetrennt)", value="AAPL, NVDA")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("⏱️ Exit-Regeln")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Breakout Stopp nutzen", value=True)
    
    st.subheader("📊 Filter-Faktoren")
    v_rel = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    beta_lim = st.slider("Max. Beta", 0.5, 3.0, 1.5)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2022-01-01"))

# --- 2. BACKTEST-KERNFUNKTION ---
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
        
        ret = df['Close'].pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_close.pct_change()) / mkt_close.pct_change().rolling(60).var()

        # Signal-Logik
        df['Trigger'] = ((df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
                         (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel) & 
                         (df['Beta'] < beta_lim)).astype(int)

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
    except:
        return None

# --- 3. AUSFÜHRUNG ---
try:
    with st.spinner('Daten werden analysiert...'):
        all_tickers = symbols + ["^GSPC"]
        data = yf.download(all_tickers, start=start_date)
        
        if not data.empty:
            mkt_close = data['Close']["^GSPC"]
            results_map = {}
            
            for s in symbols:
                res_df = run_full_backtest(s, data, mkt_close)
                if res_df is not None:
                    results_map[s] = res_df

            # --- VISUALISIERUNG ---
            st.title("🏆 Strategie-Arena")
            
            fig = go.Figure()
            for s, res_df in results_map.items():
                fig.add_trace(go.Scatter(x=res_df.index, y=res_df['Cum_Strategy'], name=s))
            
            # Markt-Benchmark hinzufügen
            mkt_cum = (1 + mkt_close.pct_change().fillna(0)).cumprod()
            fig.add_trace(go.Scatter(x=mkt_cum.index, y=mkt_cum, name="S&P 500", line=dict(dash='dash', color='gray')))
            
            fig.update_layout(template="plotly_white", height=500, hovermode="x unified", title="Rendite-Vergleich")
            st.plotly_chart(fig, use_container_width=True)

            # --- DETAIL-ANSICHT (LOGBUCH) ---
            if len(symbols) > 0:
                st.write("---")
                # Wenn mehrere Aktien da sind, wählen Sie eine für das Logbuch aus
                selected_s = st.selectbox("Detailliertes Logbuch anzeigen für:", symbols)
                
                detail_df = results_map[selected_s]
                
                # Performance-Metriken
                c1, c2, c3 = st.columns(3)
                final_ret = (detail_df['Cum_Strategy'].iloc[-1]-1)*100
                c1.metric(f"Gesamtrendite {selected_s}", f"{final_ret:.2f}%")
                
                # Handelsliste erstellen
                detail_df['Entry'] = ((detail_df['Signal'] == 1) & (detail_df['Signal'].shift(1) == 0)).astype(int)
                detail_df['Exit'] = ((detail_df['Signal'] == 0) & (detail_df['Signal'].shift(1) == 1)).astype(int)
                
                buy_dates = detail_df[detail_df['Entry'] == 1].index
                exit_dates = detail_df[detail_df['Exit'] == 1].index
                
                logs = []
                for i in range(min(len(buy_dates), len(exit_dates))):
                    b_p = detail_df.loc[buy_dates[i], 'Close']
                    e_p = detail_df.loc[exit_dates[i], 'Close']
                    logs.append({
                        "Kaufdatum": buy_dates[i].date(),
                        "Verkaufsdatum": exit_dates[i].date(),
                        "Kaufpreis": f"${b_p:.2f}",
                        "Verkaufspreis": f"${e_p:.2f}",
                        "Ergebnis": f"{(e_p/b_p-1)*100:.2f}%",
                        "Grund": detail_df.loc[exit_dates[i], 'Exit_Reason']
                    })
                
                st.subheader(f"📜 Detailliertes Logbuch: {selected_s}")
                if logs:
                    st.table(pd.DataFrame(logs))
                else:
                    st.info("Keine abgeschlossenen Trades für diesen Zeitraum gefunden.")

except Exception as e:
    st.error(f"Fehler: {e}")
