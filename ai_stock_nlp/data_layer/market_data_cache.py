"""
市场数据缓存模块

【功能】
1. 从东方财富API获取市场实时数据并缓存到数据库（直接调API，高容错）
2. 提供快速查询接口，加速市场排行展示
3. 支持定时刷新机制

【数据表】
- market_snapshot: 市场实时数据快照（全量股票）
- market_rank_cache: 排行数据缓存（涨幅榜、跌幅榜、成交额榜）
"""

import os
import time
import random
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from .db_connection import get_db_connection


class MarketDataCache:
    """
    市场数据缓存管理器
    
    使用方式:
        cache = MarketDataCache()
        # 刷新数据
        cache.refresh_market_data()
        # 获取缓存的排行数据
        gainers = cache.get_top_gainers(20)
    """
    
    def __init__(self):
        self.db = None
        try:
            self.db = get_db_connection()
            self._ensure_tables()
        except Exception as e:
            print(f"[WARN] MarketDataCache DB init failed (non-fatal): {e}")
            self.db = None
    
    def _ensure_tables(self):
        """确保数据表存在"""
        # 市场快照表 - 存储全市场股票实时数据
        create_snapshot_sql = """
        CREATE TABLE IF NOT EXISTS market_snapshot (
            id INT AUTO_INCREMENT PRIMARY KEY,
            snapshot_time DATETIME NOT NULL,
            trade_date DATE NOT NULL,
            stock_code VARCHAR(10) NOT NULL,
            stock_name VARCHAR(20),
            current_price DECIMAL(10, 2),
            change_pct DECIMAL(10, 2),
            change_amount DECIMAL(10, 2),
            volume BIGINT,
            amount DECIMAL(20, 2),
            open_price DECIMAL(10, 2),
            high_price DECIMAL(10, 2),
            low_price DECIMAL(10, 2),
            pre_close DECIMAL(10, 2),
            pe_ratio DECIMAL(10, 2),
            pb_ratio DECIMAL(10, 2),
            turnover_rate DECIMAL(10, 2),
            UNIQUE KEY uk_snapshot_code_time (snapshot_time, stock_code),
            INDEX idx_trade_date (trade_date),
            INDEX idx_change_pct (change_pct),
            INDEX idx_amount (amount)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        # 排行缓存表 - 存储预计算的排行结果
        create_rank_sql = """
        CREATE TABLE IF NOT EXISTS market_rank_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            cache_time DATETIME NOT NULL,
            trade_date DATE NOT NULL,
            rank_type VARCHAR(20) NOT NULL,
            rank_order INT NOT NULL,
            stock_code VARCHAR(10) NOT NULL,
            stock_name VARCHAR(20),
            current_price DECIMAL(10, 2),
            change_pct DECIMAL(10, 2),
            change_amount DECIMAL(10, 2),
            volume BIGINT,
            amount DECIMAL(20, 2),
            open_price DECIMAL(10, 2),
            high_price DECIMAL(10, 2),
            low_price DECIMAL(10, 2),
            pre_close DECIMAL(10, 2),
            UNIQUE KEY uk_rank_cache (trade_date, rank_type, stock_code),
            INDEX idx_cache_time (cache_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        try:
            self.db.execute_update(create_snapshot_sql)
            self.db.execute_update(create_rank_sql)
        except Exception as e:
            print(f"创建表失败: {e}")
    
    @staticmethod
    def _safe_float(value, default=0):
        """安全转换为 float，处理 NaN、'-'、'--'、空字符串等异常值"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value) if pd.notna(value) else default
        s = str(value).strip()
        if s in ('', '-', '--', '—', 'nan', 'NaN', 'None'):
            return default
        try:
            return float(s)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_int(value, default=0):
        """安全转换为 int，处理各种异常值"""
        v = MarketDataCache._safe_float(value, default)
        return int(v)

    def refresh_market_data(self, max_retries: int = 5) -> bool:
        """
        从东方财富API刷新市场数据到数据库（每页独立重试，连接断开自动恢复）
        
        Args:
            max_retries: 最大重试次数
        
        Returns:
            是否成功
        """
        df = self._fetch_spot_data(max_retries)
        if df is None:
            return False
        
        try:
            snapshot_time = datetime.now()
            trade_date = snapshot_time.date()
            
            # 清空全部旧数据，保证每只股票只有一条最新值
            self.db.execute_update("TRUNCATE TABLE market_snapshot")
            
            # 插入新数据
            insert_sql = """
            INSERT INTO market_snapshot 
            (snapshot_time, trade_date, stock_code, stock_name, current_price, 
             change_pct, change_amount, volume, amount, open_price, high_price, 
             low_price, pre_close, pe_ratio, pb_ratio, turnover_rate)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            safef = self._safe_float
            safei = self._safe_int

            records = []
            for _, row in df.iterrows():
                records.append((
                    snapshot_time,
                    trade_date,
                    str(row.get('代码', '')).zfill(6),
                    row.get('名称', ''),
                    safef(row.get('最新价')),
                    safef(row.get('涨跌幅')),
                    safef(row.get('涨跌额')),
                    safei(row.get('成交量')),
                    safef(row.get('成交额')),
                    safef(row.get('今开')),
                    safef(row.get('最高')),
                    safef(row.get('最低')),
                    safef(row.get('昨收')),
                    safef(row.get('市盈率-动态'), default=None),
                    safef(row.get('市净率'), default=None),
                    safef(row.get('换手率')),
                ))
            
            # 批量插入
            conn = self.db.connect()
            with conn.cursor() as cursor:
                cursor.executemany(insert_sql, records)
                conn.commit()
            
            # 更新排行缓存
            self._update_rank_cache(trade_date, snapshot_time)
            
            print(f"市场数据刷新成功: {snapshot_time}, 共 {len(records)} 条记录")
            return True
            
        except Exception as e:
            print(f"写入数据库失败: {e}")
            return False
    
    def _fetch_spot_data(self, max_retries: int = 5):
        """
        自定义分页拉取行情数据（绕过akshare，直接调东方财富API）
        
        优势：
        1. 复用 Session 减少连接开销
        2. 每页独立重试（某页失败不影响其他页）
        3. 连接断开后自动重建 Session
        
        Args:
            max_retries: 每页最大重试次数
        
        Returns:
            DataFrame 或 None
        """
        url = "https://82.push2.eastmoney.com/api/qt/clist/get"
        base_params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
            "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/",
            "Accept": "application/json, text/plain, */*",
        }
        
        def _create_session():
            s = requests.Session()
            s.headers.update(headers)
            # 增加连接池，支持 keep-alive
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5, pool_maxsize=10, max_retries=0
            )
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            return s
        
        def _fetch_page(session, page_num):
            """拉取单页，失败时返回 None"""
            params = base_params.copy()
            params["pn"] = str(page_num)
            for retry in range(max_retries):
                try:
                    r = session.get(url, params=params, timeout=30)
                    r.raise_for_status()
                    data = r.json()
                    if data and data.get("data") and data["data"].get("diff"):
                        return pd.DataFrame(data["data"]["diff"])
                    return None
                except Exception:
                    if retry < max_retries - 1:
                        time.sleep(2 ** retry)  # 指数退避
            return None
        
        session = _create_session()
        all_pages = []
        total = 0
        per_page = 100
        
        try:
            # 第一页：同时获取 total 和数据
            print(f"  拉取行情数据...", end=' ', flush=True)
            
            first_page = _fetch_page(session, 1)
            if first_page is None or first_page.empty:
                print("首页拉取失败")
                return None
            
            all_pages.append(first_page)
            per_page = len(first_page)
            
            # 获取总数（需要额外请求一次来获取 total）
            try:
                params = base_params.copy()
                params["pn"] = "1"
                r = session.get(url, params=params, timeout=30)
                total = r.json()["data"]["total"]
            except Exception:
                # 如果获取 total 失败，至少用第一页数据
                pass
            
            # 从第二页开始拉取
            if total > per_page:
                total_pages = (total + per_page - 1) // per_page
                print(f"共 {total} 条/{total_pages} 页...", end='', flush=True)
                
                failed_pages = []  # 记录失败页号
                
                for page in range(2, total_pages + 1):
                    # 页间随机延迟，避免被限流
                    time.sleep(random.uniform(0.3, 0.8))
                    
                    page_df = _fetch_page(session, page)
                    if page_df is not None and not page_df.empty:
                        all_pages.append(page_df)
                    else:
                        print(f" 页{page}失败", end='', flush=True)
                        # 重建 session（可能连接被污染）
                        session.close()
                        session = _create_session()
                        time.sleep(1)
                        # 再试一次
                        page_df = _fetch_page(session, page)
                        if page_df is not None and not page_df.empty:
                            all_pages.append(page_df)
                        else:
                            failed_pages.append(page)
                            print(f"(暂存)", end='', flush=True)
                    
                    # 进度提示
                    if page % 10 == 0:
                        print(f".{page}", end='', flush=True)
                
                # 末轮补漏：重试所有失败页
                if failed_pages:
                    print(f"  | 补漏 {len(failed_pages)} 页...", end='', flush=True)
                    time.sleep(3)  # 等一下网络恢复
                    session.close()
                    session = _create_session()
                    
                    retry_ok = 0
                    for page in failed_pages:
                        time.sleep(random.uniform(0.5, 1.5))
                        page_df = _fetch_page(session, page)
                        if page_df is not None and not page_df.empty:
                            all_pages.append(page_df)
                            retry_ok += 1
                        else:
                            # 再建新 session 最后试一次
                            session.close()
                            session = _create_session()
                            time.sleep(2)
                            page_df = _fetch_page(session, page)
                            if page_df is not None and not page_df.empty:
                                all_pages.append(page_df)
                                retry_ok += 1
                    
                    print(f" 恢复 {retry_ok}/{len(failed_pages)} 页", end='', flush=True)
                
                print()
            
            if not all_pages:
                print("  所有页面拉取失败")
                return None
            
            # 合并所有页
            combined = pd.concat(all_pages, ignore_index=True)
            
            # 重命名为 akshare 兼容的列名
            column_map = {
                "f2": "最新价", "f3": "涨跌幅", "f4": "涨跌额",
                "f5": "成交量", "f6": "成交额", "f7": "振幅",
                "f8": "换手率", "f9": "市盈率-动态", "f10": "量比",
                "f12": "代码", "f14": "名称", "f15": "最高",
                "f16": "最低", "f17": "今开", "f18": "昨收",
                "f20": "总市值", "f21": "流通市值", "f23": "市净率",
            }
            # 只保留存在的列
            rename_map = {k: v for k, v in column_map.items() if k in combined.columns}
            combined.rename(columns=rename_map, inplace=True)
            
            print(f"  成功，获取 {len(combined)} 条记录 (丢失 {total - len(combined)} 条)")
            return combined
            
        except Exception as e:
            print(f"\n  拉取失败: {e}")
            return None
        finally:
            session.close()
    
    def _update_rank_cache(self, trade_date: datetime.date, cache_time: datetime):
        """更新排行缓存"""
        try:
            # 清空全部排行缓存，保证只保留最新
            self.db.execute_update("TRUNCATE TABLE market_rank_cache")
            
            # 涨幅榜
            gainers_sql = """
            INSERT INTO market_rank_cache 
            (cache_time, trade_date, rank_type, rank_order, stock_code, stock_name,
             current_price, change_pct, change_amount, volume, amount, 
             open_price, high_price, low_price, pre_close)
            SELECT %s, %s, 'gainers', @rownum:=@rownum+1, stock_code, stock_name,
                   current_price, change_pct, change_amount, volume, amount,
                   open_price, high_price, low_price, pre_close
            FROM market_snapshot, (SELECT @rownum:=0) r
            WHERE trade_date = %s AND change_pct > 0
            ORDER BY change_pct DESC
            LIMIT 100
            """
            self.db.execute_update(gainers_sql, (cache_time, trade_date, trade_date))
            
            # 跌幅榜
            losers_sql = """
            INSERT INTO market_rank_cache 
            (cache_time, trade_date, rank_type, rank_order, stock_code, stock_name,
             current_price, change_pct, change_amount, volume, amount,
             open_price, high_price, low_price, pre_close)
            SELECT %s, %s, 'losers', @rownum:=@rownum+1, stock_code, stock_name,
                   current_price, change_pct, change_amount, volume, amount,
                   open_price, high_price, low_price, pre_close
            FROM market_snapshot, (SELECT @rownum:=0) r
            WHERE trade_date = %s AND change_pct < 0
            ORDER BY change_pct ASC
            LIMIT 100
            """
            self.db.execute_update(losers_sql, (cache_time, trade_date, trade_date))
            
            # 成交额榜
            volume_sql = """
            INSERT INTO market_rank_cache 
            (cache_time, trade_date, rank_type, rank_order, stock_code, stock_name,
             current_price, change_pct, change_amount, volume, amount,
             open_price, high_price, low_price, pre_close)
            SELECT %s, %s, 'volume', @rownum:=@rownum+1, stock_code, stock_name,
                   current_price, change_pct, change_amount, volume, amount,
                   open_price, high_price, low_price, pre_close
            FROM market_snapshot, (SELECT @rownum:=0) r
            WHERE trade_date = %s AND amount > 0
            ORDER BY amount DESC
            LIMIT 100
            """
            self.db.execute_update(volume_sql, (cache_time, trade_date, trade_date))
            
        except Exception as e:
            print(f"更新排行缓存失败: {e}")
    
    def get_top_gainers(self, limit: int = 20) -> pd.DataFrame:
        """从缓存获取涨幅榜"""
        if self.db is None:
            return pd.DataFrame()
        # 先尝试获取最新日期的数据（不限定今天）
        sql = """
        SELECT stock_code as 代码, stock_name as 名称, current_price as 最新价,
               change_pct as 涨跌幅, change_amount as 涨跌额, volume as 成交量,
               amount as 成交额, open_price as 今开, high_price as 最高,
               low_price as 最低, pre_close as 昨收
        FROM market_rank_cache
        WHERE rank_type = 'gainers'
          AND trade_date = (SELECT MAX(trade_date) FROM market_rank_cache WHERE rank_type = 'gainers')
        ORDER BY rank_order
        LIMIT %s
        """
        result = self.db.execute_query(sql, (limit,))
        if result:
            return pd.DataFrame(result)
        return pd.DataFrame()
    
    def get_top_losers(self, limit: int = 20) -> pd.DataFrame:
        """从缓存获取跌幅榜"""
        if self.db is None:
            return pd.DataFrame()
        sql = """
        SELECT stock_code as 代码, stock_name as 名称, current_price as 最新价,
               change_pct as 涨跌幅, change_amount as 涨跌额, volume as 成交量,
               amount as 成交额, open_price as 今开, high_price as 最高,
               low_price as 最低, pre_close as 昨收
        FROM market_rank_cache
        WHERE rank_type = 'losers'
          AND trade_date = (SELECT MAX(trade_date) FROM market_rank_cache WHERE rank_type = 'losers')
        ORDER BY rank_order
        LIMIT %s
        """
        result = self.db.execute_query(sql, (limit,))
        if result:
            return pd.DataFrame(result)
        return pd.DataFrame()
    
    def get_top_volume(self, limit: int = 20) -> pd.DataFrame:
        """从缓存获取成交额榜"""
        if self.db is None:
            return pd.DataFrame()
        sql = """
        SELECT stock_code as 代码, stock_name as 名称, current_price as 最新价,
               change_pct as 涨跌幅, change_amount as 涨跌额, volume as 成交量,
               amount as 成交额, open_price as 今开, high_price as 最高,
               low_price as 最低, pre_close as 昨收
        FROM market_rank_cache
        WHERE rank_type = 'volume'
          AND trade_date = (SELECT MAX(trade_date) FROM market_rank_cache WHERE rank_type = 'volume')
        ORDER BY rank_order
        LIMIT %s
        """
        result = self.db.execute_query(sql, (limit,))
        if result:
            return pd.DataFrame(result)
        return pd.DataFrame()
    
    def get_all_stocks(self, limit: int = 500) -> pd.DataFrame:
        """从缓存获取全部股票列表（按代码排序）"""
        if self.db is None:
            return pd.DataFrame()
        sql = """
        SELECT stock_code as 代码, stock_name as 名称, current_price as 最新价,
               change_pct as 涨跌幅, change_amount as 涨跌额, volume as 成交量,
               amount as 成交额, open_price as 今开, high_price as 最高,
               low_price as 最低, pre_close as 昨收
        FROM market_snapshot
        WHERE trade_date = (SELECT MAX(trade_date) FROM market_snapshot)
          AND amount > 0
        ORDER BY CAST(stock_code AS UNSIGNED)
        LIMIT %s
        """
        result = self.db.execute_query(sql, (limit,))
        if result:
            return pd.DataFrame(result)
        return pd.DataFrame()

    def get_cache_status(self) -> Dict:
        """获取缓存状态"""
        if self.db is None:
            return {'has_data': False, 'stock_count': 0, 'last_update': None}
        try:
            # 检查今日数据
            sql = """
            SELECT COUNT(*) as count, MAX(snapshot_time) as last_update
            FROM market_snapshot
            WHERE trade_date = CURDATE()
            """
            result = self.db.execute_query(sql)
            if result:
                return {
                    'has_data': result[0]['count'] > 0,
                    'stock_count': result[0]['count'],
                    'last_update': result[0]['last_update']
                }
        except Exception as e:
            print(f"获取缓存状态失败: {e}")
        
        return {'has_data': False, 'stock_count': 0, 'last_update': None}
    
    def is_cache_valid(self, max_age_minutes: int = 5) -> bool:
        """
        检查缓存是否有效
        
        Args:
            max_age_minutes: 最大缓存时间（分钟）
        """
        status = self.get_cache_status()
        if not status['has_data']:
            return False
        
        if status['last_update']:
            last_update = status['last_update']
            if isinstance(last_update, str):
                last_update = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
            age = datetime.now() - last_update
            return age < timedelta(minutes=max_age_minutes)
        
        return False


# 全局实例
market_cache = MarketDataCache()


def refresh_market_data() -> bool:
    """快捷函数：刷新市场数据"""
    return market_cache.refresh_market_data()


def get_cached_gainers(limit: int = 20) -> pd.DataFrame:
    """快捷函数：获取缓存的涨幅榜"""
    return market_cache.get_top_gainers(limit)


def get_cached_losers(limit: int = 20) -> pd.DataFrame:
    """快捷函数：获取缓存的跌幅榜"""
    return market_cache.get_top_losers(limit)


def get_cached_volume(limit: int = 20) -> pd.DataFrame:
    """快捷函数：获取缓存的成交额榜"""
    return market_cache.get_top_volume(limit)


def get_cached_all_stocks(limit: int = 500) -> pd.DataFrame:
    """快捷函数：获取缓存的全部股票"""
    return market_cache.get_all_stocks(limit)
