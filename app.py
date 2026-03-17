import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="我的高级策略实验室", layout="wide")

# --- 1. 左侧策略控制面板 ---
with st.sidebar:
    st.header("🛠️ 策略实验室")
    symbol = st.text_input("股票代码", value="AAPL")
    
    st.subheader("均线参数 (MA)")
    ma_val = st.slider("均线周期", 5, 200, 20)
    
    st.subheader("强弱参数 (RSI)")
    rsi_val = st.slider("RSI 买入阈值 (低于此值考虑买入)", 10, 50, 30)
    
    st.subheader("风控参数")
    stop_loss = st.slider("止损百分比 (%)", 1.0, 20.0, 5.0) / 100
    
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2023-01-01"))

# --- 2. 核心计算逻辑 ---
try:
    df = yf.download(symbol, start=start_date)
    if not df.empty:
        # 清理 yfinance 的多层表头
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        close = df['Close']
        
        # 指标计算：均线
        df['MA'] = close.rolling(window=ma_val).mean()
        
        # 指标计算：RSI (手动计算，无需额外插件)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # --- 💡 自定义你的买入逻辑 ---
        # 现在的逻辑是：价格 > 均线 且 RSI < 70
        df['Signal'] = 0.0
        buy_condition = (close > df['MA']) & (df['RSI'] < 70)
        df.loc[buy_condition, 'Signal'] = 1.0

        # --- 3. 收益统计 ---
        returns = close.pct_change()
        df['Strategy_Returns'] = (returns * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        df['Cum_Market'] = (1 + returns.fillna(0)).cumprod()

        # --- 4. 绘图 ---
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=('股价与均线', '策略 vs 市场 (累计收益)'))
        
        # 上图：价格
        fig.add_trace(go.Scatter(x=df.index, y=close, name='股价', line=dict(color='white')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MA'], name='MA', line=dict(color='cyan')), row=1, col=1)
        
        # 下图：收益对比
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='我的策略', line=dict(color='orange')), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name='直接持有', line=dict(color='gray', dash='dash')), row=2, col=1)

        # 标注买卖点
        df['Trade'] = df['Signal'].diff()
        buys = df[df['Trade'] == 1]; sells = df[df['Trade'] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Cum_Strategy'], mode='markers', marker=dict(symbol='triangle-up', size=12, color='lime'), name='买入'), row=2, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=df.loc[sells.index, 'Cum_Strategy'], mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='卖出'), row=2, col=1)

        fig.update_layout(height=800, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("未找到数据。")
except Exception as e:
    st.error(f"逻辑执行出错: {e}")
