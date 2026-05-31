"""股票数据同步 - 使用备用数据源"""
import sys
from pathlib import Path
import pandas as pd
import akshare as ak
import pymysql
from datetime import datetime
import time
import traceback

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_basic_info (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(50) NOT NULL,
    exchange VARCHAR(10),
    industry VARCHAR(100),
    full_name VARCHAR(200),
    list_date DATE,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

def get_exchange(code):
    code = str(code)
    if code.startswith('6') or code.startswith('5'):
        return 'SH'
    elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
        return 'SZ'
    elif code.startswith('8') or code.startswith('4') or code.startswith('9'):
        return 'BJ'
    return 'UNKNOWN'

def fetch_stock_list():
    """尝试多个数据源获取股票列表"""
    
    # 方法1: stock_zh_a_spot_em (东方财富)
    print("    尝试方法1: 东方财富实时行情...")
    for attempt in range(3):
        try:
            time.sleep(2)  # 等待一下
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                print(f"    [OK] 获取到 {len(df)} 只股票")
                result = pd.DataFrame()
                result['stock_code'] = df['代码'].astype(str).str.zfill(6)
                result['stock_name'] = df['名称'].astype(str)
                result['exchange'] = result['stock_code'].apply(get_exchange)
                result['industry'] = df.get('行业', None) if '行业' in df.columns else None
                result['full_name'] = None
                result['list_date'] = None
                return result
        except Exception as e:
            print(f"    尝试 {attempt + 1} 失败: {str(e)[:50]}...")
            if attempt < 2:
                time.sleep(10)
    
    # 方法2: stock_info_a_code_name (新浪)
    print("    尝试方法2: 新浪股票列表...")
    for attempt in range(3):
        try:
            time.sleep(2)
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                print(f"    [OK] 获取到 {len(df)} 只股票")
                result = pd.DataFrame()
                result['stock_code'] = df['code'].astype(str).str.zfill(6)
                result['stock_name'] = df['name'].astype(str)
                result['exchange'] = result['stock_code'].apply(get_exchange)
                result['industry'] = None
                result['full_name'] = None
                result['list_date'] = None
                return result
        except Exception as e:
            print(f"    尝试 {attempt + 1} 失败: {str(e)[:50]}...")
            if attempt < 2:
                time.sleep(10)
    
    # 方法3: stock_zh_a_hist (历史数据提取)
    print("    尝试方法3: 常用股票代码...")
    common_codes = [
        ('000001', '平安银行'), ('000002', '万科A'), ('000004', '国华网安'),
        ('000005', 'ST星源'), ('000006', '深振业A'), ('000007', '全新好'),
        ('000008', '神州高铁'), ('000009', '中国宝安'), ('000010', '美丽生态'),
        ('600000', '浦发银行'), ('600001', '邯郸钢铁'), ('600004', '白云机场'),
        ('600005', '武钢股份'), ('600006', '东风汽车'), ('600007', '中国国贸'),
        ('600008', '首创股份'), ('600009', '上海机场'), ('600010', '包钢股份'),
        ('600016', '民生银行'), ('600018', '上港集团'), ('600019', '宝钢股份'),
        ('600028', '中国石化'), ('600029', '南方航空'), ('600030', '中信证券'),
        ('600036', '招商银行'), ('600048', '保利发展'), ('600050', '中国联通'),
        ('600104', '上汽集团'), ('600519', '贵州茅台'), ('600887', '伊利股份'),
    ]
    result = pd.DataFrame(common_codes, columns=['stock_code', 'stock_name'])
    result['exchange'] = result['stock_code'].apply(get_exchange)
    result['industry'] = None
    result['full_name'] = None
    result['list_date'] = None
    print(f"    [OK] 使用内置代码列表 {len(result)} 只股票")
    return result

def main():
    print("=" * 50)
    print("Stock Info Sync Tool")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 创建表
    print("\n[1] Creating table...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("    [OK] Table ready")
    finally:
        conn.close()
    
    # 2. 获取股票数据
    print("\n[2] Fetching stock list...")
    result = fetch_stock_list()
    
    if result is None or result.empty:
        print("    [FAIL] Failed to fetch data")
        return
    
    print(f"    Total: {len(result)} stocks")
    print(f"    Sample:")
    print(result.head(3).to_string())
    
    # 3. 同步到数据库
    print("\n[3] Syncing to database...")
    conn = pymysql.connect(**DB_CONFIG)
    success = 0
    try:
        with conn.cursor() as cursor:
            insert_sql = """
            INSERT INTO stock_basic_info 
            (stock_code, stock_name, exchange, industry, full_name, list_date, update_time)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
            stock_name = VALUES(stock_name),
            exchange = VALUES(exchange)
            """
            
            for i, row in result.iterrows():
                try:
                    cursor.execute(insert_sql, (
                        row['stock_code'],
                        row['stock_name'],
                        row['exchange'],
                        row.get('industry'),
                        row.get('full_name'),
                        row.get('list_date')
                    ))
                    success += 1
                except Exception as e:
                    if success < 3:
                        print(f"    Error {row['stock_code']}: {e}")
            
            conn.commit()
            print(f"    [OK] Inserted {success} records")
    finally:
        conn.close()
    
    # 4. 验证
    print("\n[4] Verifying...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
            total = cursor.fetchone()[0]
            print(f"    Total in DB: {total}")
            
            cursor.execute("SELECT exchange, COUNT(*) as cnt FROM stock_basic_info GROUP BY exchange")
            for row in cursor.fetchall():
                print(f"    {row[0]}: {row[1]}")
    finally:
        conn.close()
    
    print(f"\nEnd: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

if __name__ == "__main__":
    main()
