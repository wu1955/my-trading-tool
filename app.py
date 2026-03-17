import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="我的美股回测工具", layout="wide")

# 侧边栏：策略参数
with st.sidebar:
    st.title("⚙️ 策略设置")
    symbol = st.text_input("股票代码 (如: NASDAQ:AAPL)", value="NASDAQ:AAPL")
    interval = st.selectbox("周期", ["1D", "1W", "1h", "15"], index=0)

# 主界面：TradingView 官方图表组件
st.title(f"📈 {symbol} 实时分析与回测")

# TradingView 嵌入代码逻辑
tv_widget_html = f"""
<div class="tradingview-widget-container" style="height:600px;">
  <div id="tradingview_chart"></div>
  <script type="text/javascript" src="https://s3.tradingview.com"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "autosize": true,
    "symbol": "{symbol}",
    "interval": "{interval}",
    "timezone": "Etc/UTC",
    "theme": "dark",
    "style": "1",
    "locale": "zh_CN",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "hide_side_toolbar": false,
    "allow_symbol_change": true,
    "container_id": "tradingview_chart"
  }});
  </script>
</div>
"""
components.html(tv_widget_html, height=600)

st.info("💡 提示：您可以在左侧修改代码，右侧图表会自动刷新。")
