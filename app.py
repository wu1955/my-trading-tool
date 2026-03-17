import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta  # 新增：专业的指标库
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="我的自定义策略工具", layout="wide")

# 侧边栏：这里你可以自由增加你需要的参数
with st.sidebar:
    st.header("⚙️ 策略参数")
    symbol = st.text_input("股票代码", value="AAPL")
    st.write("---")
    # 示例参数：你可以根据需要修改这些数字
    param_1 = st.slider("参数 A (如均线)", 5, 200, 20)
    param_2 = st.slider("参数 B (如RSI阈值)", 10, 90, 30)
    start_date = st.date_input("开始日期", value=pd.to_datetime("2023-01-01"))

try:
    df = yf.download(symbol, start=start_date)
    if not df.empty:
        # ==========================================
        # 💡 在这里编写你的自定义策略逻辑
        # ==========================================
        
        # 1. 计算指标 (使用 pandas_ta 库，支持上百种指标)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        df['MA_FAST'] = ta.sma(df['Close'], length=param_1)
        
        # 2. 定义【买入】和【卖出】条件 (这就是你的“大脑”)
        # 示例：当价格在均线上方 且 RSI 小于 70 时买入
        buy_condition = (df['Close'] > df['MA_FAST']) & (df['RSI'] < 70)
        
        # 3. 生成信号 (1代表持仓，0代表空仓)
        df['Signal'] = 0.0
        df['Signal'] = buy_condition.astype(float)
        
        # ==========================================

        # 后台自动计算收益
        df['Trade'] = df['Signal'].diff() 
        df['Returns'] = df['Close'].pct_change()
        df['Strategy'] = (1 + (df['Returns'] * df['Signal'].shift(1)).fillna(0)).cumprod()

        # 绘图 (修复了缩放问题)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                           subplot_titles=('收盘价', '策略收益曲线'))
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='white')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Strategy'], name='策略收益', line=dict(color='orange')), row=2, col=1)
        
        # 标注买卖点
        buys = df[df['Trade'] == 1]; sells = df[df['Trade'] == -1]
        fig.add_trace(go.Scatter(x=buys.index, y=df.loc[buys.index, 'Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-up', size=12, color='lime'), name='买入'), row=2, col=1)
        fig.add_trace(go.Scatter(x=sells.index, y=df.loc[sells.index, 'Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-down', size=12, color='red'), name='卖出'), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"逻辑错误: {e}")
