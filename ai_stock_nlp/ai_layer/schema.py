"""
输出协议定义模块

【模块功能】
定义AI层输出的标准JSON结构，是AI层与业务层之间的接口契约。

【核心数据结构】
1. IntentType - 意图类型枚举
   - STOCK_SELECT: 选股（当前时间）
   - GRID_BACKTEST: 网格交易回测
   - FLEX_BACKTEST: 灵活回测（自定义时序条件）

2. OutputStatus - 输出状态枚举
   - READY: 参数完整，可以执行
   - NEED_INPUT: 需要用户补充参数

3. FilterCondition - 筛选条件数据结构
   - 支持灵活的时间序列查询
   - days_ago: 0=今天, 1=昨天, 2=前天

4. OutputSchema - 标准输出协议
   - 统一AI层的输出格式
   - 包含意图、状态、参数、缺失字段

【使用示例】
output = OutputSchema(
    intent=IntentType.STOCK_SELECT,
    status=OutputStatus.READY,
    params={'filters': [...]},
    missing_fields=[]
)
print(output.to_json())
"""

from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
import json


class IntentType(str, Enum):
    """
    意图类型枚举
    
    【三种意图类型说明】
    - STOCK_SELECT: 选股查询，基于当前时间数据
    - GRID_BACKTEST: 网格交易策略回测
    - FLEX_BACKTEST: 灵活回测，支持自定义时序条件
    """
    STOCK_SELECT = "stock_select"  # 选股（当前时间）
    GRID_BACKTEST = "grid_backtest"  # 网格回测
    FLEX_BACKTEST = "flex_backtest"  # 灵活回测（自定义条件）


class OutputStatus(str, Enum):
    """
    输出状态枚举
    
    【状态说明】
    - READY: 所有必需参数已提供，可以执行
    - NEED_INPUT: 缺少必需参数，需要用户补充
    """
    READY = "ready"       # 参数完整，可以执行
    NEED_INPUT = "need_input"  # 需要用户补充参数


@dataclass
class FilterCondition:
    """
    筛选条件数据结构
    
    【属性说明】
    - field: 字段名，如"成交额"、"涨幅%"、"现价"、"市盈(动)"等
    - op: 操作符，支持 >, <, >=, <=, =, LIKE, !=
    - value: 比较值
    - source: 数据来源，"market"=行情数据, "financial"=财报数据（可选，默认market）
    - days_ago: 距今天数，0=今天, 1=昨天, 2=前天
    - logical_op: 与下一个条件的逻辑关系，默认AND
    
    【使用场景】
    - 选股筛选条件
    - 灵活回测条件
    - 支持跨日期的时序查询
    - 支持跨数据源的联合查询
    """
    field: str
    op: str
    value: Any
    source: str = "market"  # "market" | "financial"
    days_ago: int = 0
    logical_op: str = "AND"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "field": self.field,
            "op": self.op,
            "value": self.value,
            "source": self.source,
            "days_ago": self.days_ago,
            "logical_op": self.logical_op
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterCondition':
        """从字典创建实例"""
        return cls(
            field=data.get('field', ''),
            op=data.get('op', '='),
            value=data.get('value'),
            source=data.get('source', 'market'),
            days_ago=data.get('days_ago', 0),
            logical_op=data.get('logical_op', 'AND')
        )


