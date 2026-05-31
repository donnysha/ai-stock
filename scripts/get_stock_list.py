"""
获取A股股票列表并存储到数据库

使用方法：
    python get_stock_list.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import akshare as ak
import pymysql
from datetime import datetime
import time
import warnings
from pathlib import Path
warnings.filterwarnings('ignore')

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG


def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


def init_table():
    """初始化表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_basic_info (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
                    stock_name VARCHAR(50) COMMENT '股票名称',
                    exchange VARCHAR(10) COMMENT '交易所(SH/SZ/BJ)',
                    market VARCHAR(10) COMMENT '市场(沪深北)',
                    stock_type VARCHAR(20) COMMENT '股票类型',
                    industry VARCHAR(100) COMMENT '所属行业',
                    list_date DATE COMMENT '上市日期',
                    total_market_cap DECIMAL(20,2) COMMENT '总市值(元)',
                    circulating_market_cap DECIMAL(20,2) COMMENT '流通市值(元)',
                    total_shares DECIMAL(20,2) COMMENT '总股本',
                    circulating_shares DECIMAL(20,2) COMMENT '流通股',
                    pe_ratio DECIMAL(10,2) COMMENT '市盈率',
                    pb_ratio DECIMAL(10,2) COMMENT '市净率',
                    listing_status VARCHAR(20) DEFAULT '上市' COMMENT '上市状态',
                    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_code (stock_code),
                    INDEX idx_name (stock_name),
                    INDEX idx_industry (industry)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票基础信息表'
            """)
            conn.commit()
        print("[OK] 表初始化完成")
    finally:
        conn.close()


def get_stock_list() -> list:
    """
    获取A股股票代码列表
    
    依次尝试多个接口
    """
    # 方法1: stock_info_a_code_name
    print("\n[1] 尝试 stock_info_a_code_name...")
    try:
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            codes = df['code'].astype(str).str.zfill(6).tolist()
            print(f"    [OK] 获取 {len(codes)} 只股票")
            return codes
    except Exception as e:
        print(f"    [FAIL] {e}")
    
    # 方法2: stock_info_a_code_name (备用)
    print("\n[2] 尝试 stock_info_sh_name_code...")
    try:
        df_sh = ak.stock_info_sh_name_code(symbol="主板A股")
        df_sz = ak.stock_info_sz_name_code(location="主板A股")
        df = pd.concat([df_sh, df_sz], ignore_index=True)
        if df is not None and not df.empty:
            codes = df['证券代码'].astype(str).str.zfill(6).tolist()
            print(f"    [OK] 获取 {len(codes)} 只股票")
            return codes
    except Exception as e:
        print(f"    [FAIL] {e}")
    
    # 方法3: 手动返回常见股票代码（备选）
    print("\n[3] 使用手动代码列表（仅演示用）...")
    sample_codes = [
        '000001', '000002', '000004', '000005', '000006',  # 平安银行、万科等
        '600000', '600016', '600019', '600028', '600030',  # 浦发银行、民生银行等
        '600036', '600048', '600050', '600104', '600109',  # 招商银行、保利等
        '688001', '688036', '688111', '688126', '688981',  # 科创板示例
    ]
    print(f"    [OK] 获取 {len(sample_codes)} 只示例股票")
    return sample_codes


def save_to_database(codes: list):
    """保存到数据库"""
    print("\n[保存] 写入数据库...")
    
    conn = get_db_connection()
    success = 0
    
    try:
        with conn.cursor() as cursor:
            for code in codes:
                code_str = str(code).zfill(6)
                
                # 判断交易所
                if code_str.startswith('6'):
                    exchange = 'SH'
                    market = '沪深'
                    stock_type = '科创板' if code_str.startswith('688') else '主板'
                elif code_str.startswith('0') or code_str.startswith('3'):
                    exchange = 'SZ'
                    market = '沪深'
                    stock_type = '创业板' if code_str.startswith('3') else '主板'
                elif code_str.startswith('4') or code_str.startswith('8'):
                    exchange = 'BJ'
                    market = '北交所'
                    stock_type = '北交所'
                else:
                    exchange = 'UNKNOWN'
                    market = '未知'
                    stock_type = '其他'
                
                try:
                    cursor.execute("""
                        INSERT IGNORE INTO stock_basic_info (stock_code, exchange, market, stock_type)
                        VALUES (%s, %s, %s, %s)
                    """, (code_str, exchange, market, stock_type))
                    success += 1
                except:
                    pass
                
                if success % 500 == 0:
                    print(f"    进度: {success}/{len(codes)}")
            
            conn.commit()
    finally:
        conn.close()
    
    print(f"    [OK] 成功写入 {success} 条记录")


def main():
    print("=" * 50)
    print("获取A股股票列表")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 初始化表
    init_table()
    
    # 获取股票列表
    codes = get_stock_list()
    
    if not codes:
        print("\n[FAIL] 获取股票列表失败")
        sys.exit(1)
    
    # 保存到数据库
    save_to_database(codes)
    
    print("\n[完成] 股票列表获取完成")
    print("下一步运行: python sync_stock_basic_full.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
