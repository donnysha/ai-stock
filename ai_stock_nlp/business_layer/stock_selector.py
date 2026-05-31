"""
选股执行器模块:

【模块功能】
执行固化选股策略和灵活回测查询，是业务层的核心组件。

【两种选股模式】
1. 选股（select_stocks）
   - 基于当前时间数据
   - 用于实际操作决策
   - 支持多条件筛选

2. 灵活回测（flex_backtest）
   - 支持自定义时序条件
   - 可指定days_ago进行历史查询
   - 用于策略验证和回测

【筛选条件格式】
{
    'filters': [
        {'field': '成交额', 'op': '>=', 'value': 50000000},
        {'field': '涨幅%', 'op': '>=', 'value': 9.5},
        {'field': '细分行业', 'op': 'LIKE', 'value': '%科技%'}
    ],
    'limit': 50  # 可选
}

【字段名映射】
- 成交额/总金额 -> 成交额
- 涨幅%/涨跌幅 -> 涨跌幅
- 现价/价格 -> 最新价
- 市盈率 -> 市盈率-动态
- 总市值/流通市值 -> 直接使用akshare列名
"""

from typing import Dict, List, Optional, Any
import pandas as pd
from data_layer.models import StockData, QueryResult
from data_layer.financial_data_fetcher import get_financial_fetcher


