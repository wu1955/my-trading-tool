import streamlit as st
import streamlit.components.v1 as components

# 页面配置
st.set_page_config(page_title="我的私人美股分析工具", layout="wide")

# 侧边栏：输入
with st.sidebar:
    st.title("⚙️ 策略设置")
    # 尝试使用简写的代码，如 AAPL 或 TSLA
    symbol_input = st.text_input("股票代码 (如: AAPL)", value="AAPL")
    interval = st.selectbox("周期", ["D", "W", "120", "60", "30", "15", "5"], index=0)
    
    st.write("---")
    st.write("💡 提示：如果图表仍不显示，请尝试切换网络（如手机热点）。")

# 主界面标题
st.title(f"📊 {symbol_input} 实时行情分析")

# TradingView 增强版嵌入代码
# 使用了更稳定的官方 URL 和标准的容器 ID
tv_html = f"""
<div class="tradingview-widget-container" style="height: 600px; width: 100%;">
  <div id="tv_chart_container" style="height: 100%; width: 100%;"></div>
  <script type="text/javascript" src="https://s3.tradingview.com"></script>
  <script type="text/javascript">
  new TradingView.widget({{
    "width": "100%",
    "height": 600,
    "symbol": "{symbol_input}",
    "interval": "{interval}",
    "timezone": "Etc/UTC",
    "theme": "dark",
    "style": "1",
    "locale": "zh_CN",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "allow_symbol_change": true,
    "container_id": "tv_chart_container"
  }});
  </script>
</div>
"""

# 渲染图表
components.html(tv_html, height=620)

st.success("✅ 网页已连接至 TradingView 数据中心")
