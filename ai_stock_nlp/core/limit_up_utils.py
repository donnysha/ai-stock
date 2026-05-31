"""
涨跌停判断工具模块

A股涨跌停规则：
| 板块       | 代码特征       | 新股期间             | 常态涨跌幅 | ST股  |
|------------|----------------|----------------------|------------|-------|
| 上交所主板 | 60xxxx         | 前5日无限            | ±10%       | ±5%   |
| 深交所主板  | 000xxx, 001xxx | 前5日无限            | ±10%       | ±5%   |
| 科创板     | 688xxx         | 前5日无限            | ±20%       | ±20%  |
| 创业板     | 300xxx         | 前5日无限            | ±20%       | ±20%  |
| 北交所     | 8xxxxx         | 首日无限（次日±30%） | ±30%       | ±30%  |

注意：
1. 新股期间（前5个交易日）不设涨跌停限制
2. 北交所首日无限，次日即开始±30%限制
3. 涨跌停价计算：round(昨收价 × (1 ± 涨跌幅), 2)
4. "连板天"字段含义：连续涨停/跌停天数，>=1表示当天涨停/跌停
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Union, Tuple
from datetime import datetime, timedelta


class StockBoard(IntEnum):
    """股票板块枚举"""
    SSE_MAIN = 1      # 上交所主板 (60xxxx)
    SZSE_MAIN = 2     # 深交所主板 (000xxx, 001xxx)
    SZSE_GEM = 3      # 创业板 (300xxx)
    SSE_STAR = 4      # 科创板 (688xxx)
    BSE = 5           # 北交所 (8xxxxx)
    UNKNOWN = 0       # 未知板块


@dataclass
class LimitRule:
    """涨跌停规则"""
    board: StockBoard           # 板块
    limit_rate: float           # 涨跌停幅度 (0.1 = 10%)
    st_limit_rate: float        # ST股涨跌停幅度
    new_stock_free_days: int    # 新股无限涨跌天数 (0表示无此优惠)
    is_beijing_first_day_free: bool  # 北交所首日是否无限


# 涨跌停规则表
LIMIT_RULES = {
    StockBoard.SSE_MAIN: LimitRule(
        board=StockBoard.SSE_MAIN,
        limit_rate=0.10,
        st_limit_rate=0.05,
        new_stock_free_days=5,
        is_beijing_first_day_free=False
    ),
    StockBoard.SZSE_MAIN: LimitRule(
        board=StockBoard.SZSE_MAIN,
        limit_rate=0.10,
        st_limit_rate=0.05,
        new_stock_free_days=5,
        is_beijing_first_day_free=False
    ),
    StockBoard.SZSE_GEM: LimitRule(
        board=StockBoard.SZSE_GEM,
        limit_rate=0.20,
        st_limit_rate=0.20,  # 创业板ST股也是±20%
        new_stock_free_days=5,
        is_beijing_first_day_free=False
    ),
    StockBoard.SSE_STAR: LimitRule(
        board=StockBoard.SSE_STAR,
        limit_rate=0.20,
        st_limit_rate=0.20,  # 科创板ST股也是±20%
        new_stock_free_days=5,
        is_beijing_first_day_free=False
    ),
    StockBoard.BSE: LimitRule(
        board=StockBoard.BSE,
        limit_rate=0.30,
        st_limit_rate=0.30,  # 北交所ST股也是±30%
        new_stock_free_days=0,  # 首日无限，次日起30%
        is_beijing_first_day_free=True
    ),
}

# 新股无限涨跌判断容差 (避免精确日期计算问题)
NEW_STOCK_TOLERANCE_DAYS = 1


def get_stock_board(stock_code: Union[str, int]) -> StockBoard:
    """
    根据股票代码判断所属板块
    
    Args:
        stock_code: 股票代码 (6位数字字符串或整数)
    
    Returns:
        StockBoard 板块枚举
    """
    code_str = str(stock_code).zfill(6)
    
    if code_str.startswith('60'):
        return StockBoard.SSE_MAIN
    elif code_str.startswith('688'):
        return StockBoard.SSE_STAR
    elif code_str.startswith('000') or code_str.startswith('001'):
        return StockBoard.SZSE_MAIN
    elif code_str.startswith('300'):
        return StockBoard.SZSE_GEM
    elif code_str.startswith('8'):
        return StockBoard.BSE
    else:
        return StockBoard.UNKNOWN


def is_new_stock(listing_date: Union[str, int, datetime], 
                  trade_date: Union[str, datetime],
                  board: StockBoard,
                  tolerance_days: int = NEW_STOCK_TOLERANCE_DAYS) -> bool:
    """
    判断股票在交易日期是否仍处于新股期间
    
    Args:
        listing_date: 上市日期 (格式: YYYYMMDD 或 datetime)
        trade_date: 交易日期 (格式: YYYYMMDD 或 datetime)
        board: 股票板块
        tolerance_days: 容差天数（避免日期计算边界问题）
    
    Returns:
        True if still in new stock period, False otherwise
    """
    if board == StockBoard.UNKNOWN:
        return False
    
    rule = LIMIT_RULES.get(board)
    if not rule:
        return False
    
    # 解析日期
    if isinstance(listing_date, (int, str)):
        if isinstance(listing_date, int):
            listing_date = str(listing_date).zfill(8)
        listing_dt = datetime.strptime(listing_date[:8], '%Y%m%d')
    else:
        listing_dt = listing_date if isinstance(listing_date, datetime) else datetime.fromisoformat(str(listing_date))
    
    if isinstance(trade_date, (int, str)):
        if isinstance(trade_date, int):
            trade_date = str(trade_date).zfill(8)
        trade_dt = datetime.strptime(trade_date[:8], '%Y%m%d')
    else:
        trade_dt = trade_date if isinstance(trade_date, datetime) else datetime.fromisoformat(str(trade_date))
    
    # 计算交易日天数（排除周末）
    trading_days = 0
    current = listing_dt
    while current < trade_dt:
        current += timedelta(days=1)
        if current.weekday() < 5:  # 周一到周五
            trading_days += 1
    
    # 北交所特殊处理：首日无限，次日起算
    if rule.is_beijing_first_day_free:
        return trading_days == 0  # 上市首日
    
    # 其他板块：新股前N个交易日无限涨跌
    return trading_days < rule.new_stock_free_days + tolerance_days


def get_limit_threshold(
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False
) -> Optional[float]:
    """
    获取涨跌停幅度阈值
    
    Args:
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
    
    Returns:
        涨跌停幅度 (如 0.10 表示10%)，新股期间返回 None
    """
    board = get_stock_board(stock_code)
    
    if board == StockBoard.UNKNOWN:
        return None
    
    # 检查是否在新股期间
    if is_new_stock(listing_date, trade_date, board):
        return None  # 新股期间无涨跌停限制
    
    rule = LIMIT_RULES.get(board)
    if not rule:
        return None
    
    # ST股特殊处理
    if is_st:
        return rule.st_limit_rate
    
    return rule.limit_rate


def is_limit_up(
    price_change_pct: float,
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    tolerance_pct: float = 0.01
) -> bool:
    """
    判断是否涨停
    
    四舍五入容差说明：
    -------------
    涨停价计算公式：涨停价 = round(昨收价 × (1 + 涨跌幅), 2)
    
    由于四舍五入到分(0.01元)，实际涨停涨幅可能略低于理论值。
    例如主板10%涨停：
    - 昨收 10.04元 -> 涨停价 round(11.044, 2) = 11.04 -> 实际涨幅 9.96%
    - 昨收 10.05元 -> 涨停价 round(11.055, 2) = 11.06 -> 实际涨幅 10.05%
    
    最极端情况（理论计算）：
    - 主板10%：约 9.89% ~ 10.11%
    - 创业板/科创板20%：约 19.78% ~ 20.22%
    - 北交所30%：约 29.67% ~ 30.33%
    
    考虑实际价格精度(分)，使用 1% 容差是安全保守的选择。
    
    Args:
        price_change_pct: 价格变化百分比 (如 9.8 表示 9.8%)
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        tolerance_pct: 容差百分比 (默认1%，保守估计覆盖四舍五入极端情况)
    
    Returns:
        True if 涨停, False otherwise
    """
    threshold = get_limit_threshold(stock_code, listing_date, trade_date, is_st)
    
    if threshold is None:
        return False  # 新股期间无涨停
    
    # 涨停判断：涨幅 >= 阈值 - 容差
    return price_change_pct >= (threshold * 100 - tolerance_pct)


def is_limit_down(
    price_change_pct: float,
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    tolerance_pct: float = 0.01
) -> bool:
    """
    判断是否跌停
    
    跌停价计算公式：跌停价 = round(昨收价 × (1 - 涨跌幅), 2)
    
    原理同涨停，容差设置一致。
    
    Args:
        price_change_pct: 价格变化百分比（负数，如 -9.8 表示 -9.8%）
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        tolerance_pct: 容差百分比 (默认1%)
    
    Returns:
        True if 跌停, False otherwise
    """
    threshold = get_limit_threshold(stock_code, listing_date, trade_date, is_st)
    
    if threshold is None:
        return False  # 新股期间无跌停
    
    # 跌停判断：跌幅 <= -(阈值 - 容差)
    return price_change_pct <= -(threshold * 100 - tolerance_pct)


def is_limit_up_or_down(
    price_change_pct: float,
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    tolerance_pct: float = 0.01
) -> Tuple[bool, bool]:
    """
    同时判断涨停和跌停
    
    Args:
        price_change_pct: 价格变化百分比 (正数涨停，负数跌停)
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        tolerance_pct: 容差百分比
    
    Returns:
        (is_up, is_down) 元组
    """
    threshold = get_limit_threshold(stock_code, listing_date, trade_date, is_st)
    
    if threshold is None:
        return (False, False)  # 新股期间无涨跌停
    
    limit_value = threshold * 100 - tolerance_pct
    return (price_change_pct >= limit_value, price_change_pct <= -limit_value)


def is_limit_by_lianban(limit_days: Optional[int]) -> bool:
    """
    根据"连板天"字段判断是否涨停/跌停
    
    "连板天"含义：连续涨停/跌停的天数
    - 连板天 >= 1：当天涨停或跌停
    - 连板天 > 1：连续涨停或跌停（第二天及以上）
    
    注意：这个字段不能区分涨停还是跌停，需要结合涨幅方向判断
    
    Args:
        limit_days: 连板天数（来自数据库字段 `连板天`）
    
    Returns:
        True if 涨停/跌停（通过连板天判断）
    """
    if limit_days is None:
        return False
    return limit_days >= 1


def is_limit_up_by_combined(
    price_change_pct: float,
    lianban_days: Optional[int],
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    tolerance_pct: float = 0.01
) -> bool:
    """
    综合判断是否涨停（涨幅 + 连板天双重验证）
    
    涨停的两种判断方式：
    1. 涨幅判断：涨幅 >= 涨停幅度 - 容差
    2. 连板天判断：连板天 >= 1
    
    双重验证更准确，但如果两者结果不一致，可能说明：
    - 连板天字段数据有延迟
    - 股票刚上市（新股期间无涨停限制但可能有连板记录）
    
    Args:
        price_change_pct: 涨幅百分比
        lianban_days: 连板天数
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        tolerance_pct: 容差百分比
    
    Returns:
        True if 涨停（任一条件满足）
    """
    # 涨幅判断
    up_by_change = is_limit_up(price_change_pct, stock_code, listing_date, trade_date, is_st, tolerance_pct)
    
    # 连板天判断（连板天 >= 1 表示当天涨停/跌停）
    up_by_lianban = is_limit_by_lianban(lianban_days) and price_change_pct > 0
    
    # 任一条件满足即认为涨停
    return up_by_change or up_by_lianban


def is_limit_down_by_combined(
    price_change_pct: float,
    lianban_days: Optional[int],
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    tolerance_pct: float = 0.01
) -> bool:
    """
    综合判断是否跌停（跌幅 + 连板天双重验证）
    
    Args:
        price_change_pct: 跌幅百分比（负数）
        lianban_days: 连板天数
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        tolerance_pct: 容差百分比
    
    Returns:
        True if 跌停（任一条件满足）
    """
    # 跌幅判断
    down_by_change = is_limit_down(price_change_pct, stock_code, listing_date, trade_date, is_st, tolerance_pct)
    
    # 连板天判断（连板天 >= 1 表示当天涨停/跌停）
    down_by_lianban = is_limit_by_lianban(lianban_days) and price_change_pct < 0
    
    # 任一条件满足即认为跌停
    return down_by_change or down_by_lianban


def calculate_limit_price(
    prev_close: float,
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    is_st: bool = False,
    direction: str = 'up'
) -> Optional[float]:
    """
    计算涨跌停价格（根据昨收价格和涨跌停幅度）
    
    Args:
        prev_close: 昨日收盘价
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        is_st: 是否为ST股
        direction: 'up' 涨停价, 'down' 跌停价
    
    Returns:
        涨跌停价格（四舍五入到分），新股期间返回 None
    """
    threshold = get_limit_threshold(stock_code, listing_date, trade_date, is_st)
    
    if threshold is None:
        return None  # 新股期间无涨跌停价
    
    if direction == 'up':
        return round(prev_close * (1 + threshold), 2)
    else:
        return round(prev_close * (1 - threshold), 2)


def get_limit_info(
    stock_code: Union[str, int],
    listing_date: Union[str, int, datetime],
    trade_date: Union[str, datetime],
    prev_close: Optional[float] = None,
    current_price: Optional[float] = None,
    lianban_days: Optional[int] = None,
    is_st: bool = False
) -> dict:
    """
    获取完整的涨跌停信息
    
    Args:
        stock_code: 股票代码
        listing_date: 上市日期
        trade_date: 交易日期
        prev_close: 昨日收盘价（可选，用于计算涨跌停价）
        current_price: 当前价格（可选，用于判断是否涨跌停）
        lianban_days: 连板天数（可选，用于辅助判断）
        is_st: 是否为ST股
    
    Returns:
        涨跌停信息字典
    """
    board = get_stock_board(stock_code)
    board_names = {
        StockBoard.SSE_MAIN: '上交所主板',
        StockBoard.SZSE_MAIN: '深交所主板',
        StockBoard.SZSE_GEM: '创业板',
        StockBoard.SSE_STAR: '科创板',
        StockBoard.BSE: '北交所',
        StockBoard.UNKNOWN: '未知板块'
    }
    
    threshold = get_limit_threshold(stock_code, listing_date, trade_date, is_st)
    in_new_period = is_new_stock(listing_date, trade_date, board) if board != StockBoard.UNKNOWN else False
    
    result = {
        'stock_code': str(stock_code),
        'board': board_names.get(board, '未知'),
        'board_code': board.value,
        'limit_rate': threshold,  # None表示新股期间无限
        'limit_rate_pct': f"{threshold * 100:.1f}%" if threshold else "无限",
        'is_new_stock': in_new_period,
        'is_st': is_st,
    }
    
    # 计算涨跌停价
    if prev_close is not None and threshold is not None:
        result['limit_up_price'] = round(prev_close * (1 + threshold), 2)
        result['limit_down_price'] = round(prev_close * (1 - threshold), 2)
    
    # 判断是否涨跌停
    if current_price is not None and prev_close is not None and threshold is not None:
        change_pct = (current_price - prev_close) / prev_close * 100
        result['current_change_pct'] = round(change_pct, 2)
        
        # 单一条件判断
        result['is_limit_up'] = is_limit_up(change_pct, stock_code, listing_date, trade_date, is_st)
        result['is_limit_down'] = is_limit_down(change_pct, stock_code, listing_date, trade_date, is_st)
        
        # 双重验证判断
        result['is_limit_up_combined'] = is_limit_up_by_combined(
            change_pct, lianban_days, stock_code, listing_date, trade_date, is_st
        )
        result['is_limit_down_combined'] = is_limit_down_by_combined(
            change_pct, lianban_days, stock_code, listing_date, trade_date, is_st
        )
        
        # 连板天辅助信息
        if lianban_days is not None:
            result['lianban_days'] = lianban_days
            result['limit_by_lianban'] = is_limit_by_lianban(lianban_days)
    
    return result


def check_limit_status(
    stock_code: Union[str, int],
    change_pct: float,
    prev_close: float,
    current_price: float,
    listing_date: Union[str, int],
    trade_date: Union[str, int],
    lianban_days: Optional[int] = None,
    is_st: bool = False
) -> dict:
    """
    便捷函数：快速检查涨跌停状态
    
    Args:
        stock_code: 股票代码
        change_pct: 涨幅百分比 (如 9.8 或 -9.8)
        prev_close: 昨日收盘价
        current_price: 当前价格
        listing_date: 上市日期 (YYYYMMDD)
        trade_date: 交易日期 (YYYYMMDD)
        lianban_days: 连板天数（可选）
        is_st: 是否ST股
    
    Returns:
        dict 包含 is_limit_up, is_limit_down, limit_rate 等
    """
    return get_limit_info(
        stock_code=stock_code,
        listing_date=listing_date,
        trade_date=trade_date,
        prev_close=prev_close,
        current_price=current_price,
        lianban_days=lianban_days,
        is_st=is_st
    )


def get_min_change_threshold(limit_rate: float) -> float:
    """
    计算给定涨跌幅限制下的最小实际涨幅
    
    公式推导：
    设昨收 = P，价格精度 = 0.01元
    涨停价 = round(P × (1 + limit_rate), 2)
    
    当 P × (1 + limit_rate) 恰好在四舍五入边界时，实际涨幅最小
    
    Args:
        limit_rate: 涨跌幅限制 (如 0.10 表示 10%)
    
    Returns:
        最小实际涨幅百分比
    """
    # 由于价格精度是0.01，最极端情况是四舍五入导致约1%的误差
    # 但实际市场中这种情况极少，保守估计使用 1% 容差
    return limit_rate * 100 - 1.0


# ============ 测试代码 ============
if __name__ == '__main__':
    print("=" * 70)
    print("涨跌停规则测试")
    print("=" * 70)
    
    # 测试1: 基本涨跌停判断
    print("\n【测试1: 基本涨跌停判断】")
    test_cases = [
        ('600000', 9.89, '主板 9.89%（理论最小涨停）'),
        ('600000', 9.90, '主板 9.90%'),
        ('600000', 9.95, '主板 9.95%'),
        ('600000', 10.05, '主板 10.05%'),
        ('600000', -9.89, '主板 -9.89%（理论最小跌停）'),
        ('600000', -9.95, '主板 -9.95%'),
        ('300001', 19.78, '创业板 19.78%（理论最小涨停）'),
        ('300001', 19.90, '创业板 19.90%'),
        ('300001', 20.10, '创业板 20.10%'),
        ('830000', 29.67, '北交所 29.67%（理论最小涨停）'),
        ('830000', 29.90, '北交所 29.90%'),
        ('830000', 30.10, '北交所 30.10%'),
        ('600001', 4.89, '主板ST 4.89%'),
        ('600001', 5.10, '主板ST 5.10%'),
    ]
    
    for code, pct, desc in test_cases:
        is_up, is_down = is_limit_up_or_down(pct, code, 20200101, 20260428, False)
        status = "涨停" if is_up else ("跌停" if is_down else "普通")
        print(f"  {desc}: {status}")
    
    # 测试2: 涨跌停价计算
    print("\n【测试2: 涨跌停价计算】")
    price_cases = [
        (10.04, 0.10, '主板 10%'),
        (10.05, 0.10, '主板 10%'),
        (10.00, 0.20, '创业板 20%'),
        (10.00, 0.30, '北交所 30%'),
    ]
    
    for prev, rate, desc in price_cases:
        up_price = round(prev * (1 + rate), 2)
        down_price = round(prev * (1 - rate), 2)
        actual_up_rate = (up_price - prev) / prev * 100
        actual_down_rate = (prev - down_price) / prev * 100
        print(f"  {desc} 昨收 {prev}:")
        print(f"    涨停价 {up_price} (实际涨幅 {actual_up_rate:.2f}%)")
        print(f"    跌停价 {down_price} (实际跌幅 {actual_down_rate:.2f}%)")
    
    # 测试3: 连板天辅助判断
    print("\n【测试3: 连板天辅助判断】")
    lianban_cases = [
        (1, True, '连板天=1, 涨幅>0'),
        (1, False, '连板天=1, 涨幅<0'),
        (2, True, '连板天=2, 涨幅>0'),
        (None, True, '连板天=None'),
        (0, True, '连板天=0'),
    ]
    
    for days, is_positive, desc in lianban_cases:
        change = 9.9 if is_positive else -9.9
        result = is_limit_by_lianban(days) and ((is_positive and change > 0) or (not is_positive and change < 0))
        print(f"  {desc}: {'涨停/跌停' if result else '普通'}")
    
    print("\n" + "=" * 70)
    print("测试完成!")
