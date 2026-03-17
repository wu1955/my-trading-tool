import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="我的私人美股回测系统", layout="wide")

with st.sidebar:
    st.header("⚙️ 策略设置")
    symbol = st.text_input("股票代码", value="AAPL")
    ma_fast = st.slider("短期均线", 5, 50, 20)
    ma_slow = st.slider("长期均线", 20, 200, 60)
    start_date = st.date_input("开始日期", value=pd.to_datetime("2023-01-01"))

try:
    df = yf.download(symbol, start=start_date)
    if not df.empty:
        # 计算逻辑
        df['MA_F'] = df['Close'].rolling(window=ma_fast).mean()
        df['MA_S'] = df['Close'].rolling(window=ma_slow).mean()
        df['Signal'] = (df['MA_F'] > df['MA_S']).astype(float)
        df['Trade'] = df['Signal'].diff() 
        
        df['Returns'] = df['Close'].pct_change()
        df['Strategy'] = (1 + (df['Returns'] * df['Signal'].shift(1)).fillna(0)).cumprod()
        df['Market'] = (1 + df['Returns'].fillna(0)).cumprod()

        # 绘图优化
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=('股价与均线 (K线已隐去以突出均线)', '策略累计收益 (附买卖点)'))

        # 图表 1: 股价
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='white', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA_F'], name=f'{ma_fast}MA', line=dict(color='yellow', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA_S'], name=f'{ma_slow}MA', line=dict(color='blue', width=1.5)), row=1, col=1)

        # 图表 2: 收益曲线 + 信号标记
        fig.add_trace(go.Scatter(x=df.index, y=df['Strategy'], name='策略累计收益', line=dict(color='orange', width=2)), row=2, col=1)
        
        # 强制将买卖信号画在收益曲线上
        buys = df[df['Trade'] == 1]
        sells = df[df['Trade'] == -1]
        
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Strategy'], mode='markers',
                                marker=dict(symbol='triangle-up', size=15, color='lime', line=dict(width=2, color='white')),
                                name='买入信号'), row=2, col=1)
        
        fig.add_trace(go.Scatter(x=sells.index, y=df.loc[sells.index, 'Strategy'], mode='markers',
                                marker=dict(symbol='triangle-down', size=15, color='red', line=dict(width=2, color='white')),
                                name='卖出信号'), row=2, col=1)

        fig.update_layout(height=800, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

        st.success(f"回测完成！信号已标注在【下方】收益曲线上。")

except Exception as e:
    st.error(f"出错啦: {e}")
