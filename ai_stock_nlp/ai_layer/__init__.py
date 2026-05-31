# =============================================================================
# AI层模块 - 自然语言处理核心
# =============================================================================
# 功能：接收用户自然语言输入，识别意图，抽取结构化参数
# 子模块：
#   - schema.py: 定义输出协议和数据结构
#   - intent_classifier.py: 意图分类器，识别用户意图
#   - param_extractor.py: 参数抽取器，从输入中提取参数
# =============================================================================

from .schema import OutputSchema, IntentType, OutputStatus
from .intent_classifier import IntentClassifier
from .param_extractor import ParamExtractor

__all__ = [
    'OutputSchema',      # 标准输出协议
    'IntentType',        # 意图类型枚举
    'OutputStatus',      # 输出状态枚举
    'IntentClassifier',   # 意图分类器
    'ParamExtractor'      # 参数抽取器
]
