"""
查询构建器模块

【模块功能】
构建复杂的SQL查询条件，采用链式调用风格，简化查询构建过程。

【主要类】
1. QueryOperator - 操作符枚举
2. QueryBuilder - 通用查询构建器
3. StockQueryBuilder - 股票专用查询构建器

【链式调用示例】
sql, params = (QueryBuilder('stock_daily_full')
    .select('代码', '名称', '涨幅%')
    .where_gte('成交额', 50000000)
    .where_like('细分行业', '%科技%')
    .order_by('涨幅%', 'DESC')
    .limit(50)
    .build())

【防注入机制】
- 使用%s占位符
- 参数通过params列表传递
- 自动处理引号转义
"""

from typing import Dict, List, Optional, Any, Tuple
from enum import Enum


class QueryOperator(str, Enum):
    """
    查询操作符枚举
    
    【支持的枚举值】
    - EQ: 等于 (=)
    - NE: 不等于 (!=)
    - GT: 大于 (>)
    - GTE: 大于等于 (>=)
    - LT: 小于 (<)
    - LTE: 小于等于 (<=)
    - LIKE: 模糊匹配 (LIKE)
    - IN: IN列表 (IN)
    - BETWEEN: 范围 (BETWEEN)
    """
    EQ = "="      # 等于
    NE = "!="     # 不等于
    GT = ">"      # 大于
    GTE = ">="    # 大于等于
    LT = "<"      # 小于
    LTE = "<="    # 小于等于
    LIKE = "LIKE" # 模糊匹配
    IN = "IN"     # IN列表
    BETWEEN = "BETWEEN"  # 范围


