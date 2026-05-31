"""
市场数据轮询刷新脚本

【功能】
每30分钟从akshare拉取实时行情数据，刷新 market_snapshot 和 market_rank_cache 两张表。

【使用方式】
1. 前台运行: python scripts/poll_market_data.py
2. 后台运行: pythonw scripts/poll_market_data.py  (Windows无窗口)

【轮询规则】
- 交易日盘前（9:00-9:30）：预热，每30分钟拉一次
- 交易时段（9:30-11:30, 13:00-15:00）：每30分钟拉一次
- 盘后（15:00-15:30）：最后一次拉取收盘数据
- 非交易时段：暂停轮询，等待次日
"""

import sys
import time
import signal
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai_stock_nlp.data_layer.market_data_cache import market_cache

# ==================== 配置 ====================
POLL_INTERVAL_SECONDS = 30 * 60  # 30分钟
MARKET_OPEN_MORNING = dt_time(9, 30)
MARKET_CLOSE_MORNING = dt_time(11, 30)
MARKET_OPEN_AFTERNOON = dt_time(13, 0)
MARKET_CLOSE_AFTERNOON = dt_time(15, 0)
PRE_MARKET_START = dt_time(9, 0)
POST_MARKET_END = dt_time(15, 0)  # API 收盘即停服，15:00 后不可用

# 周末不运行
WEEKEND_DAYS = {5, 6}  # 周六=5, 周日=6

_is_running = True


def signal_handler(sig, frame):
    """处理退出信号"""
    global _is_running
    print(f"\n[{datetime.now()}] 收到退出信号，正在停止...")
    _is_running = False


def is_trading_time() -> bool:
    """
    判断当前是否在有效运行时段内
    盘前30分钟 ~ 盘后30分钟
    """
    now = datetime.now()

    # 周末跳过
    if now.weekday() in WEEKEND_DAYS:
        return False

    current_time = now.time()

    # 盘前预热（9:00 ~ 9:30）
    if PRE_MARKET_START <= current_time < MARKET_OPEN_MORNING:
        return True

    # 上午交易时段（9:30 ~ 11:30）
    if MARKET_OPEN_MORNING <= current_time <= MARKET_CLOSE_MORNING:
        return True

    # 午间休市（11:30 ~ 13:00）不刷新
    # 下午交易时段（13:00 ~ 15:00）
    if MARKET_OPEN_AFTERNOON <= current_time <= MARKET_CLOSE_AFTERNOON:
        return True

    # 盘后收尾（15:00 ~ 15:30）
    if MARKET_CLOSE_AFTERNOON < current_time <= POST_MARKET_END:
        return True

    return False


def wait_for_next_trading_day():
    """等到下一个有效运行时段"""
    now = datetime.now()
    current_time = now.time()

    # 如果当前在有效时段内，直接返回
    if is_trading_time():
        return

    # 如果今天营业，但当前不在有效时段
    if now.weekday() not in WEEKEND_DAYS:
        # 判断是在盘前还是盘后
        if current_time < PRE_MARKET_START:
            wait_seconds = (datetime.combine(now.date(), PRE_MARKET_START) - now).total_seconds()
            next_time = datetime.combine(now.date(), PRE_MARKET_START)
        elif current_time > POST_MARKET_END:
            # 等明天
            next_day = now.date() + timedelta(days=1)
            while next_day.weekday() in WEEKEND_DAYS:
                next_day += timedelta(days=1)
            next_time = datetime.combine(next_day, PRE_MARKET_START)
            wait_seconds = (next_time - now).total_seconds()
        else:
            # 不应出现的情况，直接等30分钟重试
            wait_seconds = POLL_INTERVAL_SECONDS
            next_time = now + timedelta(seconds=wait_seconds)
    else:
        # 周末，等到下周一
        next_day = now.date() + timedelta(days=1)
        while next_day.weekday() in WEEKEND_DAYS:
            next_day += timedelta(days=1)
        next_time = datetime.combine(next_day, PRE_MARKET_START)
        wait_seconds = (next_time - now).total_seconds()

    hours = int(wait_seconds // 3600)
    minutes = int((wait_seconds % 3600) // 60)
    print(f"[{now}] 当前非交易时段，将在 {hours}小时{minutes}分钟后 ({next_time}) 恢复轮询")
    time.sleep(min(wait_seconds, 3600))  # 最多睡1小时后重新检查


def do_refresh():
    """执行一次数据刷新"""
    print(f"\n{'='*50}")
    print(f"[{datetime.now()}] 开始刷新市场数据 (snapshot + rank_cache)...")

    success = market_cache.refresh_market_data()

    if success:
        status = market_cache.get_cache_status()
        print(f"[{datetime.now()}] 刷新成功！共 {status['stock_count']} 只股票")
    else:
        print(f"[{datetime.now()}] 刷新失败！将在下次间隔重试")

    print(f"{'='*50}\n")
    return success


def main():
    """主循环"""
    global _is_running

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("=" * 60)
    print("  市场数据轮询刷新服务已启动")
    print(f"  轮询间隔: {POLL_INTERVAL_SECONDS // 60} 分钟")
    print(f"  有效时段: 交易日 9:00 ~ 15:00")
    print(f"  刷新目标: market_snapshot + market_rank_cache")
    print("  Ctrl+C 停止服务")
    print("=" * 60)

    # 启动时立即刷新一次
    if is_trading_time():
        do_refresh()
    else:
        print(f"[{datetime.now()}] 当前非交易时段，跳过首次刷新")

    # 主循环
    while _is_running:
        # 检查是否在有效时段
        if not is_trading_time():
            wait_for_next_trading_day()
            continue

        # 等待轮询间隔
        for _ in range(POLL_INTERVAL_SECONDS):
            if not _is_running:
                break
            time.sleep(1)

        if not _is_running:
            break

        # 再次确认在有效时段（可能在睡眠中过了时段）
        if is_trading_time():
            do_refresh()
        else:
            print(f"[{datetime.now()}] 已进入非交易时段")


if __name__ == "__main__":
    main()
