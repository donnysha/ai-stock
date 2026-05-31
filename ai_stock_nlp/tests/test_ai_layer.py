"""
测试模块
测试AI层、核心调度器等组件
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
from ai_layer import IntentClassifier, ParamExtractor, IntentType, OutputSchema, check_missing_fields
from core import StrategyDispatcher, ParamValidator


class TestIntentClassifier(unittest.TestCase):
    """测试意图分类器"""
    
    def setUp(self):
        self.classifier = IntentClassifier()
    
    def test_select_intent(self):
        """测试选股意图识别"""
        test_cases = [
            "帮我找出成交额大于5000万的股票",
            "筛选今日涨幅超过5%的股票",
            "找一些医药行业的股票"
        ]
        
        for text in test_cases:
            intent = self.classifier.classify(text)
            self.assertEqual(intent, IntentType.STOCK_SELECT)
    
    def test_backtest_intent(self):
        """测试回测意图识别"""
        test_cases = [
            "对000001进行网格回测",
            "回测这只股票的网格交易策略",
            "模拟网格交易，下跌3%买入"
        ]
        
        for text in test_cases:
            intent = self.classifier.classify(text)
            self.assertEqual(intent, IntentType.GRID_BACKTEST)
    
    def test_empty_input(self):
        """测试空输入"""
        with self.assertRaises(ValueError):
            self.classifier.classify("")


class TestParamExtractor(unittest.TestCase):
    """测试参数抽取器"""
    
    def setUp(self):
        self.extractor = ParamExtractor()
    
    def test_stock_select_extraction(self):
        """测试选股参数抽取"""
        text = "找出成交额大于5000万的科技行业股票"
        schema = self.extractor.extract(text, IntentType.STOCK_SELECT)
        
        self.assertEqual(schema.intent, IntentType.STOCK_SELECT)
        self.assertIsNotNone(schema.params.get('volume_condition'))
        self.assertIsNotNone(schema.params.get('industry'))
    
    def test_grid_backtest_extraction(self):
        """测试回测参数抽取"""
        text = "对000001进行回测，下跌3%买入，上涨5%卖出"
        schema = self.extractor.extract(text, IntentType.GRID_BACKTEST)
        
        self.assertEqual(schema.intent, IntentType.GRID_BACKTEST)
        self.assertIsNotNone(schema.params.get('stock_code'))
    
    def test_missing_fields(self):
        """测试缺失字段检测"""
        params = {'volume_condition': None, 'industry': '科技'}
        missing = check_missing_fields(IntentType.STOCK_SELECT, params)
        
        self.assertIn('volume_condition', missing)


class TestOutputSchema(unittest.TestCase):
    """测试输出协议"""
    
    def test_to_json(self):
        """测试JSON序列化"""
        schema = OutputSchema(
            intent=IntentType.STOCK_SELECT,
            status=OutputSchema.status,
            params={'volume_condition': '>5000万'},
            missing_fields=['industry']
        )
        
        json_str = schema.to_json()
        self.assertIn('stock_select', json_str)
        self.assertIn('params', json_str)
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            'intent': 'stock_select',
            'status': 'ready',
            'params': {'volume_condition': '>5000万'},
            'missing_fields': []
        }
        
        schema = OutputSchema.from_dict(data)
        self.assertEqual(schema.intent, IntentType.STOCK_SELECT)
        self.assertEqual(schema.status.value, 'ready')


class TestParamValidator(unittest.TestCase):
    """测试参数验证器"""
    
    def test_stock_code_validation(self):
        """测试股票代码验证"""
        valid, msg = ParamValidator.validate_stock_code('000001')
        self.assertTrue(valid)
        
        valid, msg = ParamValidator.validate_stock_code('00001')  # 5位
        self.assertFalse(valid)
        
        valid, msg = ParamValidator.validate_stock_code('abcdef')  # 非数字
        self.assertFalse(valid)
    
    def test_date_validation(self):
        """测试日期验证"""
        valid, msg = ParamValidator.validate_date('20240101')
        self.assertTrue(valid)
        
        valid, msg = ParamValidator.validate_date('20241301')  # 无效月份
        self.assertFalse(valid)
    
    def test_date_range_validation(self):
        """测试日期范围验证"""
        valid, msg = ParamValidator.validate_date_range('20240101', '20241231')
        self.assertTrue(valid)
        
        valid, msg = ParamValidator.validate_date_range('20241231', '20240101')  # 倒序
        self.assertFalse(valid)


class TestDispatcher(unittest.TestCase):
    """测试核心调度器"""
    
    def setUp(self):
        self.dispatcher = StrategyDispatcher()
    
    def test_stock_select_process(self):
        """测试选股流程"""
        # 注意：需要数据库连接才能完整测试
        result = self.dispatcher.process("帮我找出成交额大于5000万的股票")
        
        self.assertIn('success', result)
        self.assertIn('intent', result)


if __name__ == '__main__':
    unittest.main()
