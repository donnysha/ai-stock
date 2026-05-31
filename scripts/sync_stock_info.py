"""
股票基本信息同步脚本

功能：
1. 从akshare获取A股基础信息（代码、名称、交易所、行业、上市日期等）
2. 同步到本地MySQL数据库的 stock_basic_info 表

使用方法：
    python sync_stock_info.py

依赖：
    pip install akshare pandas pymysql
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import akshare as ak
import pymysql
from datetime import datetime
import time
import sys
from pathlib import Path

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG

# ============== 建表SQL ==============
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_basic_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) NOT NULL COMMENT '股票名称',
    exchange VARCHAR(10) COMMENT '交易所(SH/SZ/BJ)',
    industry VARCHAR(100) COMMENT '所属行业',
    full_name VARCHAR(200) COMMENT '公司全称',
    list_date DATE COMMENT '上市日期',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_code (stock_code),
    INDEX idx_name (stock_name),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表';
"""


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def init_table():
    """初始化表结构"""
    print("[1/3] 初始化数据库表...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("    [OK] 表结构就绪")
    finally:
        conn.close()


def fetch_stock_list_from_akshare(max_retries=5) -> pd.DataFrame:
    """从akshare获取A股实时行情"""
    import requests
    
    for attempt in range(max_retries):
        try:
            print(f"\n[2/3] 获取A股列表 (尝试 {attempt + 1}/{max_retries})...")
            
            # 获取实时行情，增加超时时间
            df = ak.stock_zh_a_spot_em()
            
            if df.empty:
                print("    ⚠ 获取到空数据")
                time.sleep(3)
                continue
            
            print(f"    [OK] 成功获取 {len(df)} 只股票")
            
            # 处理数据
            result = pd.DataFrame()
            result['stock_code'] = df['代码'].astype(str).str.zfill(6)
            result['stock_name'] = df['名称'].astype(str)
            
            # 判断交易所
            def get_exchange(code):
                code = str(code)
                if code.startswith('6') or code.startswith('5'):
                    return 'SH'
                elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
                    return 'SZ'
                elif code.startswith('8') or code.startswith('4') or code.startswith('9'):
                    return 'BJ'
                return 'UNKNOWN'
            
            result['exchange'] = result['stock_code'].apply(get_exchange)
            
            # 尝试获取行业信息
            if '行业' in df.columns:
                result['industry'] = df['行业'].astype(str)
            else:
                result['industry'] = None
            
            result['full_name'] = None
            result['list_date'] = None
            
            return result
            
        except Exception as e:
            print(f"    [FAIL] 获取失败: {e}")
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)  # 更长的等待时间
                print(f"    等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
    
    return pd.DataFrame()


def fetch_list_dates_batch(codes: list, max_retries=3) -> dict:
    """批量获取上市日期"""
    list_dates = {}
    total = len(codes)
    
    print(f"\n    正在获取上市日期... (共 {total} 只)")
    
    for i, code in enumerate(codes):
        if i % 100 == 0:
            print(f"    进度: {i}/{total} ({i*100//total}%)")
        
        for attempt in range(max_retries):
            try:
                df = ak.stock_individual_info_em(symbol=code)
                if not df.empty:
                    # 查找上市时间
                    for _, row in df.iterrows():
                        if '上市' in str(row.get('item', '')):
                            date_str = str(row['value'])
                            # 格式化日期
                            if len(date_str) == 8 and date_str.isdigit():
                                list_dates[code] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                            elif '-' in date_str or '/' in date_str:
                                list_dates[code] = date_str.replace('/', '-')
                            break
                break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                continue
        
        # 控制请求频率
        if i % 10 == 0:
            time.sleep(0.3)
    
    print(f"    [OK] 成功获取 {len(list_dates)} 只股票的上市日期")
    return list_dates


def sync_to_database(df: pd.DataFrame, list_dates: dict):
    """同步数据到数据库"""
    print("\n[3/3] 同步数据到数据库...")
    
    if df.empty:
        print("    ⚠ 没有数据需要同步")
        return
    
    conn = get_db_connection()
    success_count = 0
    error_count = 0
    
    try:
        with conn.cursor() as cursor:
            insert_sql = """
            INSERT INTO stock_basic_info 
            (stock_code, stock_name, exchange, industry, full_name, list_date, update_time)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
            stock_name = VALUES(stock_name),
            exchange = VALUES(exchange),
            industry = VALUES(industry),
            list_date = COALESCE(VALUES(list_date), list_date),
            update_time = NOW()
            """
            
            for _, row in df.iterrows():
                try:
                    list_date = list_dates.get(row['stock_code'])
                    
                    cursor.execute(insert_sql, (
                        row['stock_code'],
                        row['stock_name'],
                        row['exchange'],
                        row['industry'] if pd.notna(row['industry']) else None,
                        row['full_name'],
                        list_date
                    ))
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 5:
                        print(f"    ⚠ 插入 {row['stock_code']} 失败: {e}")
            
            conn.commit()
    
    finally:
        conn.close()
    
    print(f"    [OK] 成功插入/更新 {success_count} 条记录")
    if error_count > 0:
        print(f"    ⚠ 失败 {error_count} 条")


def show_stats():
    """显示数据库统计信息"""
    print("\n" + "=" * 50)
    print("数据库统计")
    print("=" * 50)
    
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 总数
            cursor.execute("SELECT COUNT(*) as total FROM stock_basic_info")
            total = cursor.fetchone()['total']
            
            # 各交易所数量
            cursor.execute("""
                SELECT exchange, COUNT(*) as count 
                FROM stock_basic_info 
                GROUP BY exchange 
                ORDER BY count DESC
            """)
            exchanges = cursor.fetchall()
            
            # 有上市日期的数量
            cursor.execute("SELECT COUNT(*) as count FROM stock_basic_info WHERE list_date IS NOT NULL")
            with_date = cursor.fetchone()['count']
            
            print(f"总股票数: {total}")
            print(f"有上市日期: {with_date} ({with_date*100//total}%)")
            print("各交易所:")
            for ex in exchanges:
                print(f"  - {ex['exchange']}: {ex['count']}")
                
    finally:
        conn.close()


def main():
    print("=" * 50)
    print("股票基本信息同步工具")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 初始化表
    init_table()
    
    # 获取股票列表
    df = fetch_stock_list_from_akshare()
    
    if df.empty:
        print("\n[FAIL] 获取数据失败，请检查网络连接")
        sys.exit(1)
    
    # 批量获取上市日期（可选，跳过以加快速度）
    # list_dates = fetch_list_dates_batch(df['stock_code'].tolist())
    list_dates = {}  # 留空，使用增量更新
    
    # 同步到数据库
    sync_to_database(df, list_dates)
    
    # 显示统计
    show_stats()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


if __name__ == "__main__":
    main()
