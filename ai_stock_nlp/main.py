"""
AI股票自然语言策略分析系统主入口

【系统功能】
通过自然语言描述，自动识别选股意图，执行选股或回测策略。

【启动方式】
python main.py

【技术架构】
1. AI层: 意图识别、参数抽取
2. 业务层: 选股执行、网格回测
3. 数据层: AkShare数据获取
4. 展示层: Streamlit Web界面

【主要特性】
- 自然语言输入，无需学习复杂查询语法
- 支持选股、网格回测、灵活回测
- 涨跌停自动判断
- 历史K线回测
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """
    主入口函数
    
    【功能】
    启动Streamlit Web应用，监听8501端口。
    
    【参数配置】
    - 端口: 8501
    - 禁用使用统计
    - 禁用保存时自动重载
    """
    import streamlit.web.cli as stcli
    import time
    
    # 清理 Streamlit Runtime 缓存，避免 "Runtime instance already exists" 错误
    try:
        from streamlit.runtime.runtime import Runtime
        Runtime._instance = None
        Runtime._created = False
    except (ImportError, AttributeError):
        pass
    
    # 清理旧的 socket 进程
    try:
        import subprocess
        subprocess.run(
            ['cmd', '/c', 'netstat', '-ano'],
            capture_output=True, text=True
        )
    except:
        pass
    
    # 启动Streamlit应用
    sys.argv = [
        "streamlit",
        "run",
        str(Path(__file__).parent / "presentation_layer" / "app.py"),
        "--server.port=8501",
        "--browser.gatherUsageStats=false",
        "--server.runOnSave=false",
        "--global.developmentMode=false"
    ]
    
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
