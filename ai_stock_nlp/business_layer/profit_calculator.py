"""
收益计算器模块

【模块功能】
计算交易收益和资金曲线，生成各类收益率指标。

【主要功能】
1. 计算单笔交易收益（calculate_trade_profit）
   - 买入成本（含佣金）
   - 卖出收入（含佣金和印花税）
   - 净收益和收益率

2. 计算累计收益（calculate_cumulative_profit）
   - 累计买入/卖出金额
   - 累计盈亏

3. 生成资金曲线（generate_capital_curve）
   - 每日总资产变化
   - 持仓和现金变化
   - 收益率曲线

4. 计算综合指标（calculate_metrics）
   - 总收益率
   - 胜率
   - 盈亏比
   - 平均盈利/亏损

5. 计算回撤指标（calculate_drawdown）
   - 最大回撤金额
   - 最大回撤比例
"""

from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from data_layer.models import GridTrade


class ProfitCalculator:
    """
    收益计算器 - 固化业务代码
    
    【功能说明】
    1. 计算单笔交易收益
    2. 计算累计收益
    3. 生成资金曲线
    4. 计算收益率指标
    
    【费用标准】
    - 佣金费率：万三（0.0003）
    - 印花税率：千一（0.001，卖出时收取）
    """
    
    def __init__(self):
        """初始化收益计算器，设置费率参数"""
        self.commission_rate = 0.0003  # 佣金费率
        self.stamp_tax = 0.001  # 印花税（仅卖出时）
    
    def calculate_trade_profit(
        self,
        buy_trade: GridTrade,
        sell_trade: GridTrade
    ) -> Dict:
        """
        计算单笔交易收益
        
        Args:
            buy_trade: 买入交易
            sell_trade: 卖出交易
        
        Returns:
            收益详情字典
        """
        buy_cost = buy_trade.amount + buy_trade.amount * self.commission_rate
        sell_income = sell_trade.amount - sell_trade.amount * (self.commission_rate + self.stamp_tax)
        
        profit = sell_income - buy_cost
        profit_rate = profit / buy_cost * 100 if buy_cost > 0 else 0
        
        return {
            'buy_date': buy_trade.date,
            'buy_price': buy_trade.price,
            'buy_shares': buy_trade.shares,
            'buy_cost': round(buy_cost, 2),
            'sell_date': sell_trade.date,
            'sell_price': sell_trade.price,
            'sell_shares': sell_trade.shares,
            'sell_income': round(sell_income, 2),
            'profit': round(profit, 2),
            'profit_rate': round(profit_rate, 2),
            'holding_days': self._calc_holding_days(buy_trade.date, sell_trade.date)
        }
    
    def _calc_holding_days(self, start_date: str, end_date: str) -> int:
        """计算持有天数"""
        from datetime import datetime
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        return (end - start).days
    
    def calculate_cumulative_profit(
        self,
        trades: List[GridTrade],
        initial_capital: float
    ) -> pd.DataFrame:
        """
        计算累计收益
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
        
        Returns:
            累计收益DataFrame
        """
        if not trades:
            return pd.DataFrame()
        
        # 构建交易DataFrame
        df = pd.DataFrame([t.to_dict() for t in trades])
        
        # 计算累计买入和卖出
        df['cumulative_buy'] = df[df['action'] == 'buy']['amount'].cumsum()
        df['cumulative_sell'] = df[df['action'] == 'sell']['amount'].cumsum()
        
        # 计算累计盈亏（简化版）
        df['cumulative_profit'] = df['cumulative_sell'].fillna(0) - df['cumulative_buy'].fillna(0)
        
        # 计算收益率
        df['profit_rate'] = df['cumulative_profit'] / initial_capital * 100
        
        return df
    
    def generate_capital_curve(
        self,
        trades: List[GridTrade],
        initial_capital: float,
        kline_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        生成资金曲线
        
        Args:
            trades: 交易记录列表
            initial_capital: 初始资金
            kline_data: K线数据
        
        Returns:
            资金曲线DataFrame
        """
        if kline_data.empty:
            return pd.DataFrame()
        
        # 初始化
        result = kline_data[['date']].copy()
        result.columns = ['date']
        result['capital'] = initial_capital
        result['position'] = 0
        result['cash'] = initial_capital
        
        if not trades:
            return result
        
        # 模拟每日资金变化
        current_cash = initial_capital
        current_position = 0
        last_trade_idx = 0
        
        for idx, row in result.iterrows():
            date = row['date']
            
            # 检查是否有新的交易
            while last_trade_idx < len(trades) and trades[last_trade_idx].date <= date:
                trade = trades[last_trade_idx]
                
                if trade.action == 'buy':
                    current_cash = trade.cash
                    current_position = trade.position
                else:
                    current_cash = trade.cash
                    current_position = trade.position
                
                last_trade_idx += 1
            
            # 获取当日收盘价
            kline_row = kline_data[kline_data['date'] == date]
            if not kline_row.empty:
                close_price = float(kline_row.iloc[0].get('现价', 0))
                position_value = current_position * close_price
                total_capital = current_cash + position_value
            else:
                total_capital = current_cash
            
            result.at[idx, 'cash'] = current_cash
            result.at[idx, 'position'] = current_position
            result.at[idx, 'capital'] = total_capital
        
        # 计算收益率
        result['return_pct'] = (result['capital'] - initial_capital) / initial_capital * 100
        
        return result
    
    def calculate_metrics(
        self,
        trades: List[GridTrade],
        initial_capital: float,
        final_capital: float
    ) -> Dict:
        """
        计算综合指标
        
        Args:
            trades: 交易记录
            initial_capital: 初始资金
            final_capital: 最终资金
        
        Returns:
            指标字典
        """
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        # 计算交易统计
        buy_trades = [t for t in trades if t.action == 'buy']
        sell_trades = [t for t in trades if t.action == 'sell']
        
        # 计算盈利和亏损交易
        profits = []
        for i in range(1, len(sell_trades)):
            buy_cost = buy_trades[min(i, len(buy_trades)-1)].amount * (1 + self.commission_rate)
            sell_income = sell_trades[i].amount * (1 - self.commission_rate - self.stamp_tax)
            profit = sell_income - buy_cost
            profits.append(profit)
        
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p <= 0]
        
        metrics = {
            'total_return': round(total_return, 2),
            'total_trades': len(sell_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': round(len(winning_trades) / len(sell_trades) * 100, 2) if sell_trades else 0,
            'avg_profit': round(np.mean(winning_trades), 2) if winning_trades else 0,
            'avg_loss': round(np.mean(losing_trades), 2) if losing_trades else 0,
            'profit_factor': round(abs(sum(winning_trades) / sum(losing_trades)), 2) if losing_trades and sum(losing_trades) != 0 else 0,
        }
        
        return metrics
    
    def calculate_drawdown(self, capital_curve: pd.DataFrame) -> Dict:
        """
        计算回撤指标
        
        Args:
            capital_curve: 资金曲线
        
        Returns:
            回撤指标
        """
        if capital_curve.empty:
            return {'max_drawdown': 0, 'max_drawdown_pct': 0}
        
        capital = capital_curve['capital'].values
        peak = np.maximum.accumulate(capital)
        drawdown = capital - peak
        drawdown_pct = drawdown / peak * 100
        
        max_dd_idx = np.argmin(drawdown)
        
        return {
            'max_drawdown': round(abs(drawdown[max_dd_idx]), 2),
            'max_drawdown_pct': round(abs(drawdown_pct[max_dd_idx]), 2),
            'drawdown_start': capital_curve.iloc[0]['date'] if len(capital_curve) > 0 else '',
            'drawdown_end': capital_curve.iloc[max_dd_idx]['date'] if len(capital_curve) > max_dd_idx else ''
        }
