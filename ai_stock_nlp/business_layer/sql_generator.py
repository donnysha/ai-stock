"""
SQL生成器模块

【模块功能】
根据结构化参数生成SQL查询语句，采用固化代码方式，不允许AI动态生成SQL。

【安全约束】
1. 只允许预定义的字段和操作符
2. 禁止危险关键字（DROP、DELETE、UPDATE等）
3. 只允许SELECT语句
4. SQL注入防护

【允许的字段】
- 代码、名称、涨幅%、现价、涨跌额
- 成交量、成交额
- 市盈率、市净率、换手率
- 流通市值、总市值
- 细分行业、地区
- 历史涨幅字段（3日、5日、10日、20日、60日）

【允许的操作符】
=, >, <, >=, <=, !=, LIKE, IN
"""

from typing import Dict, List, Optional, Any
from config.settings import DB_CONFIG, STOCK_TABLE


class SQLGenerator:
    """
    SQL生成器 - 固化业务代码
    
    【功能说明】
    1. 根据选股参数生成SQL
    2. 验证SQL安全性
    3. 防止SQL注入
    
    【设计原则】
    - 所有字段和操作符都是预定义的
    - 不允许AI动态生成SQL
    - 只允许SELECT查询
    
    【字段映射】
    将中文字段名映射到数据库字段名
    """
    
    # 允许的字段映射（中文 -> 数据库字段）
    FIELD_MAPPING = {
        '代码': '代码',
        '名称': '名称',
        '涨幅%': '涨幅%',
        '现价': '现价',
        '涨跌额': '涨跌额',
        '成交量': '总量',
        '成交额': '总金额',
        '市盈率': '市盈(动)',
        '市净率': '市净率',
        '换手率': '换手%',
        '流通市值': '流通市值',
        '总市值': 'AB股总市值',
        '细分行业': '细分行业',
        '地区': '地区',
        '今开': '今开',
        '最高': '最高',
        '最低': '最低',
        '昨收': '昨收',
        '3日涨幅%': '3日涨幅%',
        '5日涨幅%': 'col_5日涨幅%',
        '10日涨幅%': 'col_10日涨幅%',
        '20日涨幅%': '20日涨幅%',
        '60日涨幅%': '60日涨幅%',
    }
    
    # 允许的操作符
    ALLOWED_OPS = ['=', '>', '<', '>=', '<=', '!=', 'LIKE', 'IN']
    
    def __init__(self):
        self.table_name = STOCK_TABLE
        self.field_mapping = self.FIELD_MAPPING
        self.allowed_ops = self.ALLOWED_OPS
    
    def generate_select_sql(
        self,
        filters: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """
        生成SELECT SQL语句
        
        Args:
            filters: 筛选条件列表
            columns: 返回的列（默认全部）
            order_by: 排序字段
            limit: 返回条数限制
        
        Returns:
            SQL语句字符串
        """
        # 构建列名
        if columns is None:
            select_cols = '*'
        else:
            select_cols = ', '.join(columns)
        
        # 构建WHERE子句
        where_clause = self._build_where_clause(filters)
        
        # 构建ORDER BY
        if order_by:
            order_clause = f"ORDER BY {order_by} DESC"
        else:
            order_clause = ""
        
        # 组合SQL
        sql = f"""
        SELECT {select_cols}
        FROM {self.table_name}
        WHERE {where_clause}
        {order_clause}
        LIMIT {limit}
        """.strip()
        
        return sql
    
    def generate_kline_sql(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        columns: Optional[List[str]] = None
    ) -> str:
        """
        生成K线数据查询SQL
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            columns: 返回的列
        
        Returns:
            SQL语句字符串
        """
        if columns is None:
            select_cols = '*'
        else:
            select_cols = ', '.join(columns)
        
        sql = f"""
        SELECT {select_cols}
        FROM {self.table_name}
        WHERE 代码 = '{stock_code}'
          AND trade_date >= '{start_date}'
          AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """.strip()
        
        return sql
    
    def _build_where_clause(self, filters: List[Dict[str, Any]]) -> str:
        """
        构建WHERE子句
        
        Args:
            filters: 筛选条件列表
        
        Returns:
            WHERE子句字符串
        """
        conditions = []
        
        for i, f in enumerate(filters):
            field = f.get('field', '')
            op = f.get('op', '=')
            value = f.get('value')
            days_ago = f.get('days_ago', 0)
            
            # 验证字段
            if field not in self.field_mapping:
                continue
            
            # 验证操作符
            if op.upper() not in self.allowed_ops:
                continue
            
            # 映射字段名
            db_field = self.field_mapping[field]
            
            # 构建条件
            if op.upper() == 'LIKE':
                condition = f"{db_field} LIKE '{value}'"
            elif op.upper() == 'IN':
                if isinstance(value, (list, tuple)):
                    values_str = ', '.join([f"'{v}'" for v in value])
                    condition = f"{db_field} IN ({values_str})"
                else:
                    condition = f"{db_field} IN ('{value}')"
            else:
                if isinstance(value, str):
                    condition = f"{db_field} {op} '{value}'"
                else:
                    condition = f"{db_field} {op} {value}"
            
            conditions.append(condition)
        
        if not conditions:
            return "1=1"  # 无条件
        
        return ' AND '.join(conditions)
    
    def validate_sql(self, sql: str) -> tuple:
        """
        验证SQL安全性
        
        Args:
            sql: SQL语句
        
        Returns:
            (is_valid, error_message)
        """
        # 检查危险关键字
        dangerous_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER',
            'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE',
            ';', '--', '/*', '*/'
        ]
        
        sql_upper = sql.upper()
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                return False, f"SQL包含危险关键字: {keyword}"
        
        # 检查是否以SELECT开头
        if not sql_upper.strip().startswith('SELECT'):
            return False, "只允许SELECT语句"
        
        return True, None


# 全局实例
sql_generator = SQLGenerator()
