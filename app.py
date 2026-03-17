import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="私人量化交易实验室-白色主题版", layout="wide")

# --- 1. 侧边栏：参数设定 ---
with st.sidebar:
    st.header("🔬 核心策略因子")
    symbol = st.text_input("股票代码", value="AAPL")
    
    st.subheader("⏱️ 持仓管理")
    hold_days = st.slider("买入后强制持仓天数", 1, 60, 10)
    
    st.subheader("📏 EMA 均线系统")
    ema_fast_val = st.number_input("短线 EMA (如10)", value=10)
    ema_mid_val = st.number_input("中线 EMA (如20)", value=20)
    ema_long_val = st.number_input("长线 EMA (如200)", value=200)
    
    st.subheader("📊 过滤因子")
    v_rel_ratio = st.slider("相对成交量倍数", 0.5, 5.0, 1.2)
    beta_limit = st.slider("最大允许 Beta", 0.5, 3.0, 1.5)
    
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2021-01-01"))

# --- 2. 核心计算引擎 ---
try:
    # 获取数据
    tickers = [symbol, "^GSPC"]
    data = yf.download(tickers, start=start_date)
    
    if not data.empty:
        # 处理表头逻辑
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][symbol]; volume = data['Volume'][symbol]
            mkt_close = data['Close']["^GSPC"]
        else:
            close = data[symbol]; volume = 0 
            
        df = pd.DataFrame({'Close': close, 'Volume': volume}).copy()
        
        # 指标计算
        df['EMA10'] = df['Close'].ewm(span=ema_fast_val, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=ema_mid_val, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=ema_long_val, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        
        # Beta 计算
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # --- 💡 持仓逻辑模拟 ---
        df['Trigger'] = (
            (df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
            (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel_ratio) & 
            (df['Beta'] < beta_limit)
        ).astype(int)

        signals = np.zeros(len(df))
        cooldown = 0
        for i in range(len(df)):
            if cooldown > 0:
                signals[i] = 1
                cooldown -= 1
            elif df['Trigger'].iloc[i] == 1:
                signals[i] = 1
                cooldown = hold_days - 1
        
        df['Signal'] = signals
        df['Strategy_Returns'] = (ret * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        df['Cum_Market'] = (1 + ret.fillna(0)).cumprod()

        # --- 3. 绘图展示 (高对比度白色主题) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                           subplot_titles=('股价与 EMA 系统', '因子观察 (相对成交量 & Beta)', f'策略累计收益 (持仓限制: {hold_days}天)'),
                           row_heights=[0.5, 0.25, 0.25])
        
        # Row 1: 股价 (深色线)
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='#1f77b4', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA10'], name='EMA10', line=dict(color='#ff7f0e', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], name='EMA20', line=dict(color='#2ca02c', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], name='EMA200', line=dict(color='#d62728', width=2)), row=1, col=1)

        # Row 2: 因子
        fig.add_trace(go.Bar(x=df.index, y=df['Rel_Vol'], name='相对成交量', marker_color='#9467bd', opacity=0.4), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Beta'], name='Beta', line=dict(color='#8c564b')), row=2, col=1)

        # Row 3: 收益曲线
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='策略收益', line=dict(color='#006400', width=3)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name='指数基准', line=dict(color='#7f7f7f', dash='dot')), row=3, col=1)

        # 标注买点 (红色五角星)
        df['Entry'] = ((df['Signal'] == 1) & (df['Signal'].shift(1) == 0)).astype(int)
        entries = df[df['Entry'] == 1]
        fig.add_trace(go.Scatter(
            x=entries.index, 
            y=df.loc[entries.index, 'Cum_Strategy'], 
            mode='markers', 
            marker=dict(symbol='star', size=14, color='red', line=dict(width=1, color='black')), 
            name='买入进场'
        ), row=3, col=1)

        # 强制设置白色主题
        fig.update_layout(height=1000, template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        # 统计报表
        st.subheader("📊 策略实测报告")
        total_ret = (df['Cum_Strategy'].iloc[-1] - 1) * 100
        trade_count = int(df['Entry'].sum())
        cols = st.columns(3)
        cols.metric("累计总收益率", f"{total_ret:.2f}%", delta=f"{total_ret - (df['Cum_Market'].iloc[-1]-1)*100:.2f}% (超额)")
        cols.metric("总交易次数", f"{trade_count} 次")
        cols.metric("状态", "空仓" if cooldown==0 else f"持仓中({cooldown}天)")

    else:
        st.warning("未找到数据。")
except Exception as e:
    st.error(f"逻辑错误: {e}")
