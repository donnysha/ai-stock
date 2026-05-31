"""
股票财务报表数据同步脚本

功能：
1. 从akshare获取个股年度/季度财务报表（同花顺接口）
2. 计算核心财务指标：ROE、毛利率、净利率、营收增速、净利润增速等
3. 存储到MySQL数据库

核心指标：
- ROE (净资产收益率) = 净利润 / 净资产
- 毛利率 = (营收 - 成本) / 营收
- 净利率 = 净利润 / 营收
- 营收增速 = (本期营收 - 上期营收) / 上期营收
- 净利润增速 = (本期净利润 - 上期净利润) / 上期净利润
- 资产负债率 = 总负债 / 总资产
- 流动比率 = 流动资产 / 流动负债
- 经营性现金流

使用方法：
    python scripts/sync_financial_data.py [股票代码]   # 获取单只股票
    python scripts/sync_financial_data.py all           # 获取所有股票（支持断点续跑）
    python scripts/sync_financial_data.py all --resume  # 从上次中断位置继续
    python scripts/sync_financial_data.py stats         # 显示统计
"""

import sys
import io
import os
import json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import pandas as pd
import akshare as ak
import pymysql
from datetime import datetime
import time
import traceback
import re
from typing import Optional, Dict
from pathlib import Path

# 添加项目根目录，复用统一配置
sys.path.insert(0, str(Path(__file__).parent.parent))
from ai_stock_nlp.config.settings import DB_CONFIG

# ============== 进度文件路径 ==============
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_financial_progress.json')

