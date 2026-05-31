# =============================================================================
# 数据层模块 - 数据获取和存储
# =============================================================================
# 功能：封装数据访问逻辑，提供统一的数据接口
# 子模块：
#   - models.py: 数据模型定义
#   - akshare_data_fetcher.py: AkShare数据获取器
#   - db_connection.py: MySQL数据库连接管理
#   - query_builder.py: SQL查询构建器
# =============================================================================

from .models import StockData, KLineData, QueryResult, GridTrade, BacktestResult
from .akshare_data_fetcher import AkshareDataFetcher, akshare_fetcher
from .db_connection import DatabaseConnection, get_db_connection, execute_query, execute_update, test_connection
from .query_builder import QueryBuilder, StockQueryBuilder, QueryOperator
from .market_data_cache import MarketDataCache, market_cache, refresh_market_data, get_cached_gainers, get_cached_losers, get_cached_volume, get_cached_all_stocks

__all__ = [
    # 数据模型
    'StockData',         # 股票基础数据模型
    'KLineData',         # K线数据模型
    'QueryResult',       # 查询结果封装
    'GridTrade',         # 网格交易记录
    'BacktestResult',    # 回测结果
    
    # AkShare数据获取器
    'AkshareDataFetcher',    # 数据获取器类
    'akshare_fetcher',      # 全局单例实例
    
    # 数据库连接
    'DatabaseConnection',    # 数据库连接管理类
    'get_db_connection',    # 获取全局连接实例
    'execute_query',        # 快捷查询函数
    'execute_update',       # 快捷更新函数
    'test_connection',     # 测试连接函数
    
    # 查询构建器
    'QueryBuilder',         # 通用查询构建器
    'StockQueryBuilder',   # 股票专用查询构建器
    'QueryOperator',        # 查询操作符枚举
    
    # 市场数据缓存
    'MarketDataCache',      # 市场数据缓存管理器
    'market_cache',         # 全局缓存实例
    'refresh_market_data',  # 刷新市场数据函数
    'get_cached_gainers',   # 获取缓存涨幅榜
    'get_cached_losers',    # 获取缓存跌幅榜
    'get_cached_volume',    # 获取缓存成交额榜
    'get_cached_all_stocks' # 获取缓存全部股票
]
