import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 页面配置
st.set_page_config(page_title="私人量化实验室-动态止损版", layout="wide")

# --- 1. 侧边栏：参数设定 ---
with st.sidebar:
    st.header("🔬 策略逻辑控制")
    symbol = st.text_input("股票代码", value="AAPL")
    
    st.subheader("⏱️ 持仓与退出")
    max_hold = st.slider("最大持仓天数", 1, 60, 20)
    use_stop_loss = st.checkbox("启用 EMA20 跌破止损", value=True)
    
    st.subheader("📏 EMA 均线参数")
    ema_f = st.number_input("短线 EMA", value=10)
    ema_m = st.number_input("中线 EMA", value=20)
    ema_l = st.number_input("长线 EMA", value=200)
    
    st.subheader("📊 进场因子过滤")
    v_rel = st.slider("相对成交量倍数", 0.5, 5.0, 1.2)
    beta_lim = st.slider("最大允许 Beta", 0.5, 3.0, 1.5)
    perf_3m_min = st.slider("3个月最低涨幅(%)", -50, 50, 0)
    
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2021-01-01"))

# --- 2. 核心引擎 ---
try:
    tickers = [symbol, "^GSPC"]
    data = yf.download(tickers, start=start_date)
    
    if not data.empty:
        # 处理表头
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][symbol]; volume = data['Volume'][symbol]
            mkt_close = data['Close']["^GSPC"]
        else:
            close = data[symbol]; volume = 0 
            
        df = pd.DataFrame({'Close': close, 'Volume': volume}).copy()
        
        # 指标计算
        df['EMA10'] = df['Close'].ewm(span=ema_f, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=ema_m, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=ema_l, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        df['Perf_3M'] = (df['Close'] / df['Close'].shift(60) - 1) * 100
        
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # --- 💡 核心：动态模拟逻辑 ---
        df['Trigger'] = (
            (df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
            (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel) & 
            (df['Beta'] < beta_lim) & (df['Perf_3M'] > perf_3m_min)
        ).astype(int)

        signals = np.zeros(len(df))
        exit_reasons = [""] * len(df) # 记录卖出原因
        in_position = False
        days_held = 0

        for i in range(len(df)):
            if in_position:
                # 检查卖出条件
                # 1. 达到最大持仓天数
                time_exit = days_held >= max_hold
                # 2. 跌破 EMA20
                sl_exit = use_stop_loss and (df['Close'].iloc[i] < df['EMA20'].iloc[i])
                
                if time_exit or sl_exit:
                    in_position = False
                    days_held = 0
                    exit_reasons[i] = "时间到" if time_exit else "破位止损"
                else:
                    signals[i] = 1
                    days_held += 1
            else:
                # 检查买入条件
                if df['Trigger'].iloc[i] == 1:
                    in_position = True
                    signals[i] = 1
                    days_held = 1
        
        df['Signal'] = signals
        df['Exit_Reason'] = exit_reasons
        df['Strategy_Returns'] = (ret * df['Signal'].shift(1)).fillna(0)
        df['Cum_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        df['Cum_Market'] = (1 + ret.fillna(0)).cumprod()

        # --- 3. 绘图 (白色主题 + 小箭头) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                           subplot_titles=('价格与 20EMA (生命线)', '因子快照', '策略收益对比'), 
                           row_heights=[0.4, 0.3, 0.3])
        
        fig.add_trace(go.Scatter(x=df.index, y=df['Close'], name='股价', line=dict(color='#1f77b4')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], name='EMA20', line=dict(color='green', dash='dot')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], name='EMA200', line=dict(color='red', width=2)), row=1, col=1)

        fig.add_trace(go.Bar(x=df.index, y=df['Rel_Vol'], name='相对成交量', marker_color='purple', opacity=0.3), row=2, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['Cum_Strategy'], name='策略收益', line=dict(color='darkgreen', width=2.5)), row=3, col=1)
        
        # 标注买点
        df['Entry'] = ((df['Signal'] == 1) & (df['Signal'].shift(1) == 0)).astype(int)
        entries = df[df['Entry'] == 1]
        fig.add_trace(go.Scatter(x=entries.index, y=df.loc[entries.index, 'Cum_Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-up', size=10, color='red'), name='进场'), row=3, col=1)
        
        # 标注卖点
        df['Exit_Mark'] = ((df['Signal'] == 0) & (df['Signal'].shift(1) == 1)).astype(int)
        exits = df[df['Exit_Mark'] == 1]
        fig.add_trace(go.Scatter(x=exits.index, y=df.loc[exits.index, 'Cum_Strategy'], mode='markers', 
                                marker=dict(symbol='triangle-down', size=10, color='blue'), name='出场'), row=3, col=1)

        fig.update_layout(height=900, template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
        
        # --- 4. 数据报表 ---
        st.subheader("📊 策略实测报告")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("累计收益率", f"{(df['Cum_Strategy'].iloc[-1]-1)*100:.2f}%")
        c2.metric("交易次数", f"{int(df['Entry'].sum())} 次")
        c3.metric("月均成交额", f"${(df['Close']*df['Volume']).rolling(21).mean().iloc[-1]/1e6:.1f}M")
        c4.metric("3M表现", f"{df['Perf_3M'].iloc[-1]:.1f}%")

        # --- 5. 交易明细表 (含卖出原因) ---
        st.subheader("📜 详细交易日志")
        # 提取买入和卖出的记录
        logs = []
        buy_dates = df[df['Entry'] == 1].index
        exit_dates = df[df['Exit_Mark'] == 1].index
        
        for i in range(len(exit_dates)):
            buy_price = df.loc[buy_dates[i], 'Close']
            exit_price = df.loc[exit_dates[i], 'Close']
            reason = df.loc[exit_dates[i], 'Exit_Reason']
            profit = (exit_price / buy_price - 1) * 100
            logs.append({
                "买入日期": buy_dates[i].date(),
                "卖出日期": exit_dates[i].date(),
                "买入价": f"${buy_price:.2f}",
                "卖出价": f"${exit_price:.2f}",
                "单笔盈亏": f"{profit:.2f}%",
                "卖出原因": reason
            })
        
        st.table(pd.DataFrame(logs))

    else:
        st.warning("未找到数据。")
except Exception as e:
    st.error(f"运行出错: {e}")
