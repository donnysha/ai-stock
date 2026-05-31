"""
AI股票自然语言策略分析系统主入口

【启动方式】
- Streamlit Cloud: 平台自动执行 `streamlit run main.py`
- 本地 Streamlit: `streamlit run ai_stock_nlp/main.py`
- 本地 Python:  `python ai_stock_nlp/main.py`
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


if __name__ == "__main__":
    # 关键判断：「streamlit」是否已在 sys.modules 中？
    # - streamlit run main.py   → 已加载，直接运行 app 代码
    # - python main.py          → 未加载，启动 streamlit 子进程
    if "streamlit" in sys.modules:
        # 已被 Streamlit 托管运行（Cloud 或 `streamlit run`）
        from presentation_layer.app import main as app_main
        app_main()
    else:
        # 直接 Python 运行，启动 Streamlit 子进程（仅本地开发用）
        import streamlit.web.cli as stcli
        app_path = str(project_root / "presentation_layer" / "app.py")
        sys.argv = [
            "streamlit",
            "run",
            app_path,
            "--server.port=8501",
            "--browser.gatherUsageStats=false",
            "--server.runOnSave=false",
            "--global.developmentMode=false",
        ]
        sys.exit(stcli.main())
