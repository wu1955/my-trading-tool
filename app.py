import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Mein Handels-Tool", layout="wide")

with st.sidebar:
    st.header("⚙️ Strategie-Einstellungen")
    symbol = st.text_input("Aktiensymbol (z. B. AAPL)", value="AAPL")
    ma_val = st.slider("Zeitraum Durchschnitt (MA)", 5, 200, 20)
    start_date = st.date_input("Startdatum", value=pd.to_datetime("2023-01-01"))

try:
    # 1. Daten herunterladen
    df = yf.download(symbol, start=start_date)
    
    if not df.empty:
        # --- FEHLERBEHEBUNG FÜR AUSRICHTUNG (ALIGNMENT) ---
        # Falls yfinance MultiIndex-Spalten liefert, nehmen wir nur die erste Ebene
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Sicherstellen, dass wir mit einer sauberen Datenreihe arbeiten
        close_price = df['Close'].copy()
        
        # 2. Indikator berechnen (Gleitender Durchschnitt)
        df['MY_MA'] = close_price.rolling(window=ma_val).mean()
        
        # 3. Strategie-Logik: Kaufen wenn Preis > Durchschnitt
        # Wir nutzen .values, um den "Alignment"-Fehler sicher zu umgehen
        df['Signal'] = 0.0
        df.loc[close_price > df['MY_MA'], 'Signal'] = 1.0
        
        # 4. Rendite berechnen
        returns = close_price.pct_change()
        # Strategie-Rendite: Gestern das Signal, heute die Marktbewegung
        strategy_returns = (returns * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + strategy_returns).cumprod()

        # --- VISUALISIERUNG ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=('Preis & Durchschnitt', 'Strategie-Rendite (Kumuliert)'))
        
        # Oben: Kursverlauf
        fig.add_trace(go.Scatter(x=df.index, y=close_price, name='Kurs', line=dict(color='white')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MY_MA'], name='MA Durchschnitt', line=dict(color='cyan')), row=1, col=1)
        
        # Unten: Renditekurve
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='Rendite', line=dict(color='orange')), row=2, col=1)
        
        # Kaufs- und Verkaufssignale einzeichnen
        df['Trade'] = df['Signal'].diff()
        buys = df[df['Trade'] == 1]
        sells = df[df['Trade'] == -1]
        
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Cum_Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-up', size=12, color='lime'), name='Kauf'), row=2, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=df.loc[sells.index, 'Cum_Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-down', size=12, color='red'), name='Verkauf'), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("Keine Daten gefunden. Prüfen Sie das Symbol.")
except Exception as e:
    st.error(f"Hoppla, ein Fehler: {e}")
