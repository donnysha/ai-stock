# =============================================================================
# 展示层模块 - Web界面
# =============================================================================
# 功能：提供Web用户界面，基于Streamlit框架
# 子模块：
#   - app.py: Streamlit Web应用主入口
#   - pages/: 多页面应用（选股、回测等）
#   - charts/: 图表组件
# =============================================================================

from .pages.stock_select import render_stock_select_page
from .pages.backtest_page import render_backtest_page
from .charts.kline_chart import KLineChart
from .charts.result_charts import ResultCharts

__all__ = [
    'render_stock_select_page',   # 选股页面渲染函数
    'render_backtest_page',       # 策略回测页面渲染函数
    'KLineChart',                 # K线图组件
    'ResultCharts'                # 结果图表组件
]