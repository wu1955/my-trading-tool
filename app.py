import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="高级多因子策略实验室", layout="wide")

# --- 1. 侧边栏：多维度参数设定 ---
with st.sidebar:
    st.header("🔬 因子过滤器")
    symbol = st.text_input("股票代码", value="AAPL")
    
    st.subheader("📊 成交量因子")
    v_period = st.slider("月均成交量周期(天)", 5, 60, 21)
    v_rel_ratio = st.slider("相对成交量倍数 (当前/均值)", 0.5, 5.0, 1.2)
    
    st.subheader("📈 价格动量")
    lookback_days = st.slider("表现回顾周期(天)", 10, 250, 60)
    min_perf = st.slider("最低区间涨跌幅 (%)", -50, 100, 10)
    
    st.subheader("📉 风险因子 (Beta)")
    beta_limit = st.slider("最大允许 Beta (波动率对比)", 0.5, 3.0, 1.5)
    
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2022-01-01"))

# --- 2. 核心计算引擎 ---
try:
    # 同时获取个股和基准(标普500)数据来计算 Beta
    tickers = [symbol, "^GSPC"]
    data = yf.download(tickers, start=start_date)
    
    if not data.empty:
        # 清理多层表头
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][symbol]
            volume = data['Volume'][symbol]
            mkt_close = data['Close']["^GSPC"]
        else:
            close = data[symbol] # 某些版本兼容
            
        # --- 计算各种因子 ---
        # 1. 月均成交量与成交额
        df = pd.DataFrame({'Close': close, 'Volume': volume})
        df['Avg_Vol'] = df['Volume'].rolling(window=v_period).mean()
        df['Rel_Vol'] = df['Volume'] / df['Avg_Vol']
        df['Turnover'] = df['Close'] * df['Volume'] # 当日成交额
        
        # 2. 区间涨跌幅 (3个月/自定义周期)
        df['Perf'] = (df['Close'] / df['Close'].shift(lookback_days) - 1) * 100
        
        # 3. 计算 Beta (个股收益与大盘收益的相关性)
        df['Ret'] = df['Close'].pct_change()
        df['Mkt_Ret'] = mkt_close.pct_change()
        # 滚动计算 60 天 Beta
        covariance = df['Ret'].rolling(60).cov(df['Mkt_Ret'])
        variance = df['Mkt_Ret'].rolling(60).var()
        df['Beta'] = covariance / variance

        # --- 💡 核心：在这里组合你的【专属策略】 ---
        # 逻辑：相对成交量够大 + 近期涨幅达标 + 波动率(Beta)不过高
        buy_condition = (
            (df['Rel_Vol'] > v_rel_ratio) & 
            (df['Perf'] > min_perf) & 
            (df['Beta'] < beta_limit)
        )
        
        df['Signal'] = 0.0
        df.loc[buy_condition, 'Signal'] = 1.0

        # 收益统计
        df['Strategy_Returns'] = (df['Ret'] * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        df['Cum_Market'] = (1 + df['Ret'].fillna(0)).cumprod()

        # --- 3. 绘图展示 ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                           subplot_titles=('价格', '因子观察 (相对成交量 & Beta)', '累计收益对比'),
                           row_heights=[0.4, 0.3, 0.3])
        
        # Row 1: 价格
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='white')), row=1, col=1)
        
        # Row 2: 因子 (相对成交量)
        fig.add_trace(go.Bar(x=df.index, y=df['Rel_Vol'], name='相对成交量', marker_color='purple', opacity=0.5), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Beta'], name='Beta值', line=dict(color='yellow')), row=2, col=1)
        fig.add_hline(y=v_rel_ratio, line_dash="dash", line_color="red", row=2, col=1)

        # Row 3: 收益
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='策略收益', line=dict(color='orange', width=3)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Market'], name='基准收益', line=dict(color='gray', dash='dot')), row=3, col=1)

        # 标注买点
        df['Trade'] = df['Signal'].diff()
        buys = df[df['Trade'] == 1]
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Cum_Strategy'], mode='markers', 
                                marker=dict(symbol='star', size=12, color='lime'), name='买入信号'), row=3, col=1)

        fig.update_layout(height=900, template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        
        # 显示实时因子数值表格
        st.subheader("📋 当前因子实时数值")
        st.table(df[['Close', 'Rel_Vol', 'Beta', 'Perf']].tail(1))

    else:
        st.warning("未找到数据。")
except Exception as e:
    st.error(f"逻辑错误: {e}。可能是因为回测时间太短导致 Beta 无法计算，请拉长时间。")
