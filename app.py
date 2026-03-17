import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Seite konfigurieren
st.set_page_config(page_title="Quant-Master-Terminal", layout="wide")

# --- 1. SEITENLEISTE: Alle Parameter & Filter ---
with st.sidebar:
    st.header("🔬 Strategie-Zentrale")
    symbol = st.text_input("Aktiensymbol (z.B. AAPL)", value="AAPL").upper()
    
    st.subheader("📏 EMA-Trend-Filter")
    # Ihre gewünschten Schalter für die Kauf-Bedingung
    f_check = st.checkbox("Preis > EMA10 erforderlich", value=True)
    m_check = st.checkbox("Preis > EMA20 erforderlich", value=True)
    l_check = st.checkbox("Preis > EMA200 erforderlich", value=True)
    
    st.subheader("📊 Filter-Faktoren")
    v_rel = st.slider("Relat. Volumen (x)", 0.5, 5.0, 1.2)
    beta_lim = st.slider("Max. Beta (US)", 0.5, 4.0, 1.5)
    perf_3m_min = st.slider("3M Performance Min (%)", -50, 50, 0)
    
    st.subheader("⏱️ Exit-Management")
    max_hold = st.slider("Max. Haltedauer (Tage)", 1, 60, 20)
    use_stop_loss = st.checkbox("EMA20-Breakout Stopp (Verkauf)", value=True)
    
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2021-01-01"))

# --- 2. BACKTEST-KERN ---
try:
    with st.spinner('Analysiere Daten...'):
        # Daten laden (Aktie + S&P500 für Beta)
        data = yf.download([symbol, "^GSPC"], start=start_date)
        
        if not data.empty and symbol in data['Close']:
            df = pd.DataFrame({
                'Close': data['Close'][symbol],
                'Volume': data['Volume'][symbol]
            }).dropna()
            mkt_close = data['Close']["^GSPC"]
            
            # Indikatoren berechnen
            df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
            df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
            df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
            
            # Beta Berechnung
            ret = df['Close'].pct_change()
            mkt_ret = mkt_close.pct_change()
            common = ret.index.intersection(mkt_ret.index)
            df['Beta'] = (ret.loc[common].rolling(60).cov(mkt_ret.loc[common]) / 
                          mkt_ret.loc[common].rolling(60).var()).reindex(df.index, method='ffill').fillna(0)

            # --- KAUF-LOGIK (Trigger) ---
            trigger = pd.Series([True] * len(df), index=df.index)
            if f_check: trigger &= (df['Close'] > df['EMA10'])
            if m_check: trigger &= (df['Close'] > df['EMA20'])
            if l_check: trigger &= (df['Close'] > df['EMA200'])
            
            # Filter hinzufügen
            trigger &= (df['Rel_Vol'] > v_rel)
            trigger &= (df['Perf_3M'] > perf_3m_min)
            if beta_lim > 0: trigger &= ((df['Beta'] < beta_lim) | (df['Beta'] == 0))
            
            df['Trigger'] = trigger.astype(int)

            # --- SIMULATION (Exit-Logik) ---
            signals = np.zeros(len(df))
            in_pos = False; days = 0
            for i in range(len(df)):
                if in_pos:
                    # Verkauf wenn Zeit abgelaufen ODER (wenn aktiviert) EMA20 gebrochen
                    time_exit = days >= max_hold
                    sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA20'].iloc[i])
                    if time_exit or sl_exit:
                        in_pos = False; days = 0
                    else:
                        signals[i] = 1; days += 1
                elif df['Trigger'].iloc[i] == 1:
                    in_pos = True; signals[i] = 1; days = 1
            
            df['Signal'] = signals
            df['Cum_Strategy'] = (1 + (ret * pd.Series(signals, index=df.index).shift(1)).fillna(0)).cumprod()

            # --- 3. GRAFIK (Zwei Etagen) ---
            st.title(f"🔍 Analyse-Ergebnis für {symbol}")
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                               subplot_titles=('Preis & EMA-Bänder', 'Strategie-Rendite (Orange)'),
                               row_heights=[0.6, 0.4])
            
            # Obere Etage: Preis & EMAs
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='Preis', line=dict(color='black', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], name='EMA10', line=dict(color='blue', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], name='EMA20 (Stopp)', line=dict(color='green', dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], name='EMA200', line=dict(color='red', width=1.5)), row=1, col=1)
            
            # Untere Etage: ORANGE Renditekurve
            fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='Rendite', 
                                    line=dict(color='#FF8C00', width=3)), row=2, col=1)
            
            fig.update_layout(template="plotly_white", height=800, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # Statistik-Zusammenfassung
            c1, c2, c3 = st.columns(3)
            c1.metric("End-Rendite", f"{(df['Cum_Strategy'].iloc[-1]-1)*100:.2f}%")
            c2.metric("Beta (Aktuell)", f"{df['Beta'].iloc[-1]:.2f}")
            c3.metric("Rel. Volumen", f"{df['Rel_Vol'].iloc[-1]:.2f}x")

        else:
            st.error("Symbol nicht gefunden oder keine Daten verfügbar.")

except Exception as e:
    st.error(f"Fehler: {e}")
