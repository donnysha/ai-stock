"""
股票基础信息同步脚本 (东方财富接口)

使用 stock_individual_info_em 获取个股详细信息：
- 总股本、流通股
- 总市值、流通市值
- 行业
- 上市时间

使用方法：
    python sync_stock_basic_full.py

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
import warnings
import os
from pathlib import Path
warnings.filterwarnings('ignore')

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG

# ============== 代理配置（可选）==============
PROXY = os.getenv('HTTP_PROXY') or os.getenv('HTTPS_PROXY')


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def init_table():
    """初始化表结构"""
    print("[1/4] 初始化数据库表...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查现有字段
            cursor.execute("DESCRIBE stock_basic_info")
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            # 需要添加的字段
            new_columns = {
                'market': "VARCHAR(10) COMMENT '市场(沪深北)'",
                'stock_type': "VARCHAR(20) COMMENT '股票类型(主板/创业板/科创板/北交所)'",
                'total_market_cap': "DECIMAL(20,2) COMMENT '总市值(元)'",
                'circulating_market_cap': "DECIMAL(20,2) COMMENT '流通市值(元)'",
                'total_shares': "DECIMAL(20,2) COMMENT '总股本'",
                'circulating_shares': "DECIMAL(20,2) COMMENT '流通股'",
                'pe_ratio': "DECIMAL(10,2) COMMENT '市盈率'",
                'pb_ratio': "DECIMAL(10,2) COMMENT '市净率'"
            }
            
            for col_name, col_def in new_columns.items():
                if col_name not in existing_columns:
                    try:
                        sql = f"ALTER TABLE stock_basic_info ADD COLUMN {col_name} {col_def}"
                        cursor.execute(sql)
                        print(f"    [+] 新增字段: {col_name}")
                    except Exception as e:
                        print(f"    [!] 添加 {col_name} 时出错: {e}")
            
            conn.commit()
        print("    [OK] 表结构检查完成")
    finally:
        conn.close()


def get_stock_list_from_db() -> list:
    """从数据库获取现有股票列表"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT stock_code FROM stock_basic_info")
            return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def fetch_single_stock_info(stock_code: str, max_retries: int = 5) -> dict:
    """
    获取单个股票的详细信息
    
    使用 stock_individual_info_em 接口
    """
    for attempt in range(max_retries):
        try:
            df = ak.stock_individual_info_em(symbol=stock_code)
            
            if df is None or df.empty:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None
            
            # 转换为字典
            info = {}
            for _, row in df.iterrows():
                item = str(row['item']).strip()
                value = row['value']
                info[item] = value
            
            return info
            
        except Exception as e:
            # 网络错误，增加等待时间
            wait_time = 2 ** attempt
            if attempt < max_retries - 1:
                time.sleep(wait_time)
            continue
    
    return None


def fetch_all_stocks_info(stock_codes: list, batch_size: int = 100) -> pd.DataFrame:
    """
    批量获取股票信息
    
    Args:
        stock_codes: 股票代码列表
        batch_size: 每批数量（避免请求过快）
    """
    print(f"\n[2/4] 获取股票详细信息...")
    print(f"    总数: {len(stock_codes)} 只")
    
    results = []
    total = len(stock_codes)
    success = 0
    failed = 0
    
    for i, code in enumerate(stock_codes):
        if i % batch_size == 0:
            progress = i * 100 // total
            print(f"    进度: {i}/{total} ({progress}%)")
        
        info = fetch_single_stock_info(code)
        
        if info:
            # 解析数据
            row = {'stock_code': code}
            
            # 基本信息
            row['stock_name'] = info.get('股票简称', info.get('股票代码', ''))
            row['industry'] = info.get('行业', None)
            
            # 上市时间
            list_date_str = str(info.get('上市时间', '')).strip()
            if list_date_str and list_date_str.isdigit() and len(list_date_str) == 8:
                row['list_date'] = f"{list_date_str[:4]}-{list_date_str[4:6]}-{list_date_str[6:]}"
            else:
                row['list_date'] = None
            
            # 市值数据
            row['total_market_cap'] = info.get('总市值', None)
            row['circulating_market_cap'] = info.get('流通市值', None)
            
            # 股本数据
            row['total_shares'] = info.get('总股本', None)
            row['circulating_shares'] = info.get('流通股', None)
            
            # 市盈率市净率
            pe = info.get('市盈率', None)
            pb = info.get('市净率', None)
            
            # 处理特殊值
            if pe and str(pe) not in ['-', '亏损', 'None', '']:
                try:
                    row['pe_ratio'] = float(pe)
                except:
                    row['pe_ratio'] = None
            else:
                row['pe_ratio'] = None
                
            if pb and str(pb) not in ['-', '亏损', 'None', '']:
                try:
                    row['pb_ratio'] = float(pb)
                except:
                    row['pb_ratio'] = None
            else:
                row['pb_ratio'] = None
            
            # 判断交易所和市场
            code_str = str(code)
            if code_str.startswith('6'):
                row['exchange'] = 'SH'
                row['market'] = '沪深'
                if code_str.startswith('688'):
                    row['stock_type'] = '科创板'
                else:
                    row['stock_type'] = '主板'
            elif code_str.startswith('0') or code_str.startswith('3'):
                row['exchange'] = 'SZ'
                row['market'] = '沪深'
                if code_str.startswith('3'):
                    row['stock_type'] = '创业板'
                else:
                    row['stock_type'] = '主板'
            elif code_str.startswith('4') or code_str.startswith('8') or code_str.startswith('9'):
                row['exchange'] = 'BJ'
                row['market'] = '北交所'
                row['stock_type'] = '北交所'
            else:
                row['exchange'] = 'UNKNOWN'
                row['market'] = '未知'
                row['stock_type'] = '其他'
            
            results.append(row)
            success += 1
        else:
            failed += 1
        
        # 控制请求频率
        if i % 10 == 0:
            time.sleep(0.2)
    
    print(f"    [完成] 成功: {success}, 失败: {failed}")
    
    return pd.DataFrame(results)


