"""简单的股票数据同步测试"""
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

def main():
    print("=" * 50)
    print("股票基本信息同步测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 1. 创建表
    print("\n[1] 创建表...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("    [OK] 表已创建或已存在")
    finally:
        conn.close()
    
    # 2. 获取股票数据
    print("\n[2] 从akshare获取数据...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"    尝试 {attempt + 1}/{max_retries}...")
            df = ak.stock_zh_a_spot_em()
            print(f"    [OK] 获取到 {len(df)} 只股票")
            break
        except Exception as e:
            print(f"    [FAIL] 失败: {e}")
            if attempt < max_retries - 1:
                print("    等待 5 秒后重试...")
                time.sleep(5)
            else:
                print("    所有尝试失败，退出")
                return
    
    if df.empty:
        print("    [FAIL] 数据为空")
        return
    
    # 3. 处理数据
    print("\n[3] 处理数据...")
    result = pd.DataFrame()
    result['stock_code'] = df['代码'].astype(str).str.zfill(6)
    result['stock_name'] = df['名称'].astype(str)
    
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
    result['industry'] = None
    result['full_name'] = None
    result['list_date'] = None
    
    print(f"    处理完成: {len(result)} 条记录")
    print(f"    示例数据:")
    print(result.head(3).to_string())
    
    # 4. 同步到数据库
    print("\n[4] 同步到数据库...")
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
                        row['industry'],
                        row['full_name'],
                        row['list_date']
                    ))
                    success += 1
                    if (i + 1) % 500 == 0:
                        print(f"    已处理 {i + 1}/{len(result)}...")
                except Exception as e:
                    if success < 5:
                        print(f"    插入失败 {row['stock_code']}: {e}")
            
            conn.commit()
            print(f"    [OK] 成功插入 {success} 条记录")
    finally:
        conn.close()
    
    # 5. 验证结果
    print("\n[5] 验证结果...")
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
            total = cursor.fetchone()[0]
            print(f"    总记录数: {total}")
            
            cursor.execute("SELECT exchange, COUNT(*) as cnt FROM stock_basic_info GROUP BY exchange")
            for row in cursor.fetchall():
                print(f"    {row[0]}: {row[1]}")
    finally:
        conn.close()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

if __name__ == "__main__":
    main()