# ============== 建表SQL ==============
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_financial_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL COMMENT '股票代码',
    stock_name VARCHAR(50) COMMENT '股票名称',
    report_date VARCHAR(20) NOT NULL COMMENT '报告期',
    report_type VARCHAR(10) COMMENT '报告类型(年报/季报)',
    fiscal_year INT COMMENT '财年',
    fiscal_quarter INT COMMENT '季度',
    
    -- 利润表数据
    revenue DECIMAL(20,4) COMMENT '营业总收入(万元)',
    operating_profit DECIMAL(20,4) COMMENT '营业利润(万元)',
    net_profit DECIMAL(20,4) COMMENT '净利润(万元)',
    total_cost DECIMAL(20,4) COMMENT '营业总成本(万元)',
    
    -- 资产负债表数据
    total_assets DECIMAL(20,4) COMMENT '总资产(万元)',
    total_liabilities DECIMAL(20,4) COMMENT '总负债(万元)',
    equity DECIMAL(20,4) COMMENT '所有者权益(万元)',
    
    -- 现金流量表数据
    operating_cash_flow DECIMAL(20,4) COMMENT '经营性现金流(万元)',
    investing_cash_flow DECIMAL(20,4) COMMENT '投资性现金流(万元)',
    financing_cash_flow DECIMAL(20,4) COMMENT '筹资性现金流(万元)',
    
    -- 核心财务指标
    roe DECIMAL(10,4) COMMENT '净资产收益率ROE(%)',
    gross_margin DECIMAL(10,4) COMMENT '毛利率(%)',
    net_margin DECIMAL(10,4) COMMENT '净利率(%)',
    revenue_growth DECIMAL(10,4) COMMENT '营收增速(%)',
    profit_growth DECIMAL(10,4) COMMENT '净利润增速(%)',
    debt_ratio DECIMAL(10,4) COMMENT '资产负债率(%)',
    current_ratio DECIMAL(10,4) COMMENT '流动比率',
    basic_eps DECIMAL(10,4) COMMENT '基本每股收益',
    
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_code_date (stock_code, report_date),
    INDEX idx_report_date (report_date),
    INDEX idx_fiscal_year (fiscal_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票财务数据表';
"""


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


def init_table():
    """初始化表结构"""
    print("[1] 初始化数据库表...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(CREATE_TABLE_SQL)
        conn.commit()
        print("    [OK] 表结构就绪")
    finally:
        conn.close()


def get_stock_name_from_db(stock_code: str) -> Optional[str]:
    """从数据库获取股票名称"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT stock_name FROM stock_basic_info WHERE stock_code = %s",
                (stock_code,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    finally:
        conn.close()


def parse_number(value) -> Optional[float]:
    """解析带单位的数字字符串，如 '145.23亿' -> 14523000000"""
    if pd.isna(value) or value is None:
        return None
    
    value = str(value).strip()
    
    # 检查是否为无效值
    if value in ['False', '', '-', 'nan', 'NaN', 'None', 'N/A']:
        return None
    
    # 检查是否包含无效字符
    if '亿' not in value and '万' not in value and '千' not in value and '百' not in value:
        try:
            num = float(value)
            if pd.isna(num):
                return None
            return num
        except:
            return None
    
    # 处理中文单位
    units = {
        '亿': 100000000,
        '万': 10000,
        '千': 1000,
        '百': 100
    }
    
    for unit, multiplier in units.items():
        if unit in value:
            try:
                num_part = value.replace(unit, '').strip()
                # 移除可能的逗号
                num_part = num_part.replace(',', '')
                num = float(num_part)
                if pd.isna(num):
                    return None
                return num * multiplier
            except:
                return None
    
    return None


def parse_report_date(date_str: str) -> tuple:
    """解析报告期，返回 (日期字符串, 年份, 季度, 类型)"""
    date_str = str(date_str).strip()
    
    try:
        if '-' in date_str:
            parts = date_str.split('-')
            year = int(parts[0])
            month = int(parts[1])
            quarter = (month - 1) // 3 + 1
            report_type = '年报' if month == 12 else '季报'
            return date_str, year, quarter, report_type
    except:
        pass
    
    return date_str, None, None, None


def get_financial_data_ths(stock_code: str, max_retries: int = 5) -> tuple:
    """
    从同花顺获取财务报表数据
    返回: (利润表, 现金流量表, 资产负债表)
    """
    profit_df = pd.DataFrame()
    cash_df = pd.DataFrame()
    balance_df = pd.DataFrame()
    
    for attempt in range(max_retries):
        try:
            print(f"    获取财务报表 (尝试 {attempt + 1}/{max_retries})...")
            
            # 利润表
            profit_df = ak.stock_financial_benefit_ths(symbol=stock_code)
            if profit_df is not None and not profit_df.empty:
                print(f"    利润表: {len(profit_df)} 条")
            
            time.sleep(2)
            
            # 现金流量表
            cash_df = ak.stock_financial_cash_ths(symbol=stock_code)
            if cash_df is not None and not cash_df.empty:
                print(f"    现金流量表: {len(cash_df)} 条")
            
            time.sleep(2)
            
            # 资产负债表
            balance_df = ak.stock_financial_debt_ths(symbol=stock_code)
            if balance_df is not None and not balance_df.empty:
                print(f"    资产负债表: {len(balance_df)} 条")
            
            break
            
        except Exception as e:
            print(f"    获取失败: {e}")
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)  # 递增等待：10s, 20s, 30s, 40s
                print(f"    等待 {wait} 秒后重试...")
                time.sleep(wait)
    
    return profit_df, cash_df, balance_df


def merge_financial_data(stock_code: str, profit_df: pd.DataFrame, 
                        cash_df: pd.DataFrame, balance_df: pd.DataFrame) -> pd.DataFrame:
    """合并财务报表数据并计算指标"""
    
    if profit_df.empty:
        return pd.DataFrame()
    
    stock_name = get_stock_name_from_db(stock_code)
    results = []
    
    # 获取上一期数据用于计算增速
    prev_revenue = None
    prev_profit = None
    
    for idx, row in profit_df.iterrows():
        try:
            report_date = str(row.get('报告期', ''))
            if not report_date or report_date == 'nan':
                continue
            
            parsed = parse_report_date(report_date)
            date_str, fiscal_year, fiscal_quarter, report_type = parsed
            
            if fiscal_year is None:
                continue
            
            # 解析财务数据
            revenue = parse_number(row.get('*营业总收入') or row.get('一、营业总收入'))
            net_profit = parse_number(row.get('*净利润') or row.get('五、净利润'))
            total_cost = parse_number(row.get('*营业支出') or row.get('二、营业支出'))
            operating_profit = parse_number(row.get('三、营业利润') or row.get('四、利润总额'))
            basic_eps = parse_number(row.get('（一）基本每股收益'))
            
            # 查找对应日期的资产负债表数据
            total_assets = None
            total_liabilities = None
            equity = None
            
            if not balance_df.empty:
                bal_match = balance_df[balance_df['报告期'] == report_date]
                if not bal_match.empty:
                    bal_row = bal_match.iloc[0]
                    total_assets = parse_number(bal_row.get('*资产合计'))
                    total_liabilities = parse_number(bal_row.get('*负债合计'))
                    equity = parse_number(bal_row.get('*所有者权益（或股东权益）合计'))
            
            # 查找对应日期的现金流量表数据
            operating_cash_flow = None
            investing_cash_flow = None
            financing_cash_flow = None
            
            if not cash_df.empty:
                cf_match = cash_df[cash_df['报告期'] == report_date]
                if not cf_match.empty:
                    cf_row = cf_match.iloc[0]
                    operating_cash_flow = parse_number(cf_row.get('*经营活动产生的现金流量净额'))
                    investing_cash_flow = parse_number(cf_row.get('*投资活动产生的现金流量净额'))
                    financing_cash_flow = parse_number(cf_row.get('*筹资活动产生的现金流量净额'))
            
            # 计算指标
            roe = None
            if net_profit is not None and equity is not None and equity != 0:
                roe = (net_profit / equity) * 100
            
            gross_margin = None
            if revenue is not None and revenue != 0 and total_cost is not None:
                gross_margin = ((revenue - total_cost) / revenue) * 100
            
            net_margin = None
            if net_profit is not None and revenue is not None and revenue != 0:
                net_margin = (net_profit / revenue) * 100
            
            # 营收增速
            revenue_growth = None
            if revenue is not None and prev_revenue is not None and prev_revenue != 0:
                revenue_growth = ((revenue - prev_revenue) / prev_revenue) * 100
            
            # 净利润增速
            profit_growth = None
            if net_profit is not None and prev_profit is not None and prev_profit != 0:
                profit_growth = ((net_profit - prev_profit) / prev_profit) * 100
            
            # 资产负债率
            debt_ratio = None
            if total_liabilities is not None and total_assets is not None and total_assets != 0:
                debt_ratio = (total_liabilities / total_assets) * 100
            
            result = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'report_date': date_str,
                'report_type': report_type,
                'fiscal_year': fiscal_year,
                'fiscal_quarter': fiscal_quarter,
                'revenue': revenue,
                'operating_profit': operating_profit,
                'net_profit': net_profit,
                'total_cost': total_cost,
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'equity': equity,
                'operating_cash_flow': operating_cash_flow,
                'investing_cash_flow': investing_cash_flow,
                'financing_cash_flow': financing_cash_flow,
                'roe': roe,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'revenue_growth': revenue_growth,
                'profit_growth': profit_growth,
                'debt_ratio': debt_ratio,
                'basic_eps': basic_eps
            }
            
            results.append(result)
            
            # 更新上一期数据
            prev_revenue = revenue
            prev_profit = net_profit
            
        except Exception as e:
            continue
    
    if not results:
        return pd.DataFrame()
    
    return pd.DataFrame(results)


