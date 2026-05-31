"""
市场数据刷新脚本

【功能】
从akshare获取实时市场数据并存入数据库缓存

【使用方式】
1. 直接运行: python scripts/refresh_market_data.py
2. 定时任务: 每5分钟运行一次

【定时任务配置】
Linux crontab:
    */5 * * * * cd /path/to/project && python scripts/refresh_market_data.py

Windows 任务计划程序:
    每5分钟运行一次
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ai_stock_nlp.data_layer.market_data_cache import market_cache
from datetime import datetime


def main():
    """主函数"""
    print(f"[{datetime.now()}] 开始刷新市场数据...")
    
    # 检查缓存是否仍有效（5分钟内）
    if market_cache.is_cache_valid(max_age_minutes=5):
        status = market_cache.get_cache_status()
        print(f"缓存仍有效，上次更新: {status['last_update']}")
        return
    
    # 刷新数据
    success = market_cache.refresh_market_data()
    
    if success:
        status = market_cache.get_cache_status()
        print(f"刷新成功！共 {status['stock_count']} 只股票")
    else:
        print("刷新失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