@dataclass
class OutputSchema:
    """
    标准输出协议
    
    【属性说明】
    - intent: 意图类型（STOCK_SELECT/GRID_BACKTEST/FLEX_BACKTEST）
    - status: 状态（READY/NEED_INPUT）
    - params: 抽取的参数字典，核心数据
    - missing_fields: 缺失字段列表，参数不完整时填充
    
    【params典型结构】
    # 选股/灵活回测
    {
        'filters': [
            {'field': '成交额', 'op': '>=', 'value': 50000000},
            {'field': '涨幅%', 'op': '>=', 'value': 9.5, 'days_ago': 1}
        ]
    }
    
    # 网格回测
    {
        'stock_code': '000001',
        'grid_buy_percent': -3.0,
        'grid_sell_percent': 5.0,
        'start_date': '20240101'
    }
    """
    intent: IntentType
    status: OutputStatus
    params: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    
    def to_json(self) -> str:
        """转换为JSON字符串，用于网络传输或日志记录"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "intent": self.intent.value if isinstance(self.intent, IntentType) else self.intent,
            "status": self.status.value if isinstance(self.status, OutputStatus) else self.status,
            "params": self.params,
            "missing_fields": self.missing_fields
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputSchema':
        """从字典创建实例，用于解析外部输入"""
        return cls(
            intent=IntentType(data['intent']) if 'intent' in data else IntentType.STOCK_SELECT,
            status=OutputStatus(data['status']) if 'status' in data else OutputStatus.NEED_INPUT,
            params=data.get('params', {}),
            missing_fields=data.get('missing_fields', [])
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'OutputSchema':
        """从JSON字符串创建实例"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @staticmethod
    def validate(data: Dict[str, Any]) -> tuple:
        """
        验证输出格式是否符合协议规范
        
        Returns:
            (is_valid, error_message): 验证结果和错误信息
        
        【验证规则】
        1. 必须包含intent字段，且值在IntentType枚举中
        2. 必须包含status字段，且值在OutputStatus枚举中
        """
        if 'intent' not in data:
            return False, "Missing 'intent' field"
        
        if data['intent'] not in [e.value for e in IntentType]:
            return False, f"Invalid intent: {data['intent']}"
        
        if 'status' not in data:
            return False, "Missing 'status' field"
        
        if data['status'] not in [e.value for e in OutputStatus]:
            return False, f"Invalid status: {data['status']}"
        
        return True, None


# 各意图类型的必需参数字段定义
# STOCK_SELECT只需要filters数组
STOCK_SELECT_REQUIRED_FIELDS = [
    'filters',  # 筛选条件数组
]

# GRID_BACKTEST需要股票代码
GRID_BACKTEST_REQUIRED_FIELDS = [
    'stock_code',  # 股票代码
]

# FLEX_BACKTEST也需要filters数组
FLEX_BACKTEST_REQUIRED_FIELDS = [
    'filters',  # 筛选条件（至少需要一个）
]


def check_params_completeness(intent: IntentType, params: Dict[str, Any]) -> List[str]:
    """
    检查缺失的字段
    
    【检查规则】
    - STOCK_SELECT: filters数组必须存在且非空
    - GRID_BACKTEST: stock_code必须存在
    - FLEX_BACKTEST: filters数组必须存在且非空
    
    Args:
        intent: 意图类型
        params: 参数字典
    
    Returns:
        缺失字段列表，空列表表示参数完整
    """
    missing = []
    
    if intent == IntentType.STOCK_SELECT:
        filters = params.get('filters', [])
        if not filters or len(filters) == 0:
            missing.append('filters')
    
    elif intent == IntentType.GRID_BACKTEST:
        stock_code = params.get('stock_code')
        if not stock_code:
            missing.append('stock_code')
    
    elif intent == IntentType.FLEX_BACKTEST:
        filters = params.get('filters', [])
        if not filters or len(filters) == 0:
            missing.append('filters')
    
    return missing


def get_required_fields(intent: IntentType) -> List[str]:
    """
    根据意图类型获取必需的参数字段
    
    Args:
        intent: 意图类型
    
    Returns:
        必需字段列表
    """
    if intent == IntentType.STOCK_SELECT:
        return STOCK_SELECT_REQUIRED_FIELDS
    elif intent == IntentType.GRID_BACKTEST:
        return GRID_BACKTEST_REQUIRED_FIELDS
    elif intent == IntentType.FLEX_BACKTEST:
        return FLEX_BACKTEST_REQUIRED_FIELDS
    return []


def check_missing_fields(intent: IntentType, params: Dict[str, Any]) -> List[str]:
    """
    检查缺失的字段（基于必需字段列表）
    
    Args:
        intent: 意图类型
        params: 参数字典
    
    Returns:
        缺失字段列表
    """
    required = get_required_fields(intent)
    missing = []
    
    for field in required:
        value = params.get(field)
        if value is None or value == '' or value == []:
            missing.append(field)
    
    return missing


def is_params_complete(intent: IntentType, params: Dict[str, Any]) -> bool:
    """
    检查参数是否完整
    
    Args:
        intent: 意图类型
        params: 参数字典
    
    Returns:
        True表示参数完整，False表示缺失
    """
    return len(check_missing_fields(intent, params)) == 0