class StockSelector:
    """
    选股执行器
    
    【功能说明】
    1. 执行选股查询（当前时间实时数据 + 财报数据库）
    2. 执行灵活回测查询（自定义时序条件）
    3. 返回标准格式的选股结果（QueryResult）
    
    【双源查询机制】
    - source="market": 从AkShare实时行情获取
    - source="financial": 从MySQL stock_financial_data获取
    - 同时存在两类条件时，取交集（都满足的股票）
    
    【使用流程】
    1. 初始化时注入data_fetcher
    2. 调用select_stocks或flex_backtest
    3. 返回QueryResult，包含success/data/message等字段
    """
    
    def __init__(self, data_fetcher=None):
        """初始化选股执行器"""
        self.data_fetcher = data_fetcher
        self.financial_fetcher = get_financial_fetcher()
    
    def select_stocks(self, params: Dict) -> QueryResult:
        """
        执行选股（当前时间 + 财报数据）

        【双源查询流程】
        1. 拆分filters为market_filters和financial_filters
        2. 从AkShare获取全量实时行情，应用market_filters
        3. 如有financial_filters，从MySQL获取财报数据，应用financial_filters
        4. 取两者交集（股票代码匹配）
        5. 合并财报列到结果中

        Args:
            params: {
                'filters': [{field, op, value, source?}, ...],
                'limit': 可选，返回数量限制，默认50
            }
        
        Returns:
            QueryResult
        """
        try:
            filters = params.get('filters', [])
            limit = params.get('limit', 50)
            
            if not filters:
                return QueryResult.error("缺少筛选条件")
            
            if self.data_fetcher is None:
                return QueryResult.error("数据获取器未初始化")
            
            # ====== 步骤1: 拆分filters ======
            market_filters = [f for f in filters if f.get('source', 'market') == 'market']
            financial_filters = [f for f in filters if f.get('source') == 'financial']
            
            has_financial = len(financial_filters) > 0
            has_market = len(market_filters) > 0
            
            print(f"\n=== Stock Select Debug ===")
            print(f"Market filters: {len(market_filters)}, Financial filters: {len(financial_filters)}")
            
            # ====== 步骤2: 行情筛选 ======
            market_df = pd.DataFrame()
            if has_market:
                df = self.data_fetcher._get_spot_data()
                if df.empty:
                    return QueryResult.ok([], "未获取到行情数据", total=0)
                
                print(f"Market data rows: {len(df)}, columns: {df.columns.tolist()}")
                market_df = self._apply_filters(df, market_filters)
                print(f"After market filter: {len(market_df)} stocks")
            else:
                # 没有行情条件时，获取全量作为基准
                df = self.data_fetcher._get_spot_data()
                if not df.empty:
                    market_df = df
                    print(f"No market filters, using all {len(market_df)} stocks as base")
            
            # 提前检查行情条件结果
            if has_market and market_df.empty:
                return QueryResult.ok([], "没有符合技术面条件的股票", total=0)
            
            # ====== 步骤3: 财报筛选 ======
            financial_df = pd.DataFrame()
            if has_financial:
                # 获取有行情数据的股票代码列表（缩小财报查询范围）
                stock_codes = None
                if not market_df.empty and '代码' in market_df.columns:
                    stock_codes = market_df['代码'].astype(str).str.zfill(6).tolist()
                    print(f"Querying financials for {len(stock_codes)} market-qualified stocks...")
                
                fin_df = self.financial_fetcher.filter_by_financials(
                    financial_filters,
                    stock_codes=stock_codes
                )
                
                if not fin_df.empty:
                    print(f"Financial filter result: {len(fin_df)} stocks")
                    # 确保stock_code列存在且为字符串
                    fin_df['stock_code'] = fin_df['stock_code'].astype(str).str.zfill(6)
                    financial_df = fin_df
                else:
                    print("No stocks passed financial filters")
            
            # ====== 步骤4: 合并结果 ======
            if has_market and has_financial:
                # 取行情和财报的交集
                if financial_df.empty:
                    return QueryResult.ok([], "没有同时满足行情和财报条件的股票", total=0)
                
                # 统一股票代码格式
                market_df['代码_str'] = market_df['代码'].astype(str).str.zfill(6)
                
                # 获取通过财报筛选的股票代码
                fin_codes = set(financial_df['stock_code'].tolist())
                market_df = market_df[market_df['代码_str'].isin(fin_codes)]
                market_df = market_df.drop(columns=['代码_str'])
                
                print(f"After intersection: {len(market_df)} stocks")
                
                # 合并财报列到行情结果中
                if not market_df.empty:
                    market_df = self._merge_financial_data(market_df, financial_df)
                    result_df = market_df
                else:
                    result_df = market_df
                    
            elif has_financial and not has_market:
                # 只有财报条件，没有行情条件
                result_df = financial_df
                # 重命名stock_code列以匹配行情数据格式
                if not result_df.empty:
                    result_df = result_df.rename(columns={
                        'stock_code': '代码',
                        'stock_name': '名称'
                    })
                    # 尝试补充行情数据
                    if not market_df.empty:
                        result_df = self._merge_market_data(result_df, market_df)
            else:
                # 只有行情条件
                result_df = market_df
            
            # ====== 步骤5: 返回结果 ======
            if result_df.empty:
                return QueryResult.ok([], "未找到符合条件的股票", total=0)
            
            total_count = len(result_df)
            result_df = result_df.head(limit)
            
            return QueryResult.ok(
                result_df,
                f"找到 {total_count} 只符合条件的股票",
                total=total_count
            )
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return QueryResult.error(f"选股执行失败: {str(e)}")
    
    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """
        根据筛选条件过滤数据
        
        Args:
            df: 原始数据
            filters: 筛选条件
        
        Returns:
            过滤后的数据
        """
        result = df.copy()
        
        # 字段名映射（条件字段名 -> akshare实际字段名）
        field_mapping = {
            # 成交额/总金额 -> 成交额 (akshare列名)
            '成交额': '成交额',
            '总金额': '成交额',
            # 涨跌幅/涨幅% -> 涨跌幅 (akshare列名)
            '涨幅%': '涨跌幅',
            '涨跌幅': '涨跌幅',
            # 现价/价格 -> 最新价 (akshare列名)
            '现价': '最新价',
            '价格': '最新价',
            # 市盈率
            '市盈率': '市盈率-动态',
            '市盈(动)': '市盈率-动态',
            # 市值字段 (akshare直接使用列名)
            '总市值': '总市值',
            '流通市值': '流通市值',
            '市值': '总市值',
            # 换手率
            '换手率': '换手率',
            '换手%': '换手率',
        }
        
        for f in filters:
            field = f.get('field', '')
            op = f.get('op', '=')
            value = f.get('value')
            days_ago = f.get('days_ago', 0)
            
            # 跳过需要历史数据的条件（实时行情只有今天）
            if days_ago and days_ago > 0:
                continue
            
            # 映射字段名
            mapped_field = field_mapping.get(field, field)
            
            if mapped_field not in result.columns:
                # 打印警告信息，帮助调试
                print(f"[WARN] Field '{mapped_field}' not in data columns, available: {result.columns.tolist()}")
                continue
            
            # 执行过滤
            if op == '>' or op == '>=':
                result = result[result[mapped_field] >= value] if op == '>=' else result[result[mapped_field] > value]
            elif op == '<' or op == '<=':
                result = result[result[mapped_field] <= value] if op == '<=' else result[result[mapped_field] < value]
            elif op == '=':
                result = result[result[mapped_field] == value]
            elif op.upper() == 'LIKE':
                result = result[result[mapped_field].astype(str).str.contains(str(value), na=False)]
        
        return result
    
    def flex_backtest(self, params: Dict) -> QueryResult:
        """
        执行灵活回测查询
        
        Args:
            params: {
                filters: [{"field": "...", "op": "...", "value": ..., "days_ago": n}, ...],
                target_day: 目标天数（默认0=今天）,
                limit: 可选，返回数量限制
            }
        
        Returns:
            QueryResult: 包含回测结果的QueryResult
        """
        try:
            filters = params.get('filters', [])
            target_day = params.get('target_day', 0)
            limit = params.get('limit', 1000)
            
            if not filters:
                return QueryResult.error("缺少筛选条件")
            
            # 从 akshare 获取全量实时行情
            if self.data_fetcher is None:
                return QueryResult.error("数据获取器未初始化")
            
            # 获取全量数据而不是排行榜
            df = self.data_fetcher._get_spot_data()
            
            if df.empty:
                return QueryResult.ok([], "未找到符合条件的股票")
            
            # 调试信息
            print(f"\n=== Backtest Debug ===")
            print(f"Data rows: {len(df)}")
            print(f"Data columns: {df.columns.tolist()}")
            
            # 检查关键列是否存在
            key_cols = ['总市值', '流通市值', '成交额', '涨跌幅', '细分行业']
            for col in key_cols:
                exists = col in df.columns
                print(f"  {'[OK]' if exists else '[X]'} {col}: {'exists' if exists else 'not exists'}")
            print(f"=====================\n")
            
            # 根据 filters 过滤数据
            filtered_df = self._apply_filters(df, filters)
            
            if filtered_df.empty:
                return QueryResult.ok([], "未找到符合条件的股票")
            
            return QueryResult.ok(filtered_df, f"找到 {len(filtered_df)} 只符合条件的股票")
        
        except Exception as e:
            return QueryResult.error(f"回测执行失败: {str(e)}")
    
    def get_stock_history(self, stock_codes: List[str], start_date: str, end_date: str) -> QueryResult:
        """
        获取股票历史数据
        
        Args:
            stock_codes: 股票代码列表
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
        
        Returns:
            QueryResult: 包含历史数据的QueryResult
        """
        try:
            if not stock_codes:
                return QueryResult.error("缺少股票代码")
            
            if self.data_fetcher is None:
                return QueryResult.error("数据获取器未初始化")
            
            # 暂时只支持单个股票
            df = self.data_fetcher.get_kline_dataframe(stock_codes[0], start_date, end_date)
            
            if df.empty:
                return QueryResult.ok([], "未找到历史数据")
            
            return QueryResult.ok(df, f"找到 {len(df)} 条历史数据")
        
        except Exception as e:
            return QueryResult.error(f"获取历史数据失败: {str(e)}")
    
    def _enrich_results(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        丰富查询结果
        
        Args:
            df: 查询结果DataFrame
        
        Returns:
            丰富后的DataFrame
        """
        result = df.copy()
        
        # 格式化成交额（万元）
        if '总金额' in result.columns:
            result['成交额_万'] = (result['总金额'] / 10000).round(2)
        
        # 格式化涨跌幅
        if '涨幅%' in result.columns:
            result['涨跌幅_显示'] = result['涨幅%'].apply(
                lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A"
            )
        
        return result
    
    def _merge_financial_data(
        self,
        market_df: pd.DataFrame,
        financial_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        将财报数据合并到行情DataFrame

        Args:
            market_df: 行情数据
            financial_df: 财报数据（含stock_code列）

        Returns:
            合并后的DataFrame
        """
        # 准备合并键
        market_df = market_df.copy()
        market_df['_code_str'] = market_df['代码'].astype(str).str.zfill(6)

        # 选择有用的财报列进行合并
        fin_cols = ['stock_code', 'roe', 'net_margin', 'gross_margin',
                    'revenue_growth', 'profit_growth', 'debt_ratio',
                    'current_ratio', 'operating_cash_flow', 'net_profit',
                    'basic_eps', 'revenue', 'report_date', 'fiscal_year']

        fin_available = [c for c in fin_cols if c in financial_df.columns]
        fin_subset = financial_df[fin_available].copy()
        fin_subset['stock_code'] = fin_subset['stock_code'].astype(str).str.zfill(6)

        # 中文列名转换
        rename_map = {
            'roe': 'ROE(%)',
            'net_margin': '销售净利率(%)',
            'gross_margin': '毛利率(%)',
            'revenue_growth': '营收增速(%)',
            'profit_growth': '净利润增速(%)',
            'debt_ratio': '资产负债率(%)',
            'current_ratio': '流动比率',
            'operating_cash_flow': '经营性现金流(万)',
            'net_profit': '归母净利润(万)',
            'basic_eps': '每股收益',
            'revenue': '营业总收入(万)',
            'report_date': '财报报告期',
            'fiscal_year': '财年',
        }

        fin_subset = fin_subset.rename(columns=rename_map)

        # LEFT JOIN: 以行情数据为主
        result = market_df.merge(
            fin_subset,
            left_on='_code_str',
            right_on='stock_code',
            how='left',
            suffixes=('', '_fin')
        )

        # 清理临时列
        result = result.drop(columns=['_code_str'], errors='ignore')
        if 'stock_code' in result.columns:
            result = result.drop(columns=['stock_code'], errors='ignore')

        return result

    def _merge_market_data(
        self,
        financial_df: pd.DataFrame,
        market_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        将行情数据合并到财报DataFrame

        Args:
            financial_df: 财报数据
            market_df: 行情数据

        Returns:
            合并后的DataFrame
        """
        market_df = market_df.copy()
        market_df['_code_str'] = market_df['代码'].astype(str).str.zfill(6)

        # 选择行情列
        mkt_cols = ['_code_str', '名称', '最新价', '涨跌幅', '涨跌额',
                    '成交额', '成交量', '总市值', '流通市值',
                    '市盈率-动态', '市净率', '换手率', '细分行业', '地区']
        mkt_available = [c for c in mkt_cols if c in market_df.columns]
        mkt_subset = market_df[mkt_available].copy()

        result = financial_df.merge(
            mkt_subset,
            left_on='stock_code',
            right_on='_code_str',
            how='left',
            suffixes=('', '_mkt')
        )

        result = result.drop(columns=['_code_str'], errors='ignore')

        # 重命名行情列
        mkt_rename = {
            '最新价': '最新价',
            '涨跌幅': '涨跌幅',
            '涨跌额': '涨跌额',
            '成交额': '成交额',
            '成交量': '成交量',
            '总市值': '总市值',
            '市盈率-动态': '市盈率-动态',
            '市净率': '市净率',
            '细分行业': '细分行业',
        }
        # 确保代码和名称在最前面
        cols_order = ['stock_code', 'stock_name']
        for c in result.columns:
            if c not in cols_order:
                cols_order.append(c)
        result = result[[c for c in cols_order if c in result.columns]]

        return result

    def validate_filters(self, filters: List[Dict]) -> tuple:
        """
        验证筛选条件
        
        Args:
            filters: 筛选条件数组
        
        Returns:
            (is_valid, error_message)
        """
        valid_market_fields = [
            '成交额', '总金额', '现价', '价格', '涨幅%', '涨跌幅',
            '市盈率', '市盈(动)', '细分行业', '地区', '市净率',
            '3日涨幅%', '5日涨幅%', '10日涨幅%', '20日涨幅%',
            '流通市值', '总市值', '换手率', '量比', '代码',
            '最新价', '涨跌额', '今开', '最高', '最低', '昨收',
            '风险标签', '日成交额下限',
        ]

        valid_financial_fields = [
            '净资产收益率ROE', 'ROE', '销售净利率', '净利率',
            '毛利率', '基本每股收益', 'EPS',
            '资产负债率', '负债率', '流动比率',
            '经营性现金流', '现金流',
            '营收增速', '净利润增速', '利润增速',
            '归母净利润', '净利润',
            '股息率', '分红连续性',
        ]

        all_valid_fields = valid_market_fields + valid_financial_fields
        valid_ops = ['>', '<', '>=', '<=', '=', 'LIKE', '!=']
        
        for f in filters:
            if 'field' not in f:
                return False, "缺少field字段"
            
            if f['field'] not in all_valid_fields:
                return False, f"不支持的字段: {f['field']}"
            
            if 'op' not in f:
                return False, "缺少op字段"
            
            if f['op'].upper() not in valid_ops:
                return False, f"不支持的操作符: {f['op']}"
            
            if 'value' not in f:
                return False, "缺少value字段"
        
        return True, None
