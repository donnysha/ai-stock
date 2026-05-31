# =============================================================================
# 业务逻辑层模块
# =============================================================================
# 功能：执行具体的业务逻辑，包括选股、回测、收益计算等
# 子模块：
#   - stock_selector.py: 选股执行器
#   - grid_backtester.py: 网格交易回测引擎
#   - profit_calculator.py: 收益计算器
#   - backtrader_engine.py: Backtrader回测引擎适配器
#   - sql_generator.py: SQL生成器（固化代码）
#   - data_fetcher.py: 业务层数据获取器封装
# =============================================================================

from .stock_selector import StockSelector
from .grid_backtester import GridBacktester
from .profit_calculator import ProfitCalculator
from .backtrader_engine import BacktraderEngine
from .sql_generator import SQLGenerator, sql_generator
from .data_fetcher import DataFetcher, get_data_fetcher

__all__ = [
    'StockSelector',       # 选股执行器
    'GridBacktester',      # 网格回测引擎
    'ProfitCalculator',    # 收益计算器
    'BacktraderEngine',    # Backtrader引擎
    'SQLGenerator',         # SQL生成器
    'sql_generator',        # SQL生成器全局实例
    'DataFetcher',          # 数据获取器
    'get_data_fetcher'      # 获取数据获取器实例
]
