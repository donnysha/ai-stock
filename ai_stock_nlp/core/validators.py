"""
参数验证器模块

【模块功能】
验证用户输入的参数是否符合要求，确保数据质量和系统稳定性。

【验证内容】
1. 选股参数验证
   - 成交量条件格式
   - 价格条件格式
   - 涨跌幅条件格式

2. 回测参数验证
   - 股票代码格式（6位数字）
   - 日期格式（YYYYMMDD）
   - 网格买卖点参数
   - 基准价类型

【验证规则】
- 股票代码：必须是6位数字
- 日期：必须是8位数字，且在合理范围内
- 网格买点：必须是负数（表示下跌）
- 网格卖点：必须是正数（表示上涨）
"""

import re
from typing import Dict, List, Tuple, Optional
from ai_layer.schema import IntentType


class ParamValidator:
    """
    参数验证器
    
    【功能说明】
    1. 验证选股参数
    2. 验证回测参数
    3. 提供验证错误信息
    
    【使用方式】
    is_valid, errors = ParamValidator.validate_grid_backtest_params(params)
    if not is_valid:
        print(errors)
    """
    
    # 股票代码正则：必须是6位数字
    STOCK_CODE_PATTERN = r'^\d{6}$'
    
    # 日期正则：必须是8位数字
    DATE_PATTERN = r'^\d{8}$'
    
    @classmethod
    def validate_stock_select_params(cls, params: Dict) -> Tuple[bool, List[str]]:
        """
        验证选股参数
        
        Args:
            params: 参数字典
        
        Returns:
            (is_valid, error_messages): 验证结果和错误列表
        """
        errors = []
        
        # 成交量条件验证
        volume = params.get('volume_condition')
        if volume:
            if not cls._validate_volume_condition(volume):
                errors.append(f"成交量条件格式不正确: {volume}")
        
        # 价格条件验证
        price = params.get('price_condition')
        if price:
            if not cls._validate_price_condition(price):
                errors.append(f"价格条件格式不正确: {price}")
        
        # 涨跌幅条件验证
        change = params.get('change_condition')
        if change:
            if not cls._validate_change_condition(change):
                errors.append(f"涨跌幅条件格式不正确: {change}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_grid_backtest_params(cls, params: Dict) -> Tuple[bool, List[str]]:
        """
        验证网格回测参数
        
        Args:
            params: 参数字典
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # 股票代码验证
        stock_code = params.get('stock_code')
        if stock_code and not re.match(cls.STOCK_CODE_PATTERN, str(stock_code)):
            errors.append(f"股票代码格式不正确，应为6位数字: {stock_code}")
        
        # 日期验证
        start_date = params.get('start_date')
        if start_date and not cls._validate_date(start_date):
            errors.append(f"起始日期格式不正确，应为YYYYMMDD: {start_date}")
        
        # 网格买卖点验证
        grid_buy = params.get('grid_buy_percent')
        if grid_buy is not None:
            if not isinstance(grid_buy, (int, float)):
                errors.append("grid_buy_percent必须是数字")
            elif grid_buy >= 0:
                errors.append("grid_buy_percent必须是负数（表示下跌）")
        
        grid_sell = params.get('grid_sell_percent')
        if grid_sell is not None:
            if not isinstance(grid_sell, (int, float)):
                errors.append("grid_sell_percent必须是数字")
            elif grid_sell <= 0:
                errors.append("grid_sell_percent必须是正数（表示上涨）")
        
        # 基准价类型验证
        base_price_type = params.get('base_price_type')
        if base_price_type and base_price_type not in ['open_price', 'avg_price']:
            errors.append(f"基准价类型不正确，应为 open_price 或 avg_price: {base_price_type}")
        
        return len(errors) == 0, errors
    
    @classmethod
    def _validate_volume_condition(cls, volume: str) -> bool:
        """验证成交量条件"""
        pattern = r'^>?\s*\d+(\.\d+)?\s*(万|亿)?$'
        return bool(re.match(pattern, str(volume).replace('大于', '').replace('小于', '')))
    
    @classmethod
    def _validate_price_condition(cls, price: str) -> bool:
        """验证价格条件"""
        # 区间格式: 10-20 或 10~20
        range_pattern = r'^\d+(\.\d+)?\s*[-~至]\s*\d+(\.\d+)?$'
        # 单值格式: <20 或 >10
        single_pattern = r'^<?\s*\d+(\.\d+)?$'
        return bool(re.match(range_pattern, str(price)) or re.match(single_pattern, str(price)))
    
    @classmethod
    def _validate_change_condition(cls, change: str) -> bool:
        """验证涨跌幅条件"""
        # 格式: 涨5% 或 涨幅大于3%
        pattern = r'^(涨|跌|涨幅|跌幅)[于]?\s*(?:大于|小于)?\s*\d+(\.\d+)?%?$'
        return bool(re.match(pattern, str(change)))
    
    @classmethod
    def _validate_date(cls, date_str: str) -> bool:
        """验证日期格式"""
        if not re.match(cls.DATE_PATTERN, str(date_str)):
            return False
        
        try:
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            
            # 基本范围检查
            if year < 2000 or year > 2100:
                return False
            if month < 1 or month > 12:
                return False
            if day < 1 or day > 31:
                return False
            
            return True
        except:
            return False
    
    @classmethod
    def validate_stock_code(cls, code: str) -> Tuple[bool, Optional[str]]:
        """验证股票代码"""
        if not code:
            return False, "股票代码不能为空"
        
        if not re.match(cls.STOCK_CODE_PATTERN, str(code)):
            return False, f"股票代码格式不正确，应为6位数字: {code}"
        
        return True, None
    
    @classmethod
    def validate_date_range(
        cls,
        start_date: str,
        end_date: str
    ) -> Tuple[bool, Optional[str]]:
        """验证日期范围"""
        if not cls._validate_date(start_date):
            return False, f"起始日期格式不正确: {start_date}"
        
        if not cls._validate_date(end_date):
            return False, f"结束日期格式不正确: {end_date}"
        
        if start_date > end_date:
            return False, "起始日期不能晚于结束日期"
        
        return True, None
