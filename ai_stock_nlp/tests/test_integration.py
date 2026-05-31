"""
集成测试
测试完整的数据流
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    @classmethod
    def setUpClass(cls):
        """初始化测试环境"""
        from data_layer.akshare_data_fetcher import akshare_fetcher
        
        cls.fetcher = akshare_fetcher
    
    def test_akshare_connection(self):
        """测试 akshare 连接"""
        result = self.fetcher.test_connection()
        self.assertTrue(result)
    
    def test_get_realtime_quote(self):
        """测试获取实时行情"""
        result = self.fetcher.get_realtime_quote('000001')
        self.assertIsNotNone(result)
        self.assertIn('代码', result)
    
    def test_full_select_flow(self):
        """测试完整选股流程"""
        from core import StrategyDispatcher
        
        dispatcher = StrategyDispatcher()
        
        # 测试自然语言输入
        result = dispatcher.process("帮我找出成交额大于5000万的股票")
        
        self.assertIn('success', result)
        self.assertIn('intent', result)
        self.assertEqual(result['intent'], 'stock_select')
    
    def test_full_backtest_flow(self):
        """测试完整回测流程"""
        from core import StrategyDispatcher
        
        dispatcher = StrategyDispatcher()
        
        # 直接调用回测接口
        result = dispatcher.process_backtest(
            stock_code='000001',
            start_date='20240101',
            end_date=None,
            grid_buy_percent=-3.0,
            grid_sell_percent=5.0,
            base_price_type='open_price',
            min_volume=1000
        )
        
        self.assertIn('success', result)


if __name__ == '__main__':
    unittest.main()
