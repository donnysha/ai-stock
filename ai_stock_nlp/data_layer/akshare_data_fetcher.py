"""
AkShare数据获取器模块

【模块功能】
使用AkShare库获取股票数据，是系统的数据源之一。

【数据来源】
- 东方财富接口（主力接口）
- 新浪接口（备用接口）

【主要功能】
1. 获取股票实时行情（get_realtime_quote）
2. 获取K线历史数据（get_kline_history / get_kline_dataframe）
3. 获取涨幅榜（get_top_gainers）
4. 获取跌幅榜（get_top_losers）
5. 获取成交额榜（get_top_volume）
6. 获取市场概览（get_market_overview）
7. 获取板块股票列表（get_sector_stocks）
8. 根据条件筛选股票（get_stocks_by_conditions）

【缓存策略】
- 实时行情数据缓存5分钟
- 避免频繁调用API

【代码格式转换】
- 输入：6位数字代码（如'000001'）
- 输出：akshare格式（如'sh000001'或'sz000001'）
  - 以6开头的股票 -> sh前缀（上交所）
  - 其他股票 -> sz前缀（深交所）
"""

from typing import List, Optional, Dict, Any
import time
import ssl
import pandas as pd
import akshare as ak
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timedelta
from .models import KLineData, StockData


# ---- 全局 Session（复用连接 + 自动重试） ----
def _create_robust_session() -> requests.Session:
    """创建带重试和SSL容错配置的Session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    # 尝试绑定 session 给 akshare（若支持）
    try:
        ak.session = session
    except Exception:
        pass
    return session


_AK_SESSION = _create_robust_session()


class AkshareDataFetcher:
    """
    基于AkShare的数据获取器
    
    【功能说明】
    1. 获取股票基础信息
    2. 获取K线历史数据
    3. 获取实时行情
    4. 获取板块/行业数据
    5. 获取涨幅榜、跌幅榜、成交额榜
    
    【使用方式】
    fetcher = AkshareDataFetcher()
    df = fetcher.get_top_gainers(20)
    """
    
    def __init__(self):
        self._stock_info_cache: Dict[str, pd.DataFrame] = {}
        self._index_list: List[str] = []  # 宽基指数列表
        self._spot_cache: Optional[pd.DataFrame] = None
        self._spot_cache_time: Optional[datetime] = None
    
    def _get_spot_data(self) -> pd.DataFrame:
        """
        获取并缓存实时行情数据（使用稳定的东方财富接口）
        """
        # 缓存5分钟
        if self._spot_cache is not None and self._spot_cache_time is not None:
            if (datetime.now() - self._spot_cache_time).seconds < 300:
                return self._spot_cache
        
        try:
            # 使用东方财富接口
            self._spot_cache = ak.stock_zh_a_spot_em()
            self._spot_cache_time = datetime.now()
            return self._spot_cache
        except Exception as e:
            print(f"东方财富接口失败，尝试备用接口: {e}")
            try:
                # 备用：使用新浪接口
                self._spot_cache = ak.stock_zh_a_spot()
                self._spot_cache_time = datetime.now()
                return self._spot_cache
            except Exception as e2:
                print(f"备用接口也失败: {e2}")
                return pd.DataFrame()
    
    def _format_stock_code(self, code: str) -> str:
        """
        格式化股票代码为 akshare 需要的格式
        
        Args:
            code: 6位股票代码
        
        Returns:
            格式化后的代码 (如: sh600000, sz000001)
        """
        code = code.strip().zfill(6)
        if code.startswith('6') or code in ['000001', '000300', '000016', '000905', '000852']:
            return f"sh{code}"
        else:
            return f"sz{code}"
    
    def _get_stock_code_pure(self, code: str) -> str:
        """获取纯数字股票代码"""
        return code.strip().zfill(6)
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict]:
        """
        获取实时行情
        
        Args:
            stock_code: 6位股票代码
        
        Returns:
            实时行情字典
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return None
            
            code = self._get_stock_code_pure(stock_code)
            result = df[df['代码'] == code]
            
            if result.empty:
                return None
            
            row = result.iloc[0]
            
            # 构建返回字典，处理可能的列名差异
            quote = {
                '代码': str(row.get('代码', '')),
                '名称': str(row.get('名称', '')),
                '现价': float(row.get('最新价', 0)) if pd.notna(row.get('最新价')) else 0,
                '涨幅%': float(row.get('涨跌幅', 0)) if pd.notna(row.get('涨跌幅')) else 0,
                '涨跌额': float(row.get('涨跌额', 0)) if pd.notna(row.get('涨跌额')) else 0,
                '总量': float(row.get('成交量', 0)) if pd.notna(row.get('成交量')) else 0,
                '总金额': float(row.get('成交额', 0)) if pd.notna(row.get('成交额')) else 0,
                '今开': float(row.get('今开', 0)) if pd.notna(row.get('今开')) else 0,
                '最高': float(row.get('最高', 0)) if pd.notna(row.get('最高')) else 0,
                '最低': float(row.get('最低', 0)) if pd.notna(row.get('最低')) else 0,
                '昨收': float(row.get('昨收', 0)) if pd.notna(row.get('昨收')) else 0,
                '市盈率(动态)': row.get('市盈率-动态'),
                '市净率': row.get('市净率'),
                'trade_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            return quote
        except Exception as e:
            print(f"获取实时行情失败: {e}")
            return None
    
    def get_kline_history(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
        period: str = "daily",
        timeout: float = 30.0,
        max_retries: int = 3
    ) -> List[KLineData]:
        """
        获取K线历史数据
        
        Args:
            stock_code: 6位股票代码
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 复权类型 qfq=前复权, hfq=后复权, ""
            period: 周期 daily/weekly/monthly
            timeout: 请求超时时间（秒），默认30秒
            max_retries: 最大重试次数，默认3次
        
        Returns:
            K线数据列表
        """
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        code = self._get_stock_code_pure(stock_code)
        
        df = None
        last_error = None
        
        # 1) 优先东方财富（重试）
        for attempt in range(max_retries):
            try:
                df = self._fetch_kline_raw(
                    symbol=code,
                    period=period,
                    start_date=start,
                    end_date=end,
                    adjust=adjust,
                    timeout=timeout
                )
                if df is not None and not df.empty:
                    break
            except Exception as e:
                last_error = e
                print(f"获取K线数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    timeout = timeout + 15
        
        # 2) 新浪兜底
        if df is None or df.empty:
            try:
                print("尝试新浪K线接口作为兜底...")
                df = self._fetch_kline_sina(
                    symbol=code,
                    start_date=start,
                    end_date=end,
                    timeout=timeout
                )
            except Exception as e2:
                print(f"新浪K线接口也失败: {e2}")
                last_error = e2
        
        # 3) akshare 原生
        if df is None or df.empty:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period=period,
                    start_date=start,
                    end_date=end,
                    adjust=adjust,
                    timeout=timeout
                )
            except Exception:
                pass
        
        if df is None or df.empty:
            if last_error:
                print(f"获取K线数据最终失败: {last_error}")
            return []
        
        results = []
        for _, row in df.iterrows():
            results.append(KLineData(
                date=str(row['日期'])[:10],
                code=code,
                name="",
                open=float(row['开盘']) if pd.notna(row['开盘']) else None,
                high=float(row['最高']) if pd.notna(row['最高']) else None,
                low=float(row['最低']) if pd.notna(row['最低']) else None,
                close=float(row['收盘']) if pd.notna(row['收盘']) else None,
                volume=float(row['成交量']) if pd.notna(row['成交量']) else None,
                amount=float(row['成交额']) if pd.notna(row['成交额']) else None,
                change_pct=float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None
            ))
        
        return results
    
    # ---- 新浪 K线 会话 ----
    _SINA_SESSION: Optional[requests.Session] = None

    @classmethod
    def _get_sina_session(cls) -> requests.Session:
        if cls._SINA_SESSION is None:
            cls._SINA_SESSION = requests.Session()
            cls._SINA_SESSION.verify = False
            cls._SINA_SESSION.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://finance.sina.com.cn",
            })
        return cls._SINA_SESSION

    def _fetch_kline_raw(
        self,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
        timeout: float
    ) -> Optional[pd.DataFrame]:
        """
        直接调用东方财富K线接口（绕过 akshare，用自定义 Session）
        """
        market_code = 1 if symbol.startswith("6") else 0
        adjust_dict = {"qfq": "1", "hfq": "2", "": "0"}
        period_dict = {"daily": "101", "weekly": "102", "monthly": "103"}
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": period_dict.get(period, "101"),
            "fqt": adjust_dict.get(adjust, "1"),
            "secid": f"{market_code}.{symbol}",
            "beg": start_date,
            "end": end_date,
        }
        r = _AK_SESSION.get(url, params=params, timeout=timeout)
        data_json = r.json()
        if not (data_json.get("data") and data_json["data"].get("klines")):
            return None
        temp_df = pd.DataFrame(
            [item.split(",") for item in data_json["data"]["klines"]]
        )
        temp_df.columns = [
            "日期", "开盘", "收盘", "最高", "最低",
            "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率",
            "股票代码",
        ]
        temp_df["股票代码"] = symbol
        return temp_df

    def _fetch_kline_sina(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeout: float
    ) -> Optional[pd.DataFrame]:
        """
        新浪 K线接口（备用），数据格式：
        [{"day":"2024-01-02","open":"...","high":"...","low":"...","close":"...","volume":"..."}, ...]
        """
        prefix = "sh" if symbol.startswith("6") else "sz"
        sina_symbol = f"{prefix}{symbol}"

        # 计算需要的记录数：日期跨度天数 + 100 条余量，最少取 300 条
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            delta_days = (ed - sd).days + 100
        except Exception:
            delta_days = 800
        datalen = max(delta_days, 300, 7)

        # scale: 240=日K
        url = (
            "https://money.finance.sina.com.cn/quotes_service/api/"
            "json_v2.php/CN_MarketData.getKLineData"
        )
        params = {
            "symbol": sina_symbol,
            "scale": "240",
            "ma": "no",
            "datalen": datalen,
        }
        session = self._get_sina_session()
        r = session.get(url, params=params, timeout=timeout)
        raw_data = r.json()

        if not raw_data or not isinstance(raw_data, list):
            return None

        rows = []
        for item in raw_data:
            try:
                day_val = item["day"]
                # 仅保留日期范围内的数据
                if day_val < start_date or day_val > end_date:
                    continue
                rows.append({
                    "日期": day_val,
                    "开盘": item["open"],
                    "收盘": item["close"],
                    "最高": item["high"],
                    "最低": item["low"],
                    "成交量": item["volume"],  # 手
                    "成交额": "0",
                    "振幅": "0",
                    "涨跌幅": "0",
                    "涨跌额": "0",
                    "换手率": "0",
                })
            except KeyError:
                continue

        if not rows:
            return None

        df = pd.DataFrame(rows)
        df["股票代码"] = symbol
        return df

    def get_kline_dataframe(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
        period: str = "daily",
        timeout: float = 30.0,
        max_retries: int = 3
    ) -> pd.DataFrame:
        """
        获取K线DataFrame
        
        Args:
            stock_code: 6位股票代码
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            adjust: 复权类型
            period: 周期 daily/weekly/monthly
            timeout: 请求超时时间（秒），默认30秒
            max_retries: 最大重试次数，默认3次
        
        Returns:
            DataFrame（列名已转换为系统兼容格式）
        """
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"
        code = self._get_stock_code_pure(stock_code)
        
        df = None
        last_error = None
        
        # 1) 优先东方财富（重试）
        for attempt in range(max_retries):
            try:
                df = self._fetch_kline_raw(
                    symbol=code,
                    period=period,
                    start_date=start,
                    end_date=end,
                    adjust=adjust,
                    timeout=timeout
                )
                if df is not None and not df.empty:
                    break
            except Exception as e:
                last_error = e
                print(f"东方财富K线获取失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  {wait}秒后重试...")
                time.sleep(wait)
                timeout = timeout + 15

        # 2) 东方财富失败 → 新浪兜底（一次）
        if df is None or df.empty:
            try:
                print("尝试新浪K线接口作为兜底...")
                df = self._fetch_kline_sina(
                    symbol=code,
                    start_date=start,
                    end_date=end,
                    timeout=timeout
                )
            except Exception as e2:
                print(f"新浪K线接口也失败: {e2}")
                last_error = e2

        # 3) 最后尝试 akshare 原生方法
        if df is None or df.empty:
            try:
                df = ak.stock_zh_a_hist(
                    symbol=code,
                    period=period,
                    start_date=start,
                    end_date=end,
                    adjust=adjust,
                    timeout=timeout
                )
            except Exception:
                pass

        if df is None or df.empty:
            if last_error:
                print(f"获取K线DataFrame最终失败: {last_error}")
            return pd.DataFrame()

        # 重命名列为图表需要的格式
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount',
            '涨跌幅': 'change_pct',
            '涨跌额': 'change',
            '换手率': 'turnover',
            '振幅': 'amplitude'
        }

        df = df.rename(columns=column_mapping)
        df['code'] = code

        return df
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        return self.get_realtime_quote(stock_code)
    
    def get_top_gainers(self, limit: int = 20) -> pd.DataFrame:
        """
        获取涨幅榜
        
        Args:
            limit: 返回数量
        
        Returns:
            涨幅榜 DataFrame
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            df = df[df['涨跌幅'] > 0].sort_values('涨跌幅', ascending=False).head(limit)
            
            # 返回原始列名格式
            return df[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '今开', '最高', '最低', '昨收']].copy()
        except Exception as e:
            print(f"获取涨幅榜失败: {e}")
            return pd.DataFrame()
    
    def get_top_losers(self, limit: int = 20) -> pd.DataFrame:
        """
        获取跌幅榜
        
        Args:
            limit: 返回数量
        
        Returns:
            跌幅榜 DataFrame
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            df = df[df['涨跌幅'] < 0].sort_values('涨跌幅', ascending=True).head(limit)
            
            return df[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '今开', '最高', '最低', '昨收']].copy()
        except Exception as e:
            print(f"获取跌幅榜失败: {e}")
            return pd.DataFrame()
    
    def get_top_volume(self, limit: int = 20) -> pd.DataFrame:
        """
        获取成交额榜
        
        Args:
            limit: 返回数量
        
        Returns:
            成交额榜 DataFrame
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            # 过滤掉成交额为0的
            df = df[df['成交额'] > 0]
            df = df.sort_values('成交额', ascending=False).head(limit)
            
            return df[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '今开', '最高', '最低', '昨收']].copy()
        except Exception as e:
            print(f"获取成交额榜失败: {e}")
            return pd.DataFrame()
    
    def get_market_overview(self) -> pd.DataFrame:
        """
        获取市场概览
        
        Returns:
            市场概览 DataFrame
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            total = len(df)
            up = len(df[df['涨跌幅'] > 0])
            down = len(df[df['涨跌幅'] < 0])
            avg_change = df['涨跌幅'].mean() if total > 0 else 0
            total_amount = df['成交额'].sum()
            
            return pd.DataFrame([{
                'total_stocks': total,
                'up_stocks': up,
                'down_stocks': down,
                'avg_change': avg_change,
                'total_amount': total_amount
            }])
        except Exception as e:
            print(f"获取市场概览失败: {e}")
            return pd.DataFrame()
    
    def get_sector_stocks(self, sector: str, limit: int = 50) -> pd.DataFrame:
        """
        获取某板块/行业的股票列表
        
        Args:
            sector: 板块/行业名称关键字
            limit: 返回数量
        
        Returns:
            股票列表 DataFrame
        """
        try:
            # 获取行业板块数据
            df = ak.stock_board_industry_name_em()
            
            # 查找匹配的行业
            matching = df[df['板块名称'].str.contains(sector, case=False, na=False)]
            
            if matching.empty:
                return pd.DataFrame()
            
            # 获取该行业下的股票
            industry_name = matching.iloc[0]['板块名称']
            stocks_df = ak.stock_board_industry_cons_em(symbol=industry_name)
            
            return stocks_df.head(limit)
        except Exception as e:
            print(f"获取板块股票失败: {e}")
            return pd.DataFrame()
    
    def get_stocks_by_conditions(
        self,
        min_amount: float = 0,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None,
        industry: Optional[str] = None,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        根据条件筛选股票
        
        Args:
            min_amount: 最小成交额（万元）
            min_change: 最小涨跌幅
            max_change: 最大涨跌幅
            industry: 行业名称
            limit: 返回数量
        
        Returns:
            符合条件的股票 DataFrame
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            # 过滤条件
            if min_amount > 0:
                df = df[df['成交额'] >= min_amount * 10000]
            
            if min_change is not None:
                df = df[df['涨跌幅'] >= min_change]
            
            if max_change is not None:
                df = df[df['涨跌幅'] <= max_change]
            
            df = df.sort_values('成交额', ascending=False).head(limit)
            
            return df[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额']].copy()
        except Exception as e:
            print(f"条件筛选股票失败: {e}")
            return pd.DataFrame()
    
    def get_index_components(self, index_code: str = "000300") -> List[str]:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码 (000300=沪深300, 000016=上证50, 等)
        
        Returns:
            成分股代码列表
        """
        try:
            if index_code == "000300":
                df = ak.stock_index_cons_sina(symbol="sh000300")
            else:
                df = ak.stock_index_cons_sina(symbol=f"sh{index_code}")
            
            return df['代码'].tolist() if not df.empty else []
        except Exception as e:
            print(f"获取指数成分股失败: {e}")
            return []
    
    def get_all_stocks(self, limit: int = 500) -> pd.DataFrame:
        """
        获取全部股票列表（按股票代码排序）
        
        Args:
            limit: 返回数量限制
        
        Returns:
            股票列表 DataFrame，按代码排序
        """
        try:
            df = self._get_spot_data()
            if df.empty:
                return pd.DataFrame()
            
            # 过滤掉成交额为0或无名称的（可能是停牌或无效数据）
            df = df[(df['成交额'] > 0) & (df['名称'].notna()) & (df['名称'] != '')]
            
            # 按纯数字代码排序（去除交易所前缀）
            df['code_numeric'] = df['代码'].astype(str).str.extract(r'(\d+)')[0].astype(int)
            df = df.sort_values('code_numeric', ascending=True)
            df = df.drop(columns=['code_numeric'])
            
            return df[['代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', '今开', '最高', '最低', '昨收']].head(limit).copy()
        except Exception as e:
            print(f"获取全部股票失败: {e}")
            return pd.DataFrame()
    
    def preload_spot_data(self) -> bool:
        """
        预加载实时行情数据到缓存
        
        在页面加载时调用，提前获取数据，
        后续 get_top_gainers / get_top_losers 等方法直接使用缓存。
        
        Returns:
            是否加载成功
        """
        try:
            df = self._get_spot_data()
            return not df.empty
        except Exception:
            return False

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            self._get_spot_data()
            return not self._spot_cache.empty
        except Exception:
            return False


# 全局实例
akshare_fetcher = AkshareDataFetcher()
