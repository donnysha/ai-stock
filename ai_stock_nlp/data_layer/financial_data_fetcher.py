"""
财报数据获取器模块

【模块功能】
从MySQL的stock_financial_data表中查询股票财报数据，用于价值投资选股。

【主要功能】
1. 获取单只/多只股票的最新财报数据
2. 根据财务指标筛选股票
3. 支持多期数据对比（ROE连续3年等）

【字段映射】
用户筛选字段 -> 数据库字段:
- 净资产收益率ROE -> roe
- 销售净利率 -> net_margin
- 毛利率 -> gross_margin
- 资产负债率 -> debt_ratio
- 流动比率 -> current_ratio
- 营收增速 -> revenue_growth
- 净利润增速 -> profit_growth
- 基本每股收益 -> basic_eps
- 经营性现金流 -> operating_cash_flow
- 归母净利润 -> net_profit
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from .db_connection import get_db_connection


class FinancialDataFetcher:
    """
    财报数据获取器

    【功能说明】
    1. 从stock_financial_data表获取最新财报数据
    2. 支持按财务指标筛选股票
    3. 返回DataFrame格式结果

    【使用示例】
    fetcher = FinancialDataFetcher()
    df = fetcher.get_latest_financials(['000001', '000002'])
    result = fetcher.filter_by_financials([
        {'field': '净资产收益率ROE', 'op': '>=', 'value': 12}
    ])
    """

    # 财务字段映射：用户输入字段 -> 数据库列名
    FIELD_MAPPING = {
        # 盈利质量
        '净资产收益率ROE': 'roe',
        'ROE': 'roe',
        'roe': 'roe',
        '销售净利率': 'net_margin',
        '净利率': 'net_margin',
        '毛利率': 'gross_margin',
        '基本每股收益': 'basic_eps',
        '每股收益': 'basic_eps',
        'EPS': 'basic_eps',
        # 财务健康
        '资产负债率': 'debt_ratio',
        '负债率': 'debt_ratio',
        '流动比率': 'current_ratio',
        '经营性现金流': 'operating_cash_flow',
        '现金流': 'operating_cash_flow',
        # 成长
        '营收增速': 'revenue_growth',
        '营业收入增速': 'revenue_growth',
        '净利润增速': 'profit_growth',
        '利润增速': 'profit_growth',
        # 归母净利润
        '归母净利润': 'net_profit',
        '净利润': 'net_profit',
    }

    # 股息率字段（需要从其他表获取，暂时映射）
    DIVIDEND_FIELD = '股息率'
    DIVIDEND_CONTINUITY = '分红连续性'

    def __init__(self):
        self.db = get_db_connection()

    def get_latest_financials(
        self,
        stock_codes: Optional[List[str]] = None,
        report_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取最新一期财报数据

        【查询逻辑】
        1. 使用子查询获取每只股票的最新report_date
        2. JOIN获取完整数据行
        3. 默认获取年报数据

        Args:
            stock_codes: 股票代码列表，None表示全量
            report_type: 报告类型过滤（年报/季报），None表示不限

        Returns:
            财报数据DataFrame
        """
        try:
            # 构建查询条件
            code_filter = ""
            params_list = []

            if stock_codes:
                placeholders = ','.join(['%s'] * len(stock_codes))
                code_filter = f"AND a.stock_code IN ({placeholders})"
                params_list = list(stock_codes)

            if report_type:
                code_filter += " AND a.report_type = %s"
                params_list.append(report_type)

            # 获取每只股票最新财报
            sql = f"""
            SELECT a.*
            FROM stock_financial_data a
            INNER JOIN (
                SELECT stock_code, MAX(report_date) AS max_date
                FROM stock_financial_data
                WHERE 1=1 {code_filter}
                GROUP BY stock_code
            ) b ON a.stock_code = b.stock_code AND a.report_date = b.max_date
            ORDER BY a.stock_code
            """

            params = tuple(params_list) if params_list else None
            results = self.db.execute_query(sql, params)

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)
            return df

        except Exception as e:
            print(f"获取财报数据失败: {e}")
            return pd.DataFrame()

    def get_multi_year_financials(
        self,
        stock_code: str,
        years: int = 3
    ) -> pd.DataFrame:
        """
        获取单只股票连续多年年报数据

        Args:
            stock_code: 股票代码
            years: 获取最近几年的数据

        Returns:
            多年财报DataFrame，按fiscal_year排序
        """
        try:
            sql = """
            SELECT *
            FROM stock_financial_data
            WHERE stock_code = %s
              AND report_type = '年报'
            ORDER BY fiscal_year DESC
            LIMIT %s
            """

            params = (stock_code, years)
            results = self.db.execute_query(sql, params)

            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)
            return df.sort_values('fiscal_year')

        except Exception as e:
            print(f"获取多年财报失败: {e}")
            return pd.DataFrame()

    def filter_by_financials(
        self,
        filters: List[Dict[str, Any]],
        stock_codes: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        根据财务指标筛选股票

        【筛选流程】
        1. 获取每只股票的最新财报
        2. 根据filters条件在pandas中过滤
        3. 返回符合条件的股票列表

        Args:
            filters: 筛选条件列表，每项包含 field/op/value
            stock_codes: 限定股票代码范围

        Returns:
            符合条件的股票DataFrame，包含所有财报字段

        【筛选条件示例】
        filters = [
            {'field': '净资产收益率ROE', 'op': '>=', 'value': 12},
            {'field': '资产负债率', 'op': '<', 'value': 60},
            {'field': '经营性现金流', 'op': '>', 'value': 0},
        ]
        """
        try:
            # 获取最新财报
            df = self.get_latest_financials(stock_codes)

            if df.empty:
                return pd.DataFrame()

            # 应用财务筛选条件
            filtered_df = self._apply_financial_filters(df, filters)

            return filtered_df

        except Exception as e:
            print(f"财务筛选失败: {e}")
            return pd.DataFrame()

    def _apply_financial_filters(
        self,
        df: pd.DataFrame,
        filters: List[Dict[str, Any]]
    ) -> pd.DataFrame:
        """
        在DataFrame上应用财务筛选条件

        Args:
            df: 财报数据DataFrame
            filters: 筛选条件列表

        Returns:
            过滤后的DataFrame
        """
        result = df.copy()

        for f in filters:
            field = f.get('field', '')
            op = f.get('op', '=')
            value = f.get('value')
            source = f.get('source', 'financial')

            # 只处理财务类字段
            if source != 'financial':
                continue

            # 映射到数据库字段
            db_field = self.FIELD_MAPPING.get(field, field)

            if db_field not in result.columns:
                print(f"[WARN] Financial field '{db_field}' not in data, available: {result.columns.tolist()}")
                continue

            # 跳过NaN值
            col = pd.to_numeric(result[db_field], errors='coerce')

            # 执行过滤
            if op in ('>', '>='):
                result = result[col >= value] if op == '>=' else result[col > value]
            elif op in ('<', '<='):
                result = result[col <= value] if op == '<=' else result[col < value]
            elif op == '=':
                result = result[col == value]
            elif op == '!=':
                result = result[col != value]
            elif op.upper() == 'LIKE':
                result = result[col.astype(str).str.contains(str(value), na=False)]

        return result

    def get_financial_summary(
        self,
        stock_codes: List[str]
    ) -> pd.DataFrame:
        """
        获取多只股票财务摘要（精简列）

        返回：stock_code, stock_name, roe, net_margin, debt_ratio,
              revenue_growth, profit_growth, operating_cash_flow

        Args:
            stock_codes: 股票代码列表

        Returns:
            财务摘要DataFrame
        """
        try:
            df = self.get_latest_financials(stock_codes)

            if df.empty:
                return pd.DataFrame()

            # 提取关键列
            summary_cols = [
                'stock_code', 'stock_name', 'report_date', 'fiscal_year',
                'roe', 'net_margin', 'gross_margin',
                'revenue_growth', 'profit_growth',
                'debt_ratio', 'current_ratio',
                'operating_cash_flow', 'net_profit',
                'basic_eps', 'revenue'
            ]

            available = [c for c in summary_cols if c in df.columns]
            return df[available].copy()

        except Exception as e:
            print(f"获取财务摘要失败: {e}")
            return pd.DataFrame()

    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            result = self.db.execute_query("SELECT COUNT(*) as cnt FROM stock_financial_data")
            count = result[0]['cnt'] if result else 0
            print(f"[OK] stock_financial_data 表共有 {count} 条记录")
            return True
        except Exception as e:
            print(f"[FAIL] 财报数据库连接失败: {e}")
            return False


# 全局实例（延迟初始化）
_financial_fetcher: Optional[FinancialDataFetcher] = None


def get_financial_fetcher() -> FinancialDataFetcher:
    """获取全局财报数据获取器实例"""
    global _financial_fetcher
    if _financial_fetcher is None:
        _financial_fetcher = FinancialDataFetcher()
    return _financial_fetcher