def save_to_database(df: pd.DataFrame):
    """保存数据到数据库"""
    if df.empty:
        print("    [WARN] 没有数据需要保存")
        return
    
    print("\n[3] 保存到数据库...")
    
    conn = get_db_connection()
    success = 0
    errors = 0
    
    try:
        with conn.cursor() as cursor:
            insert_sql = """
            INSERT INTO stock_financial_data (
                stock_code, stock_name, report_date, report_type, fiscal_year, fiscal_quarter,
                revenue, operating_profit, net_profit, total_cost,
                total_assets, total_liabilities, equity,
                operating_cash_flow, investing_cash_flow, financing_cash_flow,
                roe, gross_margin, net_margin, revenue_growth, profit_growth, debt_ratio, basic_eps
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name),
                revenue = VALUES(revenue),
                operating_profit = VALUES(operating_profit),
                net_profit = VALUES(net_profit),
                total_assets = VALUES(total_assets),
                total_liabilities = VALUES(total_liabilities),
                equity = VALUES(equity),
                operating_cash_flow = VALUES(operating_cash_flow),
                roe = VALUES(roe),
                gross_margin = VALUES(gross_margin),
                net_margin = VALUES(net_margin),
                revenue_growth = VALUES(revenue_growth),
                profit_growth = VALUES(profit_growth),
                debt_ratio = VALUES(debt_ratio),
                basic_eps = VALUES(basic_eps)
            """
            
            for _, row in df.iterrows():
                try:
                    # 确保所有值都是 Python 原生类型，没有 NaN
                    def clean_value(v):
                        if v is None:
                            return None
                        if pd.isna(v):
                            return None
                        if isinstance(v, (float, int)):
                            if pd.isna(v):
                                return None
                            return float(v) if v == v else None  # 处理 NaN
                        return v
                    
                    params = (
                        str(row['stock_code']),
                        str(row.get('stock_name')) if pd.notna(row.get('stock_name')) else None,
                        str(row['report_date']),
                        str(row.get('report_type')) if pd.notna(row.get('report_type')) else None,
                        int(row['fiscal_year']) if pd.notna(row.get('fiscal_year')) else None,
                        int(row.get('fiscal_quarter')) if pd.notna(row.get('fiscal_quarter')) else None,
                        clean_value(row.get('revenue')),
                        clean_value(row.get('operating_profit')),
                        clean_value(row.get('net_profit')),
                        clean_value(row.get('total_cost')),
                        clean_value(row.get('total_assets')),
                        clean_value(row.get('total_liabilities')),
                        clean_value(row.get('equity')),
                        clean_value(row.get('operating_cash_flow')),
                        clean_value(row.get('investing_cash_flow')),
                        clean_value(row.get('financing_cash_flow')),
                        clean_value(row.get('roe')),
                        clean_value(row.get('gross_margin')),
                        clean_value(row.get('net_margin')),
                        clean_value(row.get('revenue_growth')),
                        clean_value(row.get('profit_growth')),
                        clean_value(row.get('debt_ratio')),
                        clean_value(row.get('basic_eps'))
                    )
                    
                    # 检查是否有 NaN
                    for i, p in enumerate(params):
                        if p is not None and (not isinstance(p, str) and (p != p or str(p) == 'nan')):
                            params = list(params)
                            params[i] = None
                            params = tuple(params)
                    
                    cursor.execute(insert_sql, params)
                    success += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"    保存失败: {row.get('stock_code')} - {row.get('report_date')}: {e}")
            
            conn.commit()
            print(f"    [OK] 成功保存 {success} 条记录")
            if errors > 0:
                print(f"    [WARN] 失败 {errors} 条")
    
    finally:
        conn.close()


