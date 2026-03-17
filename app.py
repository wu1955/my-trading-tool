import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="我的私人回测工具", layout="wide")

with st.sidebar:
    st.header("⚙️ 自定义策略")
    symbol = st.text_input("股票代码", value="AAPL")
    ma_val = st.slider("均线周期", 5, 200, 20)
    start_date = st.date_input("开始日期", value=pd.to_datetime("2023-01-01"))

try:
    # 获取数据
    df = yf.download(symbol, start=start_date)
    if not df.empty:
        # ==========================================
        # 💡 这里就是你自己设定策略的地方 (无需外部插件)
        # ==========================================
        
        # 1. 计算均线 (直接用 pandas 自带的 rolling 函数)
        df['MY_MA'] = df['Close'].rolling(window=ma_val).mean()
        
        # 2. 设定你的买入逻辑
        # 比如：股价 > 均线 就买入
        buy_condition = df['Close'] > df['MY_MA']
        
        # 3. 生成信号 (1为持仓，0为空仓)
        df['Signal'] = 0.0
        df['Signal'] = buy_condition.astype(float)
        
        # ==========================================

        # 自动计算收益
        df['Trade'] = df['Signal'].diff() 
        df['Strategy'] = (1 + (df['Close'].pct_change() * df['Signal'].shift(1)).fillna(0)).cumprod()

        # 绘图
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=('股价与自定义均线', '策略累计收益'))
        
        # 上图：股价 + 均线
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='white')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MY_MA'], name='自定义均线', line=dict(color='cyan')), row=1, col=1)
        
        # 下图：收益曲线 + 买卖点
        fig.add_trace(go.Scatter(x=df.index, y=df['Strategy'], name='策略收益', line=dict(color='orange')), row=2, col=1)
        
        buys = df[df['Trade'] == 1]; sells = df[df['Trade'] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-up', size=12, color='lime'), name='买入'), row=2, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=df.loc[sells.index, 'Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-down', size=12, color='red'), name='卖出'), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"运行出错: {e}")
