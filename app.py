import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import streamlit.components.v1 as components

# 1. 基础配置
st.set_page_config(page_title="我的私人美股回测系统", layout="wide")
st.title("📈 美股策略回测与实时行情")

# 2. 侧边栏：参数输入
with st.sidebar:
    st.header("⚙️ 策略设置")
    symbol = st.text_input("股票代码 (如: AAPL)", value="AAPL")
    ma_fast = st.slider("短期均线周期", 5, 50, 20)
    ma_slow = st.slider("长期均线周期", 20, 200, 60)
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2023-01-01"))
    btn = st.button("开始回测并更新图表")

# 3. 逻辑处理：获取数据并回测
try:
    # 获取雅虎财经历史数据
    df = yf.download(symbol, start=start_date)
    
    if not df.empty:
        # 计算策略
        df['Fast_MA'] = df['Close'].rolling(window=ma_fast).mean()
        df['Slow_MA'] = df['Close'].rolling(window=ma_slow).mean()
        
        # 交易信号：金叉买入，死叉卖出
        df['Signal'] = 0.0
        df['Signal'] = (df['Fast_MA'] > df['Slow_MA']).astype(float)
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Returns'] * df['Signal'].shift(1)
        df['Cum_Returns'] = (1 + df['Strategy_Returns'].fillna(0)).cumprod()
        df['Market_Returns'] = (1 + df['Returns'].fillna(0)).cumprod()

        # 4. 显示回测指标（台式机必显部分）
        col1, col2, col3 = st.columns(3)
        final_return = (df['Cum_Returns'].iloc[-1] - 1) * 100
        market_return = (df['Market_Returns'].iloc[-1] - 1) * 100
        
        col1.metric("策略累计收益", f"{final_return:.2f}%")
        col2.metric("同期基准收益", f"{market_return:.2f}%")
        col3.metric("交易次数", int(df['Signal'].diff().abs().sum() / 2))

        # 绘制收益对比图
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Returns'], name='策略收益', line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=df.index, y=df['Market_Returns'], name='持有收益', line=dict(color='gray', dash='dash')))
        fig.update_layout(title="收益增长对比图", template="plotly_dark", height=400)
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.warning("未找到股票数据，请检查代码输入是否正确。")
except Exception as e:
    st.error(f"回测出错: {e}")

st.write("---")

# 5. 实时行情部分（TradingView 嵌入）
st.subheader("📺 实时看盘图表")
tv_html = f"""
<div style="height: 500px;">
  <div id="tv_chart"></div>
  <script type="text/javascript" src="https://s3.tradingview.com"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "{symbol}",
    "interval": "D",
    "theme": "dark",
    "style": "1",
    "locale": "zh_CN",
    "container_id": "tv_chart"
  }});
  </script>
</div>
"""
components.html(tv_html, height=520)
