# =============================================================================
# 页面模块 - 多页面应用
# =============================================================================
# 功能：分离的页面组件
# 子模块：
#   - stock_select.py: 选股页面
#   - backtest_page.py: 策略回测页面
# =============================================================================

from .stock_select import render_stock_select_page
from .backtest_page import render_backtest_page
from .news_page import render_news_page

__all__ = [
    'render_stock_select_page',     # 选股页面渲染函数
    'render_backtest_page',         # 策略回测页面渲染函数
    'render_news_page',             # 个股新闻页面渲染函数
]
