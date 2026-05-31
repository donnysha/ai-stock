"""
股票基础信息同步模块

【功能说明】
1. 从akshare获取A股基础信息（代码、名称、交易所、行业等）
2. 同步到本地MySQL数据库
3. 提供股票名称查询接口

【表结构】
- stock_code: 股票代码（6位数字）
- stock_name: 股票名称
- exchange: 交易所（SH/SZ/BJ）
- industry: 所属行业
- full_name: 公司全称
- list_date: 上市日期
"""

import pandas as pd
import akshare as ak
from typing import Optional, Dict, List
from datetime import datetime
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data_layer.db_connection import get_db_connection, execute_query, execute_update


# 建表SQL (扩充版)
CREATE_STOCK_INFO_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_basic_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) NOT NULL COMMENT '股票名称',
    exchange VARCHAR(10) COMMENT '交易所(SH/SZ/BJ)',
    market VARCHAR(10) COMMENT '市场(沪深北)',
    stock_type VARCHAR(20) COMMENT '股票类型(主板/创业板/科创板/北交所)',
    industry VARCHAR(100) COMMENT '所属行业',
    list_date DATE COMMENT '上市日期',
    total_market_cap DECIMAL(20,2) COMMENT '总市值(元)',
    circulating_market_cap DECIMAL(20,2) COMMENT '流通市值(元)',
    pe_ratio DECIMAL(10,2) COMMENT '市盈率',
    pb_ratio DECIMAL(10,2) COMMENT '市净率',
    listing_status VARCHAR(20) DEFAULT '上市' COMMENT '上市状态',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_code (stock_code),
    INDEX idx_name (stock_name),
    INDEX idx_industry (industry),
    INDEX idx_exchange (exchange),
    INDEX idx_market_cap (total_market_cap)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';
