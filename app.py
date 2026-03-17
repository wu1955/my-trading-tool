import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. 基础配置
st.set_page_config(page_title="我的私人美股回测系统", layout="wide")
st.title("📈 美股策略回测与专业 K 线")

# 2. 侧边栏：参数输入
with st.sidebar:
    st.header("⚙️ 策略设置")
    symbol = st.text_input("股票代码 (如: AAPL)", value="AAPL")
    ma_fast = st.slider("短期均线周期", 5, 50, 20)
    ma_slow = st.slider("长期均线周期", 20, 200, 60)
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2023-01-01"))
    st.write("---")
    st.info("💡 此版本不再依赖外部脚本，确保所有设备均可显示。")

# 3. 获取数据并计算
try:
    df = yf.download(symbol, start=start_date)
    if not df.empty:
        df['Fast_MA'] = df['Close'].rolling(window=ma_fast).mean()
        df['Slow_MA'] = df['Close'].rolling(window=ma_slow).mean()
        
        # 交易逻辑
        df['Signal'] = (df['Fast_MA'] > df['Slow_MA']).astype(float)
        df['Position'] = df['Signal'].diff() # 1为金叉买入，-1为死叉卖出
        
        # 收益计算
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Returns'] * df['Signal'].shift(1)
        df['Cum_Returns'] = (1 + df['Strategy_Returns'].fillna(0)).cumprod()
        df['Market_Returns'] = (1 + df['Returns'].fillna(0)).cumprod()

        # 4. 显示核心指标
        c1, c2, c3 = st.columns(3)
        c1.metric("策略累计收益", f"{(df['Cum_Returns'].iloc[-1]-1)*100:.2f}%")
        c2.metric("同期基准收益", f"{(df['Market_Returns'].iloc[-1]-1)*100:.2f}%")
        c3.metric("当前状态", "持仓" if df['Signal'].iloc[-1] > 0 else "空仓")

        # 5. 绘制专业 K 线图（包含均线和买卖信号）
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.05, subplot_titles=(f'{symbol} K线与均线', '策略累计收益'),
                           row_heights=[0.7, 0.3])

        # K线图
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                    low=df['Low'], close=df['Close'], name='K线'), row=1, col=1)
        # 均线
        fig.add_trace(go.Scatter(x=df.index, y=df['Fast_MA'], line=dict(color='yellow', width=1), name=f'{ma_fast}MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Slow_MA'], line=dict(color='blue', width=1), name=f'{ma_slow}MA'), row=1, col=1)

        # 买卖标记
        buys = df[df['Position'] == 1]
        sells = df[df['Position'] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=buys['Low']*0.98, mode='markers', 
                                marker=dict(symbol='triangle-up', size=12, color='green'), name='买入信号'), row=1, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=sells['High']*1.02, mode='markers', 
                                marker=dict(symbol='triangle-down', size=12, color='red'), name='卖出信号'), row=1, col=1)

        # 收益曲线
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Returns'], line=dict(color='orange'), name='策略累计收益'), row=2, col=1)
        
        fig.update_layout(height=800, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"数据加载失败: {e}")
