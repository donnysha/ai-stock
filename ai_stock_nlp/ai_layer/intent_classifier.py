"""
意图分类器模块

【模块功能】
负责识别用户输入的意图类型，是AI层的入口模块。

【支持的三种意图类型】
1. STOCK_SELECT - 选股（当前时间）
   - 用于实际操作决策
   - 关键词：选股、筛选、找出符合条件的股票
   
2. GRID_BACKTEST - 网格交易回测
   - 固定网格交易策略回测
   - 关键词：网格交易、网格策略、设定买卖点
   
3. FLEX_BACKTEST - 灵活回测（自定义时序条件）
   - 用于策略回测和模型验证
   - 支持跨日期条件，如"连续两天涨停"
   - 关键词：连续涨停、回测、模型、策略验证

【识别策略】
1. 优先使用规则匹配（快速响应，无需API调用）
2. 若规则无法识别，使用大模型API
3. 默认返回 STOCK_SELECT

【使用场景】
用户输入"帮我找出连续两天涨停的股票" -> FLEX_BACKTEST
用户输入"成交额大于5000万的科技股" -> STOCK_SELECT
用户输入"对000001做网格回测" -> GRID_BACKTEST
"""

import json
import re
from typing import Optional
from config.settings import AI_CONFIG
from config.prompts import INTENT_CLASSIFICATION_PROMPT
from .schema import IntentType


class IntentClassifier:
    """
    意图分类器
    
    【功能说明】
    1. 接收用户自然语言输入
    2. 调用大模型API识别意图（可选）
    3. 返回标准意图类型（STOCK_SELECT/GRID_BACKTEST/FLEX_BACKTEST）
    
    【设计原则】
    - 优先使用规则匹配，确保快速响应
    - 大模型仅作为规则匹配的补充
    """
    
    def __init__(self, llm_client=None):
        """
        初始化意图分类器
        
        Args:
            llm_client: 大模型客户端实例（可选，不传则仅用规则匹配）
        """
        self.llm_client = llm_client
        self.model = AI_CONFIG['model']
        self.temperature = AI_CONFIG['temperature']
    
    def classify(self, user_input: str) -> IntentType:
        """
        识别用户输入的意图（主入口方法）
        
        Args:
            user_input: 用户的自然语言输入
        
        Returns:
            IntentType: 识别的意图类型
        
        Raises:
            ValueError: 无法识别意图时抛出
        """
        if not user_input or not user_input.strip():
            raise ValueError("用户输入不能为空")
        
        # 步骤1：优先使用规则匹配（快速响应）
        rule_intent = self._rule_based_classify(user_input)
        if rule_intent:
            return rule_intent
        
        # 步骤2：使用大模型识别（如果可用）
        if self.llm_client:
            return self._llm_classify(user_input)
        
        # 步骤3：无法识别时抛出异常
        raise ValueError(f"无法识别意图: {user_input}")
    
    def _rule_based_classify(self, user_input: str) -> Optional[IntentType]:
        """
        基于规则的快速意图识别
        
        【规则说明】
        - 灵活回测关键词优先级最高（如"连续涨停"、"模型"等）
        - 选股关键词其次（如"选股"、"筛选"等）
        - 网格关键词默认返回网格回测
        
        Args:
            user_input: 用户输入
        
        Returns:
            IntentType: 识别的意图类型，或None表示无法用规则识别
        """
        text = user_input.lower()
        
        # 灵活回测关键词 - 最高优先级
        flex_backtest_keywords = [
            '连续涨停', '连板', '连续两天', '连续三天', '连续N天',
            '模型', '策略验证', '回测模型', '历史回测',
            '第三天', '第二天', '追涨', '回调',
            '量价齐升', '放量突破', '缩量回调'
        ]
        
        # 网格交易关键词
        grid_keywords = [
            '网格', '网格交易', '买卖点', '分批买入', '分批卖出',
            '高抛低吸', '波段', '震荡', '自动交易', '网格策略',
            '下跌', '上涨', '买入', '卖出'  # 如果没有其他关键词时
        ]
        
        # 选股关键词 - 基础筛选
        select_keywords = [
            '选股', '筛选', '找出', '查找', '符合条件的股票',
            '哪些股票', '什么股票', '推荐股票', '股票池'
        ]
        
        # 简单筛选关键词 - 最低优先级
        simple_filter_keywords = [
            '成交额', '市盈率', '行业', '价格区间', '涨幅大于', '跌幅大于'
        ]
        
        # 计算分数
        flex_score = sum(1 for kw in flex_backtest_keywords if kw in text)
        grid_score = sum(1 for kw in grid_keywords if kw in text)
        select_score = sum(1 for kw in select_keywords if kw in text)
        simple_score = sum(1 for kw in simple_filter_keywords if kw in text)
        
        # 优先级判断
        # 1. 灵活回测关键词优先
        if flex_score >= 1:
            return IntentType.FLEX_BACKTEST
        
        # 2. 选股关键词
        if select_score >= 1:
            # 如果同时有网格相关词，可能是网格回测
            if grid_score >= 1:
                return IntentType.GRID_BACKTEST
            return IntentType.STOCK_SELECT
        
        # 3. 只有简单筛选词 -> 选股
        if simple_score >= 1:
            return IntentType.STOCK_SELECT
        
        # 4. 只有网格关键词 -> 网格回测
        if grid_score >= 1:
            return IntentType.GRID_BACKTEST
        
        # 默认返回选股
        return IntentType.STOCK_SELECT
    
    def _llm_classify(self, user_input: str) -> IntentType:
        """
        使用大模型进行意图识别
        
        Args:
            user_input: 用户输入
        
        Returns:
            IntentType
        """
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_input)
        
        try:
            response = self.llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的股票策略分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature
            )
            
            # 解析JSON响应
            content = response['choices'][0]['message']['content']
            # 提取JSON
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                intent_str = data.get('intent', '')
                return IntentType(intent_str)
            
        except Exception as e:
            print(f"LLM识别失败: {e}")
        
        # 失败时使用默认意图
        return IntentType.STOCK_SELECT
