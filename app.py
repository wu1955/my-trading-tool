import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="高级趋势过滤器回测器", layout="wide")

# --- 1. SEITENLEISTE: 增加动态过滤开关 ---
with st.sidebar:
    st.header("🔬 策略实验室")
    symbols_str = st.text_input("股票代码 (如 AAPL, NVDA)", value="AAPL")
    symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]
    
    st.subheader("📏 EMA 趋势过滤开关")
    # 💡 这里的三个开关就是你要求的“股价与均线关系”
    above_ema_f = st.checkbox("要求：股价 > 短期 EMA (10)", value=True)
    above_ema_m = st.checkbox("要求：股价 > 中期 EMA (20)", value=True)
    above_ema_l = st.checkbox("要求：股价 > 长期 EMA (200)", value=True)
    
    st.write("---")
    st.subheader("参数微调")
    ema_f_val = st.number_input("短线 EMA 周期", value=10)
    ema_m_val = st.number_input("中线 EMA 周期", value=20)
    ema_l_val = st.number_input("长线 EMA 周期", value=200)
    
    max_hold = st.slider("最大持仓天数", 1, 60, 20)
    start_date = st.date_input("起始日期", value=pd.to_datetime("2021-01-01"))

# --- 2. 核心计算引擎 ---
def run_backtest(symbol, df_all, mkt_close):
    try:
        if isinstance(df_all.columns, pd.MultiIndex):
            df = df_all.xs(symbol, axis=1, level=1).dropna(subset=['Close'])
        else:
            df = df_all[['Close', 'Volume']].dropna()
        
        if len(df) < ema_l_val: return None

        # 计算均线
        df['EMA_F'] = df['Close'].ewm(span=ema_f_val, adjust=False).mean()
        df['EMA_M'] = df['Close'].ewm(span=ema_m_val, adjust=False).mean()
        df['EMA_L'] = df['Close'].ewm(span=ema_l_val, adjust=False).mean()
        
        # --- 💡 动态逻辑组装 ---
        # 初始条件为 True (全选)
        condition = pd.Series([True] * len(df), index=df.index)
        
        if above_ema_f:
            condition &= (df['Close'] > df['EMA_F'])
        if above_ema_m:
            condition &= (df['Close'] > df['EMA_M'])
        if above_ema_l:
            condition &= (df['Close'] > df['EMA_L'])
            
        df['Trigger'] = condition.astype(int)

        # 模拟持仓
        signals = np.zeros(len(df)); in_pos = False; days = 0
        ret = df['Close'].pct_change()
        
        for i in range(len(df)):
            if in_pos:
                if days >= max_hold or (df['Close'].iloc[i] < df['EMA_M'].iloc[i]): # 跌破中线止损
                    in_pos = False; days = 0
                else:
                    signals[i] = 1; days += 1
            elif df['Trigger'].iloc[i] == 1:
                in_pos = True; signals[i] = 1; days = 1
        
        df['Signal'] = signals
        df['Cum_Strategy'] = (1 + (ret * pd.Series(signals, index=df.index).shift(1)).fillna(0)).cumprod()
        return df
    except: return None

# --- 3. 页面渲染 ---
try:
    if symbols:
        data = yf.download(symbols + ["^GSPC"], start=start_date)
        mkt_close = data['Close']["^GSPC"]
        
        results_map = {}
        for s in symbols:
            res = run_backtest(s, data, mkt_close)
            if res is not None: results_map[s] = res

        # 选定展示的个股
        selected_s = symbols[0] if len(symbols) == 1 else st.selectbox("选择分析个股", symbols)
        
        if selected_s in results_map:
            d_df = results_map[selected_s]
            
            # 创建双图：上方股价+均线，下方橙色收益线
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
                               subplot_titles=(f'{selected_s} 价格与均线系统', '策略累计收益 (橙色线)'),
                               row_heights=[0.6, 0.4])
            
            # 上图
            fig.add_trace(go.Scatter(x=d_df.index, y=d_df['Close'], name='股价', line=dict(color='black', width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=d_df.index, y=d_df['EMA_F'], name='短线EMA', line=dict(color='blue', width=1, dash='dot')), row=1, col=1)
            fig.add_trace(go.Scatter(x=d_df.index, y=d_df['EMA_L'], name='长线EMA', line=dict(color='red', width=1.5)), row=1, col=1)
            
            # 下图：橙色收益曲线
            fig.add_trace(go.Scatter(x=d_df.index, y=d_df['Cum_Strategy'], name='策略收益', 
                                    line=dict(color='#FF8C00', width=3)), row=2, col=1)
            
            fig.update_layout(template="plotly_white", height=800, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            # 导出与报表 (保留之前的功能)
            st.write("📈 **当前策略表现**")
            st.metric("最终净值", f"{d_df['Cum_Strategy'].iloc[-1]:.2f}")

except Exception as e:
    st.error(f"发生错误: {e}")
