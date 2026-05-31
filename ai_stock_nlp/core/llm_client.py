"""
LLM客户端模块 - 火山引擎ARK版

【模块功能】
提供统一的AI大模型调用接口，使用火山引擎官方SDK。

【使用方式】
from core.llm_client import get_llm_client
client = get_llm_client()
response = client.chat(model="doubao-pro-32k", messages=[...])

【安装依赖】
pip install volcengine-python-sdk[ark]
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import AI_CONFIG


class LLMClient:
    """
    大模型客户端 - 火山引擎ARK版
    
    【功能说明】
    封装火山引擎ARK API调用，提供简单的chat接口。
    
    【配置来源】
    - model: 从 config.settings.AI_CONFIG 读取
    - api_base: 从 config.settings.AI_CONFIG 读取
    - api_key: 从 config.settings.AI_CONFIG 读取
    """
    
    def __init__(self):
        """初始化LLM客户端"""
        # 优先使用环境变量，兼容运行时设置
        self.model = os.getenv('ARK_MODEL', AI_CONFIG['model'])
        self.api_base = os.getenv('ARK_API_BASE', AI_CONFIG['api_base'])
        self.api_key = os.getenv('ARK_API_KEY', AI_CONFIG.get('api_key', ''))
        self.temperature = AI_CONFIG.get('temperature', 0)
        self.timeout = AI_CONFIG.get('timeout', 60)
        self._client = None
    
    def _get_ark_client(self):
        """获取火山引擎ARK客户端实例（懒加载）"""
        if self._client is None:
            try:
                from volcenginesdkarkruntime import Ark
                self._client = Ark(
                    base_url=self.api_base,
                    api_key=self.api_key,
                )
            except ImportError:
                raise ImportError("请安装火山引擎SDK: pip install volcengine-python-sdk[ark]")
        return self._client
    
    def chat(
        self,
        model: Optional[str] = None,
        messages: List[Dict[str, str]] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        调用大模型API
        
        Args:
            model: 模型名称（默认为配置中的模型）
            messages: 消息列表，格式 [{"role": "user"/"system"/"assistant", "content": "..."}]
            temperature: 温度参数（默认为0）
            **kwargs: 其他参数
        
        Returns:
            API响应字典
        """
        if messages is None:
            raise ValueError("messages不能为空")
        
        client = self._get_ark_client()
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        
        try:
            # 使用 responses.create() 接口
            response = client.responses.create(
                model=model,
                input=messages,  # 火山引擎SDK直接使用messages作为input
                temperature=temperature,
                **kwargs
            )
            
            # 提取文本内容
            output_text = ""
            if hasattr(response, 'output') and response.output:
                for item in response.output:
                    if hasattr(item, 'type') and item.type == 'message':
                        for content in item.content:
                            if hasattr(content, 'text'):
                                output_text = content.text
                                break
                        break
            
            # 转换为兼容格式
            return {
                'choices': [
                    {
                        'message': {
                            'content': output_text
                        },
                        'finish_reason': 'stop'
                    }
                ],
                'usage': {
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                }
            }
        except Exception as e:
            raise Exception(f"LLM API调用失败: {str(e)}")


# 全局客户端实例（单例模式）
_llm_client_instance = None


def get_llm_client() -> LLMClient:
    """
    获取LLM客户端单例实例
    
    Returns:
        LLMClient实例
    """
    global _llm_client_instance
    if _llm_client_instance is None:
        _llm_client_instance = LLMClient()
    return _llm_client_instance


def is_llm_available() -> bool:
    """
    检查LLM是否可用（API Key是否配置）
    
    Returns:
        是否可用
    """
    # 优先检查环境变量（运行时设置），其次检查配置文件
    api_key = os.getenv('ARK_API_KEY', AI_CONFIG.get('api_key', '')).strip()
    return bool(api_key)