def sync_single_stock(stock_code: str):
    """同步单只股票的财务数据"""
    stock_code = stock_code.strip().zfill(6)
    
    print("=" * 50)
    print(f"财务数据同步 - {stock_code}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    init_table()
    
    # 获取数据
    profit_df, cash_df, balance_df = get_financial_data_ths(stock_code)
    
    if profit_df.empty:
        print("    [WARN] 未获取到任何财务数据")
        return
    
    # 合并并计算指标
    result_df = merge_financial_data(stock_code, profit_df, cash_df, balance_df)
    
    if result_df.empty:
        print("    [WARN] 数据处理失败")
        return
    
    print(f"\n    处理完成: {len(result_df)} 条有效数据")
    
    # 保存
    save_to_database(result_df)
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)


def get_all_stock_codes() -> list:
    """获取所有股票代码（按代码排序）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT stock_code FROM stock_basic_info ORDER BY stock_code")
            return [r[0] for r in cursor.fetchall()]
    finally:
        conn.close()


def check_stock_synced(stock_code: str) -> bool:
    """检查某只股票是否已有财务数据"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM stock_financial_data WHERE stock_code = %s",
                (stock_code,)
            )
            return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def get_db_synced_codes() -> set:
    """获取 stock_financial_data 表中已有数据的股票代码集合"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT stock_code FROM stock_financial_data")
            return {r[0] for r in cursor.fetchall()}
    finally:
        conn.close()


def load_progress() -> dict:
    """加载进度文件"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'completed': [],
        'failed': [],
        'last_index': 0,
        'total_success': 0,
        'total_fail': 0,
        'total_skipped': 0
    }