class QueryBuilder:
    """
    查询构建器
    
    【功能说明】
    1. 构建WHERE条件
    2. 构建ORDER BY
    3. 构建LIMIT/OFFSET
    4. 组合复杂查询
    
    【使用方式】
    builder = QueryBuilder('table_name')
    builder.select('col1', 'col2')
    builder.where_equal('col1', 'value')
    builder.order_by('col2', 'DESC')
    sql, params = builder.build()
    """
    
    def __init__(self, table_name: str):
        """
        初始化查询构建器
        
        Args:
            table_name: 表名
        """
        self.table_name = table_name
        self._columns: List[str] = []
        self._conditions: List[str] = []
        self._order_by: List[str] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._params: List[Any] = []
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """
        指定要查询的列
        
        Args:
            columns: 列名列表
        
        Returns:
            self
        """
        self._columns = list(columns)
        return self
    
    def where_equal(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field = value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} = %s")
        self._params.append(value)
        return self
    
    def where_not_equal(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field != value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} != %s")
        self._params.append(value)
        return self
    
    def where_gt(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field > value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} > %s")
        self._params.append(value)
        return self
    
    def where_gte(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field >= value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} >= %s")
        self._params.append(value)
        return self
    
    def where_lt(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field < value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} < %s")
        self._params.append(value)
        return self
    
    def where_lte(self, field: str, value: Any) -> 'QueryBuilder':
        """
        WHERE field <= value
        
        Args:
            field: 字段名
            value: 值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} <= %s")
        self._params.append(value)
        return self
    
    def where_like(self, field: str, pattern: str) -> 'QueryBuilder':
        """
        WHERE field LIKE pattern
        
        Args:
            field: 字段名
            pattern: 匹配模式
        
        Returns:
            self
        """
        self._conditions.append(f"{field} LIKE %s")
        self._params.append(pattern)
        return self
    
    def where_in(self, field: str, values: List[Any]) -> 'QueryBuilder':
        """
        WHERE field IN (values)
        
        Args:
            field: 字段名
            values: 值列表
        
        Returns:
            self
        """
        placeholders = ', '.join(['%s'] * len(values))
        self._conditions.append(f"{field} IN ({placeholders})")
        self._params.extend(values)
        return self
    
    def where_between(
        self,
        field: str,
        low: Any,
        high: Any
    ) -> 'QueryBuilder':
        """
        WHERE field BETWEEN low AND high
        
        Args:
            field: 字段名
            low: 最小值
            high: 最大值
        
        Returns:
            self
        """
        self._conditions.append(f"{field} BETWEEN %s AND %s")
        self._params.extend([low, high])
        return self
    
    def where_is_null(self, field: str) -> 'QueryBuilder':
        """
        WHERE field IS NULL
        
        Args:
            field: 字段名
        
        Returns:
            self
        """
        self._conditions.append(f"{field} IS NULL")
        return self
    
    def where_is_not_null(self, field: str) -> 'QueryBuilder':
        """
        WHERE field IS NOT NULL
        
        Args:
            field: 字段名
        
        Returns:
            self
        """
        self._conditions.append(f"{field} IS NOT NULL")
        return self
    
    def and_where(self, condition: str, *params: Any) -> 'QueryBuilder':
        """
        添加AND条件
        
        Args:
            condition: 条件表达式
            params: 参数
        
        Returns:
            self
        """
        if self._conditions:
            self._conditions.append(f"AND ({condition})")
        else:
            self._conditions.append(f"({condition})")
        self._params.extend(params)
        return self
    
    def or_where(self, condition: str, *params: Any) -> 'QueryBuilder':
        """
        添加OR条件
        
        Args:
            condition: 条件表达式
            params: 参数
        
        Returns:
            self
        """
        if self._conditions:
            self._conditions.append(f"OR ({condition})")
        else:
            self._conditions.append(f"({condition})")
        self._params.extend(params)
        return self
    
    def order_by(self, field: str, direction: str = 'ASC') -> 'QueryBuilder':
        """
        添加排序
        
        Args:
            field: 排序字段
            direction: 排序方向 (ASC/DESC)
        
        Returns:
            self
        """
        direction = direction.upper()
        if direction not in ('ASC', 'DESC'):
            direction = 'ASC'
        self._order_by.append(f"{field} {direction}")
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """
        设置LIMIT
        
        Args:
            limit: 限制条数
        
        Returns:
            self
        """
        self._limit = limit
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """
        设置OFFSET
        
        Args:
            offset: 偏移量
        
        Returns:
            self
        """
        self._offset = offset
        return self
    
    def build(self) -> Tuple[str, tuple]:
        """
        构建SQL语句和参数
        
        Returns:
            (sql, params)
        """
        # SELECT
        if self._columns:
            select_clause = f"SELECT {', '.join(self._columns)}"
        else:
            select_clause = "SELECT *"
        
        # FROM
        from_clause = f"FROM {self.table_name}"
        
        # WHERE
        if self._conditions:
            where_clause = "WHERE " + " ".join(self._conditions)
        else:
            where_clause = "WHERE 1=1"
        
        # ORDER BY
        if self._order_by:
            order_clause = "ORDER BY " + ", ".join(self._order_by)
        else:
            order_clause = ""
        
        # LIMIT
        limit_clause = ""
        if self._limit is not None:
            limit_clause = f"LIMIT {self._limit}"
            if self._offset is not None:
                limit_clause += f" OFFSET {self._offset}"
        
        # 组合SQL
        sql_parts = [select_clause, from_clause, where_clause, order_clause, limit_clause]
        sql = " ".join(part for part in sql_parts if part)
        
        return sql, tuple(self._params)
    
    def to_sql(self) -> str:
        """返回SQL语句字符串（不含参数）"""
        sql, _ = self.build()
        return sql
    
    def to_dict(self) -> Dict[str, Any]:
        """
        返回查询配置字典
        
        Returns:
            包含SQL和参数的字典
        """
        sql, params = self.build()
        return {
            'sql': sql,
            'params': params
        }


class StockQueryBuilder(QueryBuilder):
    """
    股票查询构建器
    
    专门用于股票数据的查询
    """
    
    def __init__(self):
        from config.settings import STOCK_TABLE
        super().__init__(STOCK_TABLE)
    
    def filter_by_code(self, code: str) -> 'StockQueryBuilder':
        """按代码筛选"""
        return self.where_equal('代码', code)
    
    def filter_by_name(self, name: str) -> 'StockQueryBuilder':
        """按名称模糊搜索"""
        return self.where_like('名称', f'%{name}%')
    
    def filter_by_industry(self, industry: str) -> 'StockQueryBuilder':
        """按行业筛选"""
        return self.where_like('细分行业', f'%{industry}%')
    
    def filter_by_area(self, area: str) -> 'StockQueryBuilder':
        """按地区筛选"""
        return self.where_equal('地区', area)
    
    def filter_by_change_range(
        self,
        min_change: Optional[float] = None,
        max_change: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按涨跌幅范围筛选"""
        if min_change is not None:
            self.where_gte('涨幅%', min_change)
        if max_change is not None:
            self.where_lte('涨幅%', max_change)
        return self
    
    def filter_by_price_range(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按价格范围筛选"""
        if min_price is not None:
            self.where_gte('现价', min_price)
        if max_price is not None:
            self.where_lte('现价', max_price)
        return self
    
    def filter_by_volume(
        self,
        min_volume: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按成交量筛选"""
        if min_volume is not None:
            self.where_gte('总量', min_volume)
        return self
    
    def filter_by_amount(
        self,
        min_amount: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按成交额筛选"""
        if min_amount is not None:
            self.where_gte('总金额', min_amount)
        return self
    
    def filter_by_pe(
        self,
        max_pe: Optional[float] = None,
        min_pe: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按市盈率筛选"""
        if max_pe is not None:
            self.where_lte('市盈(动)', max_pe)
        if min_pe is not None:
            self.where_gte('市盈(动)', min_pe)
        return self
    
    def filter_by_market_cap(
        self,
        min_cap: Optional[float] = None,
        max_cap: Optional[float] = None
    ) -> 'StockQueryBuilder':
        """按总市值筛选"""
        if min_cap is not None:
            self.where_gte('AB股总市值', min_cap)
        if max_cap is not None:
            self.where_lte('AB股总市值', max_cap)
        return self
    
    def filter_limit_up(self) -> 'StockQueryBuilder':
        """筛选涨停股票（约9.5%以上）"""
        return self.where_gte('涨幅%', 9.5)
    
    def filter_limit_down(self) -> 'StockQueryBuilder':
        """筛选跌停股票（约-9.5%以下）"""
        return self.where_lte('涨幅%', -9.5)
    
    def order_by_change(self, ascending: bool = False) -> 'StockQueryBuilder':
        """按涨跌幅排序"""
        direction = 'ASC' if ascending else 'DESC'
        return self.order_by('涨幅%', direction)
    
    def order_by_volume(self, ascending: bool = False) -> 'StockQueryBuilder':
        """按成交量排序"""
        direction = 'ASC' if ascending else 'DESC'
        return self.order_by('总量', direction)
    
    def order_by_amount(self, ascending: bool = False) -> 'StockQueryBuilder':
        """按成交额排序"""
        direction = 'ASC' if ascending else 'DESC'
        return self.order_by('总金额', direction)
    
    def order_by_market_cap(self, ascending: bool = False) -> 'StockQueryBuilder':
        """按总市值排序"""
        direction = 'ASC' if ascending else 'DESC'
        return self.order_by('AB股总市值', direction)
