import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="私人量化实验室-全因子版", layout="wide")

# --- 1. 侧边栏：完整参数设定 ---
with st.sidebar:
    st.header("🔬 策略参数控制")
    symbol = st.text_input("股票代码", value="AAPL")
    hold_days = st.slider("强制持仓天数", 1, 60, 10)
    
    st.subheader("📏 EMA 均线系统")
    ema_f = st.number_input("短线 EMA", value=10)
    ema_m = st.number_input("中线 EMA", value=20)
    ema_l = st.number_input("长线 EMA", value=200)
    
    st.subheader("📊 因子过滤")
    v_rel = st.slider("相对成交量倍数", 0.5, 5.0, 1.2)
    beta_lim = st.slider("最大允许 Beta", 0.5, 3.0, 1.5)
    min_perf_3m = st.slider("3个月最低涨幅(%)", -50, 50, 0)
    
    start_date = st.date_input("起始日期", value=pd.to_datetime("2021-01-01"))

# --- 2. 核心引擎 ---
try:
    # 获取个股和大盘数据
    tickers = [symbol, "^GSPC"]
    data = yf.download(tickers, start=start_date)
    
    if not data.empty:
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][symbol]; volume = data['Volume'][symbol]
            mkt_close = data['Close']["^GSPC"]
        else:
            close = data[symbol]; volume = 0 
            
        df = pd.DataFrame({'Close': close, 'Volume': volume}).copy()
        
        # --- A. 因子计算 ---
        # 1. 均线
        df['EMA10'] = df['Close'].ewm(span=ema_f, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=ema_m, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=ema_l, adjust=False).mean()
        
        # 2. 成交量相关
        df['Avg_Vol_Month'] = df['Volume'].rolling(21).mean() # 月均成交量
        df['Rel_Vol'] = df['Volume'] / df['Avg_Vol_Month']
        df['Turnover_Month'] = df['Close'] * df['Avg_Vol_Month'] # 月均成交额
        
        # 3. 3个月表现 (60个交易日)
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
        
        # 4. Beta 计算
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # --- B. 信号逻辑 ---
        df['Trigger'] = (
            (df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
            (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel) & 
            (df['Beta'] < beta_lim) & (df['Perf_3M'] > min_perf_3m)
        ).astype(int)

        signals = np.zeros(len(df)); cooldown = 0
        for i in range(len(df)):
            if cooldown > 0:
                signals[i] = 1; cooldown -= 1
            elif df['Trigger'].iloc[i] == 1:
                signals[i] = 1; cooldown = hold_days - 1
        
        df['Signal'] = signals
        df['Strategy_Returns'] = (ret * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        df['Cum_Market'] = (1 + ret.fillna(0)).cumprod()

        # --- 3. 绘图 (白色主题 + 小箭头) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                           subplot_titles=('价格与 EMA', '成交量与 3个月表现', '策略累计收益'), 
                           row_heights=[0.4, 0.3, 0.3])
        
        # Row 1
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='#1f77b4')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], name='EMA200', line=dict(color='red', width=2)), row=1, col=1)

        # Row 2 (展示成交量和表现)
        fig.add_trace(go.Bar(x=df.index, y=df['Rel_Vol'], name='相对成交量', marker_color='purple', opacity=0.3), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Perf_3M'], name='3M涨幅%', line=dict(color='orange')), row=2, col=1)

        # Row 3 (收益曲线 + 红色小箭头)
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='策略收益', line=dict(color='darkgreen', width=2.5)), row=3, col=1)
        
        df['Entry'] = ((df['Signal'] == 1) & (df['Signal'].shift(1) == 0)).astype(int)
        entries = df[df['Entry'] == 1]
        
        # 修改点：改用小箭头
        fig.add_trace(go.Scatter(
            x=entries.index, 
            y=df.loc[entries.index, 'Cum_Strategy'], 
            mode='markers', 
            marker=dict(symbol='triangle-up', size=10, color='red'), # 红色小箭头
            name='买入信号'
        ), row=3, col=1)

        fig.update_layout(height=900, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        
        # --- 4. 详细因子仪表盘 ---
        st.subheader("📋 因子实时数值与报告")
        last = df.iloc[-1]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("累计收益率", f"{(df['Cum_Strategy'].iloc[-1]-1)*100:.2f}%")
        c2.metric("月均成交量", f"{last['Avg_Vol_Month']/1e6:.1f}M")
        c3.metric("月成交额", f"${last['Turnover_Month']/1e6:.1f}M")
        c4.metric("3个月表现", f"{last['Perf_3M']:.1f}%")

        # --- 5. 交易明细表 ---
        st.subheader("📜 历史交易清单")
        trade_history = df[df['Entry'] == 1][['Close', 'Rel_Vol', 'Beta', 'Perf_3M']].copy()
        trade_history.columns = ['买入价', '相对成交量', 'Beta值', '3M表现%']
        st.dataframe(trade_history.style.format("{:.2f}"), use_container_width=True)

    else:
        st.warning("未找到数据。")
except Exception as e:
    st.error(f"运行出错: {e}")