def save_progress(progress: dict):
    """保存进度到文件"""
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def sync_all_stocks(resume: bool = True):
    """
    同步所有股票的财务数据
    
    参数:
        resume: 是否启用断点续跑（默认 True，自动跳过已完成的和上次失败的）
    """
    print("=" * 60, flush=True)
    print("财务数据同步 - 全量", flush=True)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    if resume:
        print("模式: 支持断点续跑", flush=True)
    print("=" * 60, flush=True)
    
    init_table()
    
    codes = get_all_stock_codes()
    total_stocks = len(codes)
    print(f"\n数据库中总共有 {total_stocks} 只股票", flush=True)
    
    # 加载进度
    print("加载进度文件...", flush=True)
    progress = load_progress() if resume else {
        'completed': [],
        'failed': [],
        'last_index': 0,
        'total_success': 0,
        'total_fail': 0,
        'total_skipped': 0
    }
    
    completed_set = set(progress.get('completed', []))
    failed_set = set(progress.get('failed', []))
    total_success = progress.get('total_success', 0)
    total_fail = progress.get('total_fail', 0)
    total_skipped = progress.get('total_skipped', 0)
    
    # 统计需要同步的股票（先查数据库，已入库的跳过）
    print(f"\n检查数据库中已有数据（可能耗时，请等待）...", flush=True)
    db_synced_codes = get_db_synced_codes()
    print(f"  表中已有财务数据的股票: {len(db_synced_codes)} 只", flush=True)
    db_synced_count = 0
    progress_skip_count = 0
    
    to_sync = []
    for idx, code in enumerate(codes):
        if code in completed_set:
            progress_skip_count += 1
            total_skipped += 1
            # 每 500 只输出一次进度
            if progress_skip_count % 500 == 0:
                print(f"  [跳过-进度] 已跳过 {progress_skip_count}/{len(codes)} 只...", flush=True)
            continue
        if code in db_synced_codes:
            # 表中已有数据，直接标记完成并跳过
            completed_set.add(code)
            progress['completed'].append(code)
            total_skipped += 1
            db_synced_count += 1
            # 每 100 只输出一次
            if db_synced_count % 100 == 0:
                print(f"  [跳过-库] 已跳过 {db_synced_count} 只库里已有数据的股票...", flush=True)
            continue
        to_sync.append(code)
    
    if db_synced_count > 0:
        progress['total_skipped'] = total_skipped
        save_progress(progress)
    
    print(f"\n统计结果:", flush=True)
    print(f"  进度文件已完成: {progress_skip_count}")
    print(f"  库里已有数据:   {db_synced_count}")
    print(f"  上次失败:       {len(failed_set)}")
    print(f"  >>> 待同步:     {len(to_sync)}", flush=True)
    
    if not to_sync:
        print("\n所有股票已同步完成！", flush=True)
        show_stats()
        return
    
    print(f"\n开始同步 {len(to_sync)} 只股票...\n", flush=True)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print(f"预计每只约 8-15 秒（含请求间隔），请耐心等待...\n", flush=True)
    
    start_index = progress.get('last_index', 0)
    batch_buffer = []  # 批量积累数据，减少DB操作
    
    for i, code in enumerate(to_sync):
        current_index = i + 1
        overall_index = start_index + current_index
        
        # 每 10 只显示汇总进度条
        if current_index % 10 == 0 or current_index == 1:
            pct = (overall_index / total_stocks) * 100
            now = datetime.now().strftime('%H:%M:%S')
            print(f"\n[{now}] 进度: {current_index}/{len(to_sync)} 本轮 ({overall_index}/{total_stocks} 总计, {pct:.1f}%)", flush=True)
            print(f"    成功 {total_success} | 失败 {total_fail} | 跳过 {total_skipped}", flush=True)
        
        try:
            print(f"[{current_index}/{len(to_sync)}] 处理 {code}...", flush=True)
            
            profit_df, cash_df, balance_df = get_financial_data_ths(code)
            
            if profit_df.empty:
                total_fail += 1
                progress['failed'].append(code)
                print(f"    [FAIL] {code} - 未获取到财务数据", flush=True)
                save_progress(progress)
                continue
            
            result_df = merge_financial_data(code, profit_df, cash_df, balance_df)
            
            if not result_df.empty:
                save_to_database(result_df)
                total_success += 1
                completed_set.add(code)
                progress['completed'].append(code)
                # 如果之前失败过，从失败列表移除
                if code in failed_set:
                    failed_set.discard(code)
                    progress['failed'] = list(failed_set)
                print(f"    [OK] {code} - {len(result_df)} 条财务数据", flush=True)
            else:
                total_fail += 1
                progress['failed'].append(code)
                print(f"    [WARN] {code} - 数据处理后为空", flush=True)
            
        except Exception as e:
            total_fail += 1
            progress['failed'].append(code)
            error_msg = str(e)[:200]
            print(f"    [ERROR] {code} 失败: {error_msg}", flush=True)
        
        # 更新进度
        progress['total_success'] = total_success
        progress['total_fail'] = total_fail
        progress['total_skipped'] = total_skipped
        progress['last_index'] = overall_index
        
        # 每 10 只股票保存一次进度
        if current_index % 10 == 0:
            save_progress(progress)
        
        # 每 100 只股票暂停更长时间，避免被限制
        if current_index % 100 == 0:
            print(f"\n--- 已处理 {current_index} 只，休息 30 秒 ---", flush=True)
            time.sleep(30)
        else:
            # 控制请求频率，加长间隔
            time.sleep(3)
    
    # 最终保存进度
    save_progress(progress)
    
    # 清理进度文件（全部完成时）
    if total_fail == 0:
        try:
            os.remove(PROGRESS_FILE)
            print("\n[OK] 全部成功，已清理进度文件")
        except:
            pass
    
    print("\n" + "=" * 60, flush=True)
    print(f"同步完成", flush=True)
    print(f"成功: {total_success}, 失败: {total_fail}, 跳过: {total_skipped}", flush=True)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
    print("=" * 60, flush=True)
    
    # 如果有失败，打印失败列表
    if total_fail > 0:
        failed_list = progress.get('failed', [])
        if failed_list:
            print(f"\n失败股票列表 ({len(failed_list)} 只):")
            for fcode in failed_list[-20:]:  # 最多显示20只
                print(f"  - {fcode}")
            if len(failed_list) > 20:
                print(f"  ... 还有 {len(failed_list) - 20} 只")
            print(f"\n提示: 再次运行 'python sync_financial_data.py all' 会自动重试失败项")


