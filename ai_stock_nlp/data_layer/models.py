"""
数据模型定义模块

【模块功能】
定义系统使用的数据结构，提供数据类的创建、转换和序列化方法。

【数据模型列表】
1. StockData - 股票基础数据
2. KLineData - K线数据
3. QueryResult - 查询结果封装
4. GridTrade - 网格交易记录
5. BacktestResult - 回测结果

【设计原则】
- 使用dataclass简化数据类定义
- 提供from_dict/from_dataframe工厂方法
- 提供to_dict/to_json序列化方法
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd


@dataclass
class StockData:
    """
    股票基础数据模型
    
    【属性说明】
    - code: 股票代码，6位数字字符串
    - name: 股票名称
    - industry: 所属行业
    - area: 地区
    - price: 最新价
    - change_pct: 涨跌幅（百分比）
    - volume: 成交量
    - amount: 成交额
    - pe: 市盈率
    - market_cap: 总市值
    - date: 数据日期
    
    【使用场景】
    - 存储单只股票的基础信息
    - 作为选股结果的基本单位
    """
    code: str
    name: str
    industry: Optional[str] = None
    area: Optional[str] = None
    price: Optional[float] = None
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    pe: Optional[float] = None
    market_cap: Optional[float] = None
    date: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StockData':
        """从字典创建实例"""
        return cls(
            code=str(data.get('代码', '')),
            name=str(data.get('名称', '')),
            industry=data.get('细分行业'),
            area=data.get('地区'),
            price=float(data['现价']) if data.get('现价') else None,
            change_pct=float(data['涨幅%']) if data.get('涨幅%') else None,
            volume=float(data['总量']) if data.get('总量') else None,
            amount=float(data['总金额']) if data.get('总金额') else None,
            pe=float(data['市盈(动)']) if data.get('市盈(动)') else None,
            market_cap=float(data.get('流通市值', 0)),
            date=str(data.get('trade_date', data.get('日期', '')))[:10] if data.get('trade_date') else data.get('日期')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'code': self.code,
            'name': self.name,
            'industry': self.industry,
            'area': self.area,
            'price': self.price,
            'change_pct': self.change_pct,
            'volume': self.volume,
            'amount': self.amount,
            'pe': self.pe,
            'market_cap': self.market_cap,
            'date': self.date
        }


@dataclass
class KLineData:
    """
    K线数据模型
    
    Attributes:
        date: 日期
        open: 开盘价
        high: 最高价
        low: 最低价
        close: 收盘价
        volume: 成交量
        amount: 成交额
        change_pct: 涨跌幅
    """
    date: str
    code: str
    name: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    change_pct: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KLineData':
        """从字典创建实例"""
        # 处理日期字段
        trade_date = data.get('trade_date')
        if trade_date:
            if isinstance(trade_date, str):
                date_str = str(trade_date)[:10]
            else:
                date_str = str(trade_date)
        else:
            date_str = str(data.get('date', data.get('日期', '')))
        
        return cls(
            date=date_str,
            code=str(data.get('代码', '')),
            name=data.get('名称'),
            open=float(data['今开']) if data.get('今开') else None,
            high=float(data['最高']) if data.get('最高') else None,
            low=float(data['最低']) if data.get('最低') else None,
            close=float(data['现价']) if data.get('现价') else None,
            volume=float(data['总量']) if data.get('总量') else None,
            amount=float(data['总金额']) if data.get('总金额') else None,
            change_pct=float(data['涨幅%']) if data.get('涨幅%') else None
        )
    
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> List['KLineData']:
        """从DataFrame创建K线数据列表"""
        return [cls.from_dict(row) for _, row in df.iterrows()]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'date': self.date,
            'code': self.code,
            'name': self.name,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'amount': self.amount,
            'change_pct': self.change_pct
        }


@dataclass
class QueryResult:
    """
    查询结果封装
    
    Attributes:
        success: 是否成功
        data: 数据
        message: 消息
        count: 返回数据的条数（截断后）
        total: 符合条件的总条数（截断前）
    """
    success: bool
    data: Any = None
    message: str = ""
    count: int = 0
    total: int = 0
    
    @classmethod
    def ok(cls, data: Any, message: str = "success", total: int = None) -> 'QueryResult':
        """创建成功结果"""
        count = len(data) if hasattr(data, '__len__') else 0
        total = total if total is not None else count
        return cls(success=True, data=data, message=message, count=count, total=total)
    
    @classmethod
    def error(cls, message: str, data: Any = None) -> 'QueryResult':
        """创建错误结果"""
        return cls(success=False, data=data, message=message, count=0, total=0)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'data': self.data,
            'message': self.message,
            'count': self.count,
            'total': self.total
        }


@dataclass
class GridTrade:
    """
    网格交易记录
    
    Attributes:
        date: 交易日期
        action: 交易动作 (buy/sell)
        price: 成交价格
        shares: 成交数量
        amount: 成交金额
        position: 持仓数量
        cash: 剩余现金
    """
    date: str
    action: str  # 'buy' or 'sell'
    price: float
    shares: int
    amount: float
    position: int = 0
    cash: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'date': self.date,
            'action': self.action,
            'price': self.price,
            'shares': self.shares,
            'amount': self.amount,
            'position': self.position,
            'cash': self.cash
        }


@dataclass
class BacktestResult:
    """
    回测结果
    
    Attributes:
        stock_code: 股票代码
        stock_name: 股票名称
        trades: 交易记录列表
        total_return: 总收益率
        win_rate: 胜率
        max_drawdown: 最大回撤
        sharpe_ratio: 夏普比率
        final_position: 最终持仓
        final_cash: 最终现金
    """
    stock_code: str
    stock_name: str
    trades: List[GridTrade] = field(default_factory=list)
    total_return: float = 0.0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    final_position: int = 0
    final_cash: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'trades': [t.to_dict() for t in self.trades],
            'total_return': self.total_return,
            'win_rate': self.win_rate,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'final_position': self.final_position,
            'final_cash': self.final_cash
        }
