"""
业务层数据获取器模块:

【模块功能】
封装数据获取逻辑，提供统一的业务层数据接口，支持缓存优化。

【数据来源】
底层使用AkShare数据获取器，本模块进行业务层封装和过滤逻辑。

【主要功能】
1. 获取股票实时行情（get_stock_spot）
2. 获取K线历史数据（get_stock_kline / get_stock_kline_dataframe）
3. 获取涨幅榜/跌幅榜/成交额榜（get_top_gainers/losers/volume）
4. 获取板块股票列表（get_sector_stocks）
5. 获取市场概览（get_market_overview）
6. 根据条件筛选股票（filter_stocks）

【缓存策略】
- 实时行情数据缓存5分钟
- 避免频繁调用API，提升响应速度

【字段映射说明】
- 查询条件字段 -> akshare实际列名
- 市值字段单位是元 (500亿 = 500e8)
"""

from typing import List, Optional, Dict, Any
import pandas as pd
from data_layer.models import StockData, KLineData, QueryResult


class DataFetcher:
    """
    数据获取器 - 业务层封装
    
    【功能说明】
    1. 封装数据获取细节，简化业务层调用
    2. 提供统一的接口，屏蔽底层差异
    3. 支持缓存优化，提升性能
    
    【使用方式】
    fetcher = DataFetcher(akshare_fetcher)
    df = fetcher.get_top_gainers(20)
    """
    
    def __init__(self, akshare_fetcher=None):
        """
        初始化数据获取器
        
        Args:
            akshare_fetcher: AkShare数据获取器实例
        """
        self._fetcher = akshare_fetcher
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
    
    def get_stock_spot(
        self,
        stock_code: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
        
        Returns:
            实时行情字典
        """
        if self._fetcher:
            return self._fetcher.get_realtime_quote(stock_code)
        return None
    
    def get_stock_kline(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> List[KLineData]:
        """
        获取股票K线数据
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            adjust: 复权类型 (qfq/hfq/"")
        
        Returns:
            K线数据列表
        """
        if self._fetcher:
            return self._fetcher.get_kline_history(
                stock_code, start_date, end_date, adjust
            )
        return []
    
    def get_stock_kline_dataframe(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票K线DataFrame
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            adjust: 复权类型
        
        Returns:
            K线DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_kline_dataframe(
                stock_code, start_date, end_date, adjust
            )
        return pd.DataFrame()
    
    def get_top_gainers(
        self,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        获取涨幅榜
        
        Args:
            limit: 返回条数
        
        Returns:
            涨幅榜DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_top_gainers(limit)
        return pd.DataFrame()
    
    def get_top_losers(
        self,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        获取跌幅榜
        
        Args:
            limit: 返回条数
        
        Returns:
            跌幅榜DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_top_losers(limit)
        return pd.DataFrame()
    
    def get_top_volume(
        self,
        limit: int = 20
    ) -> pd.DataFrame:
        """
        获取成交额榜
        
        Args:
            limit: 返回条数
        
        Returns:
            成交额榜DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_top_volume(limit)
        return pd.DataFrame()
    
    def get_sector_stocks(
        self,
        sector: str,
        limit: int = 50
    ) -> pd.DataFrame:
        """
        获取某板块的股票列表
        
        Args:
            sector: 板块名称
            limit: 返回条数
        
        Returns:
            股票列表DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_sector_stocks(sector, limit)
        return pd.DataFrame()
    
    def get_market_overview(self) -> pd.DataFrame:
        """
        获取市场概览
        
        Returns:
            市场概览DataFrame
        """
        if self._fetcher:
            return self._fetcher.get_market_overview()
        return pd.DataFrame()
    
    def get_index_components(
        self,
        index_code: str = "000300"
    ) -> List[str]:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码
        
        Returns:
            成分股代码列表
        """
        if self._fetcher:
            return self._fetcher.get_index_components(index_code)
        return []
    
    def filter_stocks(
        self,
        filters: List[Dict[str, Any]],
        limit: int = 50
    ) -> QueryResult:
        """
        根据条件筛选股票
        
        Args:
            filters: 筛选条件列表
            limit: 返回条数限制
        
        Returns:
            QueryResult查询结果
        """
        if not self._fetcher:
            return QueryResult.error("数据获取器未初始化")
        
        try:
            # 获取全量实时行情
            df = self._fetcher._get_spot_data()
            
            if df.empty:
                return QueryResult.ok([], "未找到数据")
            
            # 应用过滤条件
            filtered_df = self._apply_filters(df, filters)
            
            # 截断
            total_count = len(filtered_df)
            result_df = filtered_df.head(limit)
            
            return QueryResult.ok(
                result_df,
                f"找到 {total_count} 只符合条件的股票",
                total=total_count
            )
            
        except Exception as e:
            return QueryResult.error(f"筛选失败: {str(e)}")
    
    def _apply_filters(
        self,
        df: pd.DataFrame,
        filters: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        应用过滤条件
        
        Args:
            df: 原始数据
            filters: 过滤条件
        
        Returns:
            过滤后的数据
        """
        result = df.copy()
        
        # 字段名映射 (查询条件字段 -> akshare列名)
        field_mapping = {
            # 价格类
            '现价': '最新价',
            '价格': '最新价',
            '今开': '今开',
            '最高': '最高',
            '最低': '最低',
            '昨收': '昨收',
            # 涨跌幅类
            '涨幅%': '涨跌幅',
            '涨跌幅': '涨跌幅',
            '涨跌额': '涨跌额',
            # 成交类
            '成交额': '成交额',
            '总金额': '成交额',
            '成交量': '成交量',
            # 市值类 (单位：元)
            '总市值': '总市值',
            '流通市值': '流通市值',
            '市值': '总市值',
            # 估值类
            '市盈率': '市盈率-动态',
            '市盈(动)': '市盈率-动态',
            '市净率': '市净率',
            # 行业类
            '细分行业': '细分行业',
            '行业': '细分行业',
            '板块': '细分行业',
            '地区': '地区',
            # 其他
            '换手率': '换手率',
            '换手%': '换手率',
        }
        
        for f in filters:
            field = f.get('field', '')
            op = f.get('op', '=')
            value = f.get('value')
            days_ago = f.get('days_ago', 0)
            
            # 跳过需要历史数据的条件
            if days_ago and days_ago > 0:
                continue
            
            # 映射字段名
            mapped_field = field_mapping.get(field, field)
            
            if mapped_field not in result.columns:
                continue
            
            # 执行过滤
            if op in ('>', '>='):
                col = result[mapped_field]
                result = result[col >= value] if op == '>=' else result[col > value]
            elif op in ('<', '<='):
                col = result[mapped_field]
                result = result[col <= value] if op == '<=' else result[col < value]
            elif op == '=':
                result = result[result[mapped_field] == value]
            elif op.upper() == 'LIKE':
                result = result[result[mapped_field].astype(str).str.contains(str(value), na=False)]
        
        return result
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_time.clear()


# 全局实例（延迟初始化）
_data_fetcher: Optional[DataFetcher] = None


def get_data_fetcher(akshare_fetcher=None) -> DataFetcher:
    """获取全局数据获取器实例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher(akshare_fetcher)
    elif akshare_fetcher is not None:
        _data_fetcher._fetcher = akshare_fetcher
    return _data_fetcher