def show_stats():
    """显示数据库统计"""
    print("\n" + "=" * 60)
    print("数据库统计")
    print("=" * 60)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM stock_financial_data")
            total = cursor.fetchone()[0]
            print(f"总记录数: {total}")
            
            # 股票数
            cursor.execute("SELECT COUNT(DISTINCT stock_code) FROM stock_financial_data")
            stocks = cursor.fetchone()[0]
            print(f"已同步股票数: {stocks}")
            
            # 数据库中总共有多少股票
            cursor.execute("SELECT COUNT(*) FROM stock_basic_info")
            total_stocks = cursor.fetchone()[0]
            print(f"数据库总股票数: {total_stocks}")
            if total_stocks > 0:
                print(f"同步覆盖率: {stocks}/{total_stocks} ({stocks/total_stocks*100:.1f}%)")
            
            # 最新数据示例
            cursor.execute("""
                SELECT stock_code, stock_name, report_date, report_type,
                       ROUND(roe, 2) as roe, ROUND(gross_margin, 2) as gross_margin,
                       ROUND(net_margin, 2) as net_margin, ROUND(revenue_growth, 2) as revenue_growth,
                       ROUND(profit_growth, 2) as profit_growth, ROUND(debt_ratio, 2) as debt_ratio
                FROM stock_financial_data 
                WHERE fiscal_year >= 2023
                ORDER BY stock_code, fiscal_year DESC, fiscal_quarter DESC
                LIMIT 10
            """)
            print("\n最新财务数据示例 (2023年以来):")
            print("-" * 80)
            for row in cursor.fetchall():
                print(f"{row[0]} {row[1]} ({row[2]} {row[3]})")
                print(f"  ROE: {row[4]}% | 毛利率: {row[5]}% | 净利率: {row[6]}%")
                print(f"  营收增速: {row[7]}% | 净利润增速: {row[8]}% | 资产负债率: {row[9]}%")
                print()
    
    finally:
        conn.close()
    
    # 显示进度文件状态
    if os.path.exists(PROGRESS_FILE):
        progress = load_progress()
        print(f"\n进度文件存在:")
        print(f"  已完成: {len(progress.get('completed', []))} 只")
        print(f"  失败: {len(progress.get('failed', []))} 只")
        print(f"  最后位置: 第 {progress.get('last_index', 0)} 只")


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        resume = '--resume' in sys.argv or '-r' in sys.argv
        
        if arg.lower() == 'all':
            sync_all_stocks(resume=True)
        elif arg.lower() == 'stats':
            show_stats()
        elif arg.lower() == '--resume' or arg.lower() == '-r':
            # 直接 --resume 等同于 all --resume
            sync_all_stocks(resume=True)
        else:
            sync_single_stock(arg)
    else:
        # 默认全量同步（支持断点续跑）
        print("用法:")
        print("  python sync_financial_data.py [股票代码]   # 获取单只股票")
        print("  python sync_financial_data.py all           # 获取所有股票（支持断点续跑）")
        print("  python sync_financial_data.py stats         # 显示统计")
        print("  python sync_financial_data.py --resume      # 从上次中断处继续")
        print("\n默认模式: 全量同步（支持断点续跑）")
        print("-" * 50)
        sync_all_stocks(resume=True)
    
    # 显示统计
    show_stats()


if __name__ == "__main__":
    main()
