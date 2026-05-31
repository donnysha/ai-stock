"""
网格交易回测引擎模块

【模块功能】
执行固化的网格交易策略，进行历史回测，生成详细的回测报告。

【网格交易策略原理】
1. 设定基准价（首日开盘价或均价）
2. 设定网格参数：
   - grid_buy_percent: 下跌X%时买入
   - grid_sell_percent: 上涨Y%时卖出
3. 模拟交易：
   - 价格下跌达到阈值时，分批买入（10%仓位）
   - 价格上涨达到阈值时，分批卖出（50%持仓）

【回测指标】
- 总收益率
- 胜率
- 最大回撤
- 夏普比率

【费用计算】
- 佣金费率：万三（0.0003）
- 印花税率：千一（0.001，卖出时）
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np
from data_layer.models import KLineData, GridTrade, BacktestResult
from config.settings import BACKTEST_CONFIG


@dataclass
class GridLevel:
    """
    网格档位数据类
    
    【属性说明】
    - level: 档位编号，0为基准价档位
    - buy_price: 该档位触发买入的价格
    - sell_price: 该档位触发卖出的价格
    - position: 当前档位的持仓数量
    """
    level: int  # 档位编号
    buy_price: float  # 买入价格
    sell_price: float  # 卖出价格
    position: int  # 持仓数量
    
    def __repr__(self):
        return f"GridLevel(level={self.level}, buy={self.buy_price:.2f}, sell={self.sell_price:.2f})"


class GridBacktester:
    """
    网格交易回测引擎 - 固化业务代码
    
    【功能说明】
    1. 获取历史K线数据
    2. 执行网格交易策略
    3. 计算交易记录
    4. 生成回测报告
    
    【使用示例】
    backtester = GridBacktester(data_fetcher)
    result = backtester.backtest(
        stock_code='000001',
        start_date='20240101',
        end_date='20240601',
        grid_buy_percent=-3.0,
        grid_sell_percent=5.0
    )
    """
    
    def __init__(self, data_fetcher=None):
        self.data_fetcher = data_fetcher
        self.config = BACKTEST_CONFIG
    
    def backtest(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        grid_buy_percent: float = -3.0,
        grid_sell_percent: float = 5.0,
        base_price_type: str = 'open_price',
        min_volume: float = 0,
        initial_capital: float = None
    ) -> BacktestResult:
        """
        执行网格回测
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            grid_buy_percent: 下跌百分之多少买入（负数）
            grid_sell_percent: 上涨百分之多少卖出（正数）
            base_price_type: 基准价类型 (open_price/avg_price)
            min_volume: 最小成交额（万）
            initial_capital: 初始资金
        
        Returns:
            BacktestResult: 回测结果
        """
        if initial_capital is None:
            initial_capital = self.config['initial_capital']
        
        # 获取历史数据
        df = self._get_kline_data(stock_code, start_date, end_date, min_volume)
        
        if df.empty:
            return BacktestResult(
                stock_code=stock_code,
                stock_name='',
                total_return=0,
                trades=[]
            )
        
        stock_name = df.iloc[0].get('名称', '') if '名称' in df.columns else ''
        
        # 设置基准价
        base_price = self._get_base_price(df, base_price_type)
        
        # 计算网格价格
        grid_levels = self._calculate_grid_levels(base_price, grid_buy_percent, grid_sell_percent)
        
        # 模拟交易
        trades, position, cash = self._simulate_trades(
            df, grid_levels, base_price, 
            grid_buy_percent, grid_sell_percent,
            initial_capital
        )
        
        # 计算收益率
        total_return = self._calculate_return(trades, initial_capital, position, cash, df)
        
        # 计算其他指标
        win_rate = self._calculate_win_rate(trades)
        max_drawdown = self._calculate_max_drawdown(trades, initial_capital)
        sharpe_ratio = self._calculate_sharpe_ratio(trades)
        
        return BacktestResult(
            stock_code=stock_code,
            stock_name=stock_name,
            trades=trades,
            total_return=total_return,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            final_position=position,
            final_cash=cash
        )
    
    def _get_kline_data(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        min_volume: float = 0
    ) -> pd.DataFrame:
        """
        获取K线数据
        
        Args:
            stock_code: 股票代码
            start_date: 起始日期
            end_date: 结束日期
            min_volume: 最小成交额
        
        Returns:
            K线数据DataFrame
        """
        if self.data_fetcher is None:
            return pd.DataFrame()
        
        # 使用 akshare 获取K线数据
        df = self.data_fetcher.get_kline_dataframe(stock_code, start_date, end_date)
        
        if df.empty:
            return df
        
        # 过滤成交额过小的数据
        if min_volume > 0 and '总金额' in df.columns:
            df = df[df['总金额'] >= min_volume * 10000]
        
        return df
    
    def _get_base_price(self, df: pd.DataFrame, price_type: str) -> float:
        """
        获取基准价格
        
        Args:
            df: K线数据
            price_type: 价格类型
        
        Returns:
            基准价格
        """
        if price_type == 'open_price':
            # akshare 返回的列名是 '今开'
            if '今开' in df.columns:
                return float(df.iloc[0]['今开'])
            elif '开盘' in df.columns:
                return float(df.iloc[0]['开盘'])
            else:
                return float(df.iloc[0]['现价'])
        elif price_type == 'avg_price':
            # 均价 = 总金额 / 总成交量
            if '总金额' in df.columns and '总量' in df.columns:
                return float(df.iloc[0]['总金额']) / float(df.iloc[0]['总量'])
        return float(df.iloc[0]['现价'])
    
    def _calculate_grid_levels(
        self,
        base_price: float,
        grid_buy_percent: float,
        grid_sell_percent: float
    ) -> List[GridLevel]:
        """
        计算网格档位
        
        Args:
            base_price: 基准价格
            grid_buy_percent: 买入下跌幅度（负数）
            grid_sell_percent: 卖出上涨幅度（正数）
        
        Returns:
            网格档位列表
        """
        levels = []
        
        # 向下计算买入档位（负数）
        level = 1
        current_price = base_price * (1 + grid_buy_percent / 100)
        while current_price > base_price * 0.5:  # 最多跌50%
            levels.append(GridLevel(
                level=level,
                buy_price=current_price,
                sell_price=current_price * (1 + abs(grid_buy_percent) / 100),
                position=0
            ))
            level += 1
            current_price = current_price * (1 + grid_buy_percent / 100)
        
        # 向上计算卖出档位（正数）
        level = 0
        current_price = base_price
        while current_price < base_price * 1.5:  # 最多涨50%
            if level > 0:  # 基准价不在网格内
                levels.append(GridLevel(
                    level=level,
                    buy_price=current_price * (1 + grid_buy_percent / 100),
                    sell_price=current_price,
                    position=0
                ))
            level += 1
            current_price = current_price * (1 + grid_sell_percent / 100)
        
        return sorted(levels, key=lambda x: x.buy_price, reverse=True)
    
    def _simulate_trades(
        self,
        df: pd.DataFrame,
        grid_levels: List[GridLevel],
        base_price: float,
        grid_buy_percent: float,
        grid_sell_percent: float,
        initial_capital: float
    ) -> Tuple[List[GridTrade], int, float]:
        """
        模拟交易过程
        
        Args:
            df: K线数据
            grid_levels: 网格档位
            base_price: 基准价
            grid_buy_percent: 买入幅度
            grid_sell_percent: 卖出幅度
            initial_capital: 初始资金
        
        Returns:
            (交易记录, 最终持仓, 最终现金)
        """
        trades = []
        position = 0  # 持仓数量
        cash = initial_capital  # 现金
        current_price = base_price
        last_trade_price = base_price
        
        # 初始化网格状态
        for level in grid_levels:
            level.position = 0
        
        for idx, row in df.iterrows():
            # 获取日期
            date = str(row.get('trade_date', row.get('日期', '')))[:10]
            
            # 使用当日收盘价作为交易价格（akshare 返回 '收盘' 或 '现价'）
            close_price = float(row.get('收盘', row.get('现价', 0)))
            
            if close_price == 0:
                continue
            
            # 计算价格变化
            if last_trade_price == 0:
                pct_change = 0
            else:
                pct_change = (close_price - last_trade_price) / last_trade_price * 100
            
            # 检查是否触发买入条件
            if pct_change <= grid_buy_percent and cash > 0:
                # 计算买入数量（按100股整数倍）
                buy_amount = cash * 0.1  # 每次买入10%仓位
                shares = int(buy_amount / close_price / 100) * 100
                
                if shares > 0:
                    amount = shares * close_price
                    commission = amount * self.config['commission_rate']
                    total_cost = amount + commission
                    
                    if total_cost <= cash:
                        cash -= total_cost
                        position += shares
                        
                        trades.append(GridTrade(
                            date=date,
                            action='buy',
                            price=close_price,
                            shares=shares,
                            amount=amount,
                            position=position,
                            cash=cash
                        ))
                        last_trade_price = close_price
            
            # 检查是否触发卖出条件
            elif pct_change >= grid_sell_percent and position > 0:
                # 卖出50%持仓
                sell_shares = int(position * 0.5 / 100) * 100
                
                if sell_shares > 0:
                    sell_amount = sell_shares * close_price
                    commission = sell_amount * self.config['commission_rate']
                    stamp_tax = sell_amount * self.config['stamp_tax']
                    total_receive = sell_amount - commission - stamp_tax
                    
                    cash += total_receive
                    position -= sell_shares
                    
                    trades.append(GridTrade(
                        date=date,
                        action='sell',
                        price=close_price,
                        shares=sell_shares,
                        amount=sell_amount,
                        position=position,
                        cash=cash
                    ))
                    last_trade_price = close_price
        
        return trades, position, cash
    
    def _calculate_return(
        self,
        trades: List[GridTrade],
        initial_capital: float,
        final_position: int,
        final_cash: float,
        df: pd.DataFrame
    ) -> float:
        """计算总收益率"""
        if df.empty:
            return 0.0
        
        # 计算持仓市值（akshare 返回 '收盘' 或 '现价'）
        last_close = float(df.iloc[-1].get('收盘', df.iloc[-1].get('现价', 0)))
        position_value = final_position * last_close
        
        # 计算总资产
        total_assets = final_cash + position_value
        
        # 计算收益率
        total_return = (total_assets - initial_capital) / initial_capital * 100
        
        return round(total_return, 2)
    
    def _calculate_win_rate(self, trades: List[GridTrade]) -> float:
        """计算胜率"""
        sell_trades = [t for t in trades if t.action == 'sell']
        
        if len(sell_trades) < 2:
            return 0.0
        
        wins = 0
        for i in range(1, len(sell_trades)):
            # 获取上一次卖出价格
            prev_sell_price = sell_trades[i-1].price
            curr_sell_price = sell_trades[i].price
            
            if curr_sell_price > prev_sell_price:
                wins += 1
        
        return round(wins / (len(sell_trades) - 1) * 100, 2) if len(sell_trades) > 1 else 0.0
    
    def _calculate_max_drawdown(self, trades: List[GridTrade], initial_capital: float) -> float:
        """计算最大回撤"""
        if not trades:
            return 0.0
        
        peak = initial_capital
        max_drawdown = 0.0
        
        for trade in trades:
            # 计算当时的总资产
            total_assets = trade.cash + trade.position * trade.price
            
            if total_assets > peak:
                peak = total_assets
            
            drawdown = (peak - total_assets) / peak * 100
            
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return round(max_drawdown, 2)
    
    def _calculate_sharpe_ratio(self, trades: List[GridTrade]) -> float:
        """计算夏普比率（简化版）"""
        if len(trades) < 2:
            return 0.0
        
        # 提取每日收益率
        returns = []
        for i in range(1, len(trades)):
            prev_total = trades[i-1].cash + trades[i-1].position * trades[i-1].price
            curr_total = trades[i].cash + trades[i].position * trades[i].price
            
            if prev_total > 0:
                daily_return = (curr_total - prev_total) / prev_total
                returns.append(daily_return)
        
        if not returns:
            return 0.0
        
        # 计算年化夏普比率（假设250个交易日）
        avg_return = np.mean(returns) * 250
        std_return = np.std(returns) * np.sqrt(250)
        
        if std_return == 0:
            return 0.0
        
        sharpe = avg_return / std_return
        return round(sharpe, 2)