"""


def init_stock_info_table():
    """初始化股票基础信息表"""
    try:
        execute_update(CREATE_STOCK_INFO_TABLE_SQL)
        print("[OK] Stock basic info table initialized")
        return True
    except Exception as e:
        print(f"✗ 初始化表失败: {e}")
        return False


def fetch_stock_info_from_akshare(max_retries: int = 3) -> pd.DataFrame:
    """
    从akshare获取A股基础信息（包含上市日期）
    
    Args:
        max_retries: 最大重试次数
    
    Returns:
        DataFrame包含股票基础信息
    """
    import time
    
    for attempt in range(max_retries):
        try:
            print(f"正在获取A股列表 (尝试 {attempt + 1}/{max_retries})...")
            
            # 1. 获取A股实时行情（包含代码和名称）
            spot_df = ak.stock_zh_a_spot_em()
            
            if spot_df.empty:
                print("获取到空数据，重试...")
                time.sleep(2)
                continue
            
            print(f"成功获取 {len(spot_df)} 只股票的实时行情")
            
            # 处理列名，保留英文字段
            result = pd.DataFrame()
            result['stock_code'] = spot_df['代码'].astype(str)
            result['stock_name'] = spot_df['名称'].astype(str)
            
            # 根据代码前缀判断交易所
            def get_exchange(code):
                if code.startswith('6') or code.startswith('5'):
                    return 'SH'
                elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
                    return 'SZ'
                elif code.startswith('8') or code.startswith('4'):
                    return 'BJ'
                return 'UNKNOWN'
            
            result['exchange'] = result['stock_code'].apply(get_exchange)
            
            # 尝试获取行业和上市日期
            result['industry'] = None
            result['full_name'] = None
            result['list_date'] = None
            
            return result
            
        except Exception as e:
            print(f"获取失败: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print("已达到最大重试次数，获取失败")
    
    return pd.DataFrame()


def get_list_date_from_akshare(stock_code: str, max_retries: int = 3) -> Optional[str]:
    """
    从akshare获取指定股票的上市日期
    
    Args:
        stock_code: 股票代码
        max_retries: 最大重试次数
    
    Returns:
        上市日期字符串(YYYY-MM-DD)，获取失败返回None
    """
    import time
    
    for attempt in range(max_retries):
        try:
            # 尝试通用接口（最稳定）
            df = ak.stock_individual_info_em(symbol=stock_code)
            if not df.empty:
                list_date_row = df[df['item'] == '上市时间']
                if not list_date_row.empty:
                    date_value = str(list_date_row.iloc[0]['value'])
                    # 格式化为 YYYY-MM-DD
                    if len(date_value) == 8 and date_value.isdigit():
                        return f"{date_value[:4]}-{date_value[4:6]}-{date_value[6:]}"
                    return date_value
            
            # 根据交易所选择专用接口
            if stock_code.startswith('6'):
                # 上海主板
                df = ak.stock_info_sh_name_code(symbol="主板A股")
                result = df[df['证券代码'].astype(str) == stock_code]
                if not result.empty:
                    return str(result.iloc[0].get('上市日期'))
            elif stock_code.startswith('0') or stock_code.startswith('3'):
                # 深圳
                df = ak.stock_info_sz_name_code(location="主板A股")
                result = df[df['证券代码'].astype(str) == stock_code]
                if not result.empty:
                    return str(result.iloc[0].get('上市日期'))
            elif stock_code.startswith('8') or stock_code.startswith('4'):
                # 北交所/新三板
                df = ak.stock_info_bj_name_code()
                result = df[df['证券代码'].astype(str) == stock_code]
                if not result.empty:
                    return str(result.iloc[0].get('上市日期'))
            
            return None
            
        except Exception as e:
            print(f"获取 {stock_code} 上市日期失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return None


def sync_stock_info_to_db(force_full: bool = False) -> bool:
    """
    同步股票基础信息到数据库
    
    Args:
        force_full: 是否强制全量更新（默认增量）
    
    Returns:
        同步是否成功
    """
    try:
        print("正在从akshare获取股票基础信息...")
        df = fetch_stock_info_from_akshare()
        
        if df.empty:
            print("✗ 未获取到数据")
            return False
        
        print(f"获取到 {len(df)} 只股票信息")
        
        # 清空表（全量更新）
        if force_full:
            execute_update("TRUNCATE TABLE stock_basic_info")
            print("已清空旧数据")
        
        # 插入或更新数据
        insert_sql = """
        INSERT INTO stock_basic_info 
        (stock_code, stock_name, exchange, market, stock_type, industry, list_date, update_time)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON DUPLICATE KEY UPDATE
        stock_name = VALUES(stock_name),
        exchange = VALUES(exchange),
        market = VALUES(market),
        stock_type = VALUES(stock_type),
        industry = VALUES(industry),
        update_time = NOW()
        """
        
        count = 0
        for _, row in df.iterrows():
            try:
                execute_update(insert_sql, (
                    row['stock_code'],
                    row['stock_name'],
                    row['exchange'],
                    row['industry'],
                    row['full_name'],
                    row['list_date']
                ))
                count += 1
            except Exception as e:
                print(f"Insert {row['stock_code']} failed: {e}")
        
        print(f"[OK] Synced {count} stocks")
        return True
        
    except Exception as e:
        print(f"✗ 同步失败: {e}")
        return False


def get_stock_name_from_db(stock_code: str) -> Optional[str]:
    """
    从数据库获取股票名称
    
    Args:
        stock_code: 6位股票代码
    
    Returns:
        股票名称，不存在返回None
    """
    try:
        result = execute_query(
            "SELECT stock_name FROM stock_basic_info WHERE stock_code = %s",
            (stock_code,)
        )
        if result:
            return result[0]['stock_name']
        return None
    except Exception as e:
        print(f"查询股票名称失败: {e}")
        return None


def get_stock_info_from_db(stock_code: str) -> Optional[Dict]:
    """
    从数据库获取股票完整信息
    
    Args:
        stock_code: 6位股票代码
    
    Returns:
        股票信息字典
    """
    try:
        result = execute_query(
            "SELECT * FROM stock_basic_info WHERE stock_code = %s",
            (stock_code,)
        )
        if result:
            return result[0]
        return None
    except Exception as e:
        print(f"查询股票信息失败: {e}")
        return None


def get_list_date_from_db(stock_code: str) -> Optional[str]:
    """
    从数据库获取股票上市日期
    
    Args:
        stock_code: 6位股票代码
    
    Returns:
        上市日期字符串(YYYY-MM-DD)，不存在返回None
    """
    try:
        result = execute_query(
            "SELECT list_date FROM stock_basic_info WHERE stock_code = %s",
            (stock_code,)
        )
        if result and result[0]['list_date']:
            # 转换为字符串格式
            list_date = result[0]['list_date']
            if isinstance(list_date, str):
                return list_date
            else:
                return list_date.strftime('%Y-%m-%d')
        return None
    except Exception as e:
        print(f"查询上市日期失败: {e}")
        return None


def get_or_fetch_list_date(stock_code: str, akshare_fetcher=None) -> Optional[str]:
    """
    获取股票上市日期（先查库，没有则联网获取并存入数据库）
    
    Args:
        stock_code: 6位股票代码
        akshare_fetcher: 数据获取器（用于备用方案）
    
    Returns:
        上市日期字符串(YYYY-MM-DD)
    """
    # 先查数据库
    list_date = get_list_date_from_db(stock_code)
    if list_date:
        return list_date
    
    # 联网获取
    print(f"数据库中没有 {stock_code} 的上市日期，正在从网络获取...")
    list_date = get_list_date_from_akshare(stock_code)
    
    # 如果联网获取失败，尝试从K线数据推断
    if not list_date and akshare_fetcher:
        try:
            print(f"尝试从K线数据获取 {stock_code} 的最早交易日期...")
            # 获取较长时间范围的数据（缩小范围以降低失败率）
            from datetime import date as dt_date, timedelta as dt_timedelta
            today_str = dt_date.today().strftime('%Y%m%d')
            df = akshare_fetcher.get_kline_dataframe(stock_code, '20000101', today_str)
            if df is not None and not df.empty:
                # 获取最早的日期（get_kline_dataframe已将"日期"重命名为"date"）
                if 'date' in df.columns:
                    earliest_date = df['date'].min()
                elif '日期' in df.columns:
                    earliest_date = df['日期'].min()
                elif 'trade_date' in df.columns:
                    earliest_date = df['trade_date'].min()
                else:
                    earliest_date = df.index.min()
                
                # 格式化日期
                if hasattr(earliest_date, 'strftime'):
                    list_date = earliest_date.strftime('%Y-%m-%d')
                else:
                    list_date = str(earliest_date)[:10]
                print(f"从K线数据推断 {stock_code} 的上市日期约为: {list_date}")
        except Exception as e:
            print(f"从K线数据获取上市日期失败: {e}")
    
    if list_date:
        # 更新到数据库
        try:
            # 确保股票记录在表中
            stock_name = get_stock_name_from_db(stock_code)
            if not stock_name:
                # 如果股票不在表中，先插入基础记录
                execute_update(
                    """INSERT INTO stock_basic_info (stock_code, stock_name, list_date) 
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE list_date = VALUES(list_date)""",
                    (stock_code, stock_code, list_date)
                )
            else:
                execute_update(
                    "UPDATE stock_basic_info SET list_date = %s WHERE stock_code = %s",
                    (list_date, stock_code)
                )
            print(f"已更新 {stock_code} 的上市日期: {list_date}")
        except Exception as e:
            print(f"更新上市日期到数据库失败: {e}")
    
    return list_date


def search_stocks_by_name(keyword: str, limit: int = 20) -> List[Dict]:
    """
    根据名称关键字搜索股票
    
    Args:
        keyword: 搜索关键字
        limit: 返回数量限制
    
    Returns:
        股票列表
    """
    try:
        result = execute_query(
            """SELECT stock_code, stock_name, exchange, market, stock_type, industry, 
                      total_market_cap, circulating_market_cap, pe_ratio, pb_ratio
               FROM stock_basic_info 
               WHERE stock_name LIKE %s OR stock_code LIKE %s
               LIMIT %s""",
            (f'%{keyword}%', f'%{keyword}%', limit)
        )
        return result
    except Exception as e:
        print(f"搜索股票失败: {e}")
        return []


def get_all_stock_codes() -> List[str]:
    """获取所有股票代码列表"""
    try:
        result = execute_query("SELECT stock_code FROM stock_basic_info")
        return [r['stock_code'] for r in result]
    except Exception as e:
        print(f"获取股票代码列表失败: {e}")
        return []


def get_stocks_by_market_cap(min_cap: float = None, max_cap: float = None, 
                              stock_type: str = None, limit: int = 1000) -> List[Dict]:
    """
    根据市值范围筛选股票
    
    Args:
        min_cap: 最小市值(亿元)，None表示不限
        max_cap: 最大市值(亿元)，None表示不限
        stock_type: 股票类型筛选(主板/创业板/科创板/北交所)
        limit: 返回数量限制
    
    Returns:
        股票列表
    """
    try:
        conditions = []
        params = []
        
        # 市值筛选（数据库存储的是元，需要转换为亿元比较）
        if min_cap is not None:
            conditions.append("total_market_cap >= %s")
            params.append(min_cap * 100000000)  # 亿元转元
        if max_cap is not None:
            conditions.append("total_market_cap <= %s")
            params.append(max_cap * 100000000)
        
        # 股票类型筛选
        if stock_type:
            conditions.append("stock_type = %s")
            params.append(stock_type)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        sql = f"""
            SELECT stock_code, stock_name, exchange, stock_type, industry,
                   total_market_cap, circulating_market_cap, pe_ratio, pb_ratio
            FROM stock_basic_info 
            WHERE {where_clause}
            ORDER BY total_market_cap DESC
            LIMIT %s
        """
        
        result = execute_query(sql, params)
        return result
    except Exception as e:
        print(f"按市值筛选股票失败: {e}")
        return []


if __name__ == "__main__":
    # 初始化表并同步数据
    print("=" * 50)
    print("股票基础信息同步工具")
    print("=" * 50)
    
    # 初始化表
    init_stock_info_table()
    
    # 同步数据
    sync_stock_info_to_db(force_full=True)
    
    # 测试查询
    print("\n测试查询：")
    name = get_stock_name_from_db("000001")
    print(f"000001 名称: {name}")