def sync_to_database(df: pd.DataFrame):
    """同步数据到数据库"""
    print("\n[3/4] 同步数据到数据库...")
    
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
            (stock_code, stock_name, exchange, market, stock_type, industry, list_date,
             total_market_cap, circulating_market_cap, total_shares, circulating_shares,
             pe_ratio, pb_ratio, update_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
            stock_name = VALUES(stock_name),
            exchange = VALUES(exchange),
            market = VALUES(market),
            stock_type = VALUES(stock_type),
            industry = VALUES(industry),
            list_date = COALESCE(VALUES(list_date), list_date),
            total_market_cap = VALUES(total_market_cap),
            circulating_market_cap = VALUES(circulating_market_cap),
            total_shares = VALUES(total_shares),
            circulating_shares = VALUES(circulating_shares),
            pe_ratio = VALUES(pe_ratio),
            pb_ratio = VALUES(pb_ratio),
            update_time = NOW()
            """
            
            for _, row in df.iterrows():
                try:
                    cursor.execute(insert_sql, (
                        row['stock_code'],
                        row.get('stock_name', row['stock_code']),
                        row['exchange'],
                        row['market'],
                        row['stock_type'],
                        row.get('industry', None),
                        row.get('list_date', None),
                        row.get('total_market_cap', None),
                        row.get('circulating_market_cap', None),
                        row.get('total_shares', None),
                        row.get('circulating_shares', None),
                        row.get('pe_ratio', None),
                        row.get('pb_ratio', None)
                    ))
                    success_count += 1
                    
                except Exception as e:
                    error_count += 1
                    if error_count <= 3:
                        print(f"    ⚠ 插入 {row['stock_code']} 失败: {e}")
            
            conn.commit()
    
    finally:
        conn.close()
    
    print(f"    [OK] 成功插入/更新 {success_count} 条记录")
    if error_count > 0:
        print(f"    ⚠ 失败 {error_count} 条")


def show_stats():
    """显示数据库统计信息"""
    print("\n[4/4] 数据库统计...")
    
    conn = get_db_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM stock_basic_info")
            total = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT market, stock_type, COUNT(*) as count 
                FROM stock_basic_info 
                GROUP BY market, stock_type 
                ORDER BY count DESC
            """)
            breakdown = cursor.fetchall()
            
            cursor.execute("SELECT COUNT(*) as count FROM stock_basic_info WHERE total_market_cap IS NOT NULL")
            with_cap = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM stock_basic_info WHERE list_date IS NOT NULL")
            with_date = cursor.fetchone()['count']
            
            print(f"\n{'='*50}")
            print(f"数据库统计")
            print(f"{'='*50}")
            print(f"总股票数: {total}")
            print(f"有市值数据: {with_cap} ({with_cap*100//max(total,1)}%)")
            print(f"有上市日期: {with_date} ({with_date*100//max(total,1)}%)")
            print(f"\n各市场分布:")
            for item in breakdown:
                print(f"  - {item['market']} {item['stock_type']}: {item['count']}")
    finally:
        conn.close()


def main():
    print("=" * 50)
    print("股票基础信息同步工具 (东方财富接口)")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 测试单个接口是否可用
    print("\n[测试] 测试 stock_individual_info_em 接口...")
    print("    正在连接东方财富服务器...")
    test_result = fetch_single_stock_info("000001", max_retries=5)
    if test_result:
        print(f"    [OK] 接口正常，返回数据示例:")
        for k, v in list(test_result.items())[:6]:
            print(f"        {k}: {v}")
    else:
        print("\n    [FAIL] 接口连接失败")
        print("\n可能原因：")
        print("    1. 网络不稳定，请稍后重试")
        print("    2. 东方财富服务器繁忙")
        print("    3. 需要设置代理")
        print("\n解决方案：")
        print("    - 稍等1-2分钟后再运行")
        print("    - 设置代理: set HTTP_PROXY=http://127.0.0.1:7890")
        sys.exit(1)
    
    # 初始化表
    init_table()
    
    # 获取数据库中已有的股票列表
    existing_codes = get_stock_list_from_db()
    
    if existing_codes:
        print(f"\n[信息] 数据库已有 {len(existing_codes)} 只股票")
        print("    将获取这些股票的详细信息...")
        stock_codes = existing_codes
    else:
        print("\n[信息] 数据库为空，需要先获取股票列表...")
        print("    请先运行以下命令获取股票列表:")
        print("    python -c \"import akshare as ak; df = ak.stock_info_a_code_name(); print('\\n'.join(df['code'].tolist()[:10]))\"")
        print("\n    或手动添加股票代码到数据库")
        sys.exit(1)
    
    # 获取详细信息
    df = fetch_all_stocks_info(stock_codes)
    
    if df.empty:
        print("\n[FAIL] 获取数据失败")
        sys.exit(1)
    
    # 同步到数据库
    sync_to_database(df)
    
    # 显示统计
    show_stats()
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


if __name__ == "__main__":
    main()
