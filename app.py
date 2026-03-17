import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# 页面配置
st.set_page_config(page_title="多股策略竞技场", layout="wide")

# --- 1. 侧边栏：多股参数设定 ---
with st.sidebar:
    st.header("🔬 竞技场设置")
    # 支持输入多个代码
    symbols_str = st.text_input("股票代码 (用逗号分隔)", value="AAPL, NVDA, TSLA")
    symbols = [s.strip().upper() for s in symbols_str.split(",")]
    
    st.subheader("⏱️ 持仓与退出")
    max_hold = st.slider("最大持仓天数", 1, 60, 20)
    use_stop_loss = st.checkbox("启用 EMA20 破位止损", value=True)
    
    st.subheader("📏 统一因子门槛")
    v_rel = st.slider("相对成交量倍数", 0.5, 5.0, 1.2)
    beta_lim = st.slider("最大允许 Beta", 0.5, 3.0, 2.0)
    
    start_date = st.date_input("回测起始日期", value=pd.to_datetime("2022-01-01"))

# --- 2. 核心回测引擎 (多股循环) ---
def run_backtest(symbol, df_all, mkt_close):
    try:
        # 提取单只股票数据
        df = pd.DataFrame({
            'Close': df_all['Close'][symbol],
            'Volume': df_all['Volume'][symbol]
        }).copy()
        
        # 指标计算
        df['EMA10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['Rel_Vol'] = df['Volume'] / df['Volume'].rolling(21).mean()
        
        ret = df['Close'].pct_change()
        mkt_ret = mkt_close.pct_change()
        df['Beta'] = ret.rolling(60).cov(mkt_ret) / mkt_ret.rolling(60).var()

        # 信号逻辑
        df['Trigger'] = (
            (df['Close'] > df['EMA10']) & (df['EMA10'] > df['EMA20']) & 
            (df['Close'] > df['EMA200']) & (df['Rel_Vol'] > v_rel) & 
            (df['Beta'] < beta_lim)
        ).astype(int)

        signals = np.zeros(len(df))
        in_pos = False; days = 0
        for i in range(len(df)):
            if in_pos:
                if (days >= max_hold) or (use_stop_loss and df['Close'].iloc[i] < df['EMA20'].iloc[i]):
                    in_pos = False; days = 0
                else:
                    signals[i] = 1; days += 1
            elif df['Trigger'].iloc[i] == 1:
                in_pos = True; signals[i] = 1; days = 1
        
        return (1 + (ret * pd.Series(signals).shift(1).values).fillna(0)).cumprod()
    except:
        return None

# --- 3. 执行对比 ---
try:
    with st.spinner('正在调取全球数据并计算...'):
        all_tickers = symbols + ["^GSPC"]
        data = yf.download(all_tickers, start=start_date)
        
        if not data.empty:
            mkt_close = data['Close']["^GSPC"]
            results = pd.DataFrame(index=data.index)
            
            # 对每只股票运行同样的策略
            for s in symbols:
                res = run_backtest(s, data, mkt_close)
                if res is not None:
                    results[s] = res
            
            # 加入大盘基准
            results['S&P 500 (基准)'] = (1 + mkt_close.pct_change().fillna(0)).cumprod()

            # --- 4. 绘图对比 ---
            st.title("🏆 多股策略收益竞技场")
            fig = go.Figure()
            for col in results.columns:
                width = 3 if col in symbols else 1.5
                dash = 'dash' if col == 'S&P 500 (基准)' else 'solid'
                fig.add_trace(go.Scatter(x=results.index, y=results[col], name=col, line=dict(width=width, dash=dash)))

            fig.update_layout(height=600, template="plotly_white", title="不同股票在同一策略下的收益表现", 
                              hovermode="x unified", yaxis_title="累计净值 (1.0 = 初始资金)")
            st.plotly_chart(fig, use_container_width=True)

            # --- 5. 排行榜表格 ---
            st.subheader("📊 最终战绩排名")
            final_stats = []
            for s in symbols:
                if s in results.columns:
                    total_ret = (results[s].iloc[-1] - 1) * 100
                    final_stats.append({"股票": s, "累计收益率": f"{total_ret:.2f}%", "最终净值": round(results[s].iloc[-1], 2)})
            
            stats_df = pd.DataFrame(final_stats).sort_values(by="最终净值", ascending=False)
            st.table(stats_df)

except Exception as e:
    st.error(f"竞技场运行出错: {e}")
