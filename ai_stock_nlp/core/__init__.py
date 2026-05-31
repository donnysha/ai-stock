# =============================================================================
# 核心模块 - 系统核心功能
# =============================================================================
# 功能：协调各层工作，提供涨跌停判断、参数验证等核心工具
# 子模块：
#   - dispatcher.py: 策略调度器，协调AI层和业务层
#   - validators.py: 参数验证器
#   - limit_up_utils.py: 涨跌停判断工具
# =============================================================================

from .dispatcher import StrategyDispatcher
from .validators import ParamValidator
from .limit_up_utils import (
    get_stock_board,
    is_new_stock,
    get_limit_threshold,
    is_limit_up,
    is_limit_down,
    is_limit_up_or_down,
    is_limit_by_lianban,
    is_limit_up_by_combined,
    is_limit_down_by_combined,
    calculate_limit_price,
    get_limit_info,
    check_limit_status,
    get_min_change_threshold,
    StockBoard,
    LimitRule,
)

__all__ = [
    'StrategyDispatcher',     # 策略调度器
    'ParamValidator',         # 参数验证器
    # 涨跌停工具
    'get_stock_board',       # 获取股票板块
    'is_new_stock',          # 判断是否新股
    'get_limit_threshold',   # 获取涨跌停阈值
    'is_limit_up',           # 判断是否涨停
    'is_limit_down',         # 判断是否跌停
    'is_limit_up_or_down',   # 同时判断涨跌停
    'is_limit_by_lianban',   # 根据连板天判断
    'is_limit_up_by_combined',    # 综合判断涨停
    'is_limit_down_by_combined',  # 综合判断跌停
    'calculate_limit_price',      # 计算涨跌停价
    'get_limit_info',             # 获取涨跌停信息
    'check_limit_status',         # 检查涨跌停状态
    'get_min_change_threshold',    # 获取最小涨幅阈值
    'StockBoard',             # 板块枚举
    'LimitRule',             # 涨跌停规则
]
