"""
Streamlit Web应用主入口

【模块功能】
AI股票自然语言策略分析系统的Web界面，基于Streamlit框架构建。

【页面结构】
1. 首页 - 功能介绍和快速入口
2. 智能选股 - 自然语言选股
3. 网格回测 - 网格交易策略回测
4. 市场概览 - 涨跌幅榜和成交额榜

【核心功能】
- 自然语言输入，自动识别意图和抽取参数
- 选股结果下载
- 批量回测
- 回测结果展示

【技术栈】
- Streamlit: Web框架
- 异步加载: 后台线程加载排行数据
- Session State: 状态管理
"""

import streamlit as st
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, date
import threading

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import FRONTEND_CONFIG
from core.dispatcher import StrategyDispatcher
from core.llm_client import get_llm_client, is_llm_available
from data_layer.akshare_data_fetcher import akshare_fetcher
from data_layer.market_data_cache import market_cache


def go_to_kline_page(stock_code: str, stock_name: str):
    """
    跳转到K线图页面

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
    """
    # 保存当前页面，以便返回
    st.session_state['prev_page'] = st.session_state.current_page
    # 设置K线页面参数
    st.query_params["page"] = "K线图"
    st.query_params["code"] = stock_code
    st.query_params["name"] = stock_name
    st.rerun()


# 页面配置
st.set_page_config(
    page_title=FRONTEND_CONFIG['page_title'],
    page_icon=FRONTEND_CONFIG['page_icon'],
    layout=FRONTEND_CONFIG['layout'],
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# 初始化调度器（使用缓存避免重复创建）
@st.cache_resource
def get_dispatcher():
    """获取策略调度器实例，使用缓存优化"""
    # 优先使用 AI 解析自然语言
    llm_client = None
    if is_llm_available():
        llm_client = get_llm_client()
        print("[OK] AI model connected, using AI-enhanced parsing")
    else:
        print("[WARN] AI model not configured, using rule-based matching")
    return StrategyDispatcher(llm_client=llm_client)

dispatcher = get_dispatcher()


def main():
    """主入口函数，管理页面导航"""
    # 使用 query_params 处理页面导航（更可靠）
    query_params = st.query_params
    
    # 从 URL 参数获取当前页面，默认为首页
    url_page = query_params.get("page", "首页")
    
    # 初始化session_state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = url_page
    elif url_page != st.session_state.current_page:
        # URL 参数变化时更新 session_state
        st.session_state.current_page = url_page
    
    # 侧边栏 - 功能导航（按钮样式）
    st.sidebar.title("功能导航")
    
    pages = ["首页", "智能选股", "策略回测", "市场概览"]
    icons = ["🏠", "🔍", "📊", "📈"]
    
    for page, icon in zip(pages, icons):
        if st.sidebar.button(f"{icon} {page}", use_container_width=True, type="secondary" if st.session_state.current_page != page else "primary"):
            st.query_params["page"] = page
            st.rerun()
    
    if st.session_state.current_page == "首页":
        render_home_page()
    elif st.session_state.current_page == "智能选股":
        render_stock_select_page()
    elif st.session_state.current_page == "策略回测":
        from presentation_layer.pages.backtest_page import render_backtest_page
        render_backtest_page(akshare_fetcher)
    elif st.session_state.current_page == "市场概览":
        render_market_overview_page()
    elif st.session_state.current_page == "K线图":
        from presentation_layer.pages.kline_page import render_kline_page
        render_kline_page()
    elif st.session_state.current_page == "价值投资":
        from presentation_layer.pages.value_invest_page import render_value_invest_page
        render_value_invest_page()
    elif st.session_state.current_page == "AI投研报告":
        from presentation_layer.pages.report_page import render_report_page
        render_report_page()
    elif st.session_state.current_page == "个股新闻":
        from presentation_layer.pages.news_page import render_news_page
        render_news_page()


def render_home_page():
    """首页"""
    st.title("📈 AI股票自然语言策略分析系统")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎯 智能选股")
        st.write("""
        输入自然语言描述，AI将帮您：
        - 筛选符合条件的股票
        - 按行业、涨跌幅、成交额等条件选股
        - 快速找到投资机会
        """)
        if st.button("开始选股 →", key="go_select"):
            st.query_params["page"] = "智能选股"
            st.rerun()
    
    with col2:
        st.subheader("📊 策略回测")
        st.write("""
        基于Backtrader的专业回测：
        - 网格交易策略
        - 完整绩效分析
        - 夏普比率、最大回撤等指标
        """)
        if st.button("开始回测 →", key="go_backtest"):
            st.query_params["page"] = "策略回测"
            st.rerun()
    
    # 首页市场排行
    st.markdown("---")
    st.subheader("📊 市场排行")
    render_home_market_ranking()


def format_intent_description(user_input: str, filters: list) -> str:
    """
    生成用户友好的意图描述
    
    Args:
        user_input: 用户原始输入
        filters: 解析出的过滤条件列表
        
    Returns:
        友好的描述字符串
    """
    if not filters:
        return f"查询: {user_input}"
    
    parts = []
    for f in filters:
        field = f.get('field', '')
        op = f.get('op', '')
        value = f.get('value', '')
        
        op_display = {'>': '>', '<': '<', '>=': '≥', '<=': '≤', '=': '=', 'LIKE': '包含'}.get(op, op)
        
        # 格式化数值
        if isinstance(value, (int, float)):
            if field in ['成交额', '总金额', '流通市值', '总市值']:
                if value >= 100000000:
                    value_display = f"{value/100000000:.1f}亿"
                else:
                    value_display = f"{value/10000:.0f}万"
            elif field in ['涨幅%', '涨跌幅', '换手率']:
                value_display = f"{value:.1f}%"
            else:
                value_display = str(value)
        else:
            value_display = str(value).replace('%', '')
        
        parts.append(f"{field}{op_display}{value_display}")
    
    conditions = "，".join(parts)
    return f"查询「{user_input}」，条件: {conditions}"


def render_stock_select_page():
    """选股页面"""
    st.subheader("🔍 智能选股")

    # 输入区域
    st.subheader("输入选股条件")
    user_input = st.text_area(
        "用自然语言描述您的选股条件：",
        placeholder="例如：帮我找出成交额大于5000万的科技行业股票，价格在10-50元之间",
        height=100
    )

    col1, col2 = st.columns([1, 4])

    with col1:
        submitted = st.button("🔍 开始选股", type="primary")

    with col2:
        use_ai = st.checkbox("启用AI增强解析", value=True)

    if submitted and user_input:
        with st.spinner("正在分析您的需求..."):
            try:
                # 调用调度器处理
                result = dispatcher.process(user_input)

                if result['success']:
                    # 获取filters用于生成友好描述
                    params = result.get('params', {})
                    filters = params.get('filters', [])
                    intent_desc = format_intent_description(user_input, filters)
                    st.success(f"✅ 识别成功: {intent_desc}")

                    if 'data' in result and result['data'] is not None:
                        # 显示选股结果
                        df = result['data']

                        # 检查是否有截断（默认limit=50）
                        limit = result.get('params', {}).get('limit', 50)
                        actual_total = result.get('total', len(df))

                        if len(df) >= limit and actual_total > limit:
                            # 结果被截断，添加警告
                            st.warning(f"⚠️ 符合条件共约 {actual_total} 只，已展示前 {limit} 只。如需查看更多，请调整条件缩小范围或提高限制。")
                            st.subheader(f"📋 选股结果 (展示 {len(df)} 只 / 共约 {actual_total} 只)")
                        else:
                            st.subheader(f"📋 选股结果 (共 {len(df)} 只)")

                        # 保存选股结果到session_state供回测使用
                        st.session_state.selected_stocks = df
                        st.session_state.selected_stocks_params = {
                            'description': user_input,
                            'count': len(df)
                        }

                        # 显示带操作栏的表格（传入filters以动态显示相关列）
                        display_stock_table_with_actions(df, "selection", filters)


                    else:
                        st.info("未找到符合条件的股票，请尝试调整条件")
                else:
                    st.error(f"处理失败: {result.get('message', '未知错误')}")

            except Exception as e:
                st.error(f"执行出错: {str(e)}")





def render_market_overview_page():
    """市场概览页面"""
    st.subheader("📈 市场概览")
    
    with st.spinner("加载市场数据..."):
        try:
            # 市场统计
            overview = akshare_fetcher.get_market_overview()
            
            if not overview.empty:
                row = overview.iloc[0]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("股票总数", f"{row['total_stocks']:,}")
                
                with col2:
                    st.metric("上涨家数", f"{row['up_stocks']:,}")
                
                with col3:
                    st.metric("下跌家数", f"{row['down_stocks']:,}")
                
                with col4:
                    avg_change = row['avg_change']
                    st.metric("平均涨跌幅", f"{avg_change:.2f}%")
            
            # 排行榜
            tab1, tab2, tab3 = st.tabs(["涨幅榜", "跌幅榜", "成交额榜"])
            
            with tab1:
                df = akshare_fetcher.get_top_gainers(20)
                if not df.empty:
                    display_market_table_with_actions(df, "gainers")
            
            with tab2:
                df = akshare_fetcher.get_top_losers(20)
                if not df.empty:
                    display_market_table_with_actions(df, "losers")
            
            with tab3:
                df = akshare_fetcher.get_top_volume(20)
                if not df.empty:
                    display_market_table_with_actions(df, "volume")
                    
        except Exception as e:
            st.error(f"加载失败: {str(e)}")


def render_home_market_ranking():
    """
    首页市场排行组件 - 使用Tab切换展示
    展示涨幅榜、跌幅榜和成交额榜
    数据来源：数据库缓存 market_rank_cache / market_snapshot（快速读取）
    """
    # 初始化session_state
    if 'home_rank_data' not in st.session_state:
        st.session_state.home_rank_data = {
            'gainers': None,
            'losers': None,
            'volume': None,
            'all_stocks': None,
            'load_time': None,
            'loading': False
        }
    
    # 从数据库缓存加载数据（瞬间完成，无需进度条）
    if st.session_state.home_rank_data['gainers'] is None and not st.session_state.home_rank_data['loading']:
        st.session_state.home_rank_data['loading'] = True
        try:
            # 检查缓存是否有数据
            cache_status = market_cache.get_cache_status()
            
            if cache_status.get('has_data'):
                # 直接从数据库读取（毫秒级）
                st.session_state.home_rank_data['gainers'] = market_cache.get_top_gainers(20)
                st.session_state.home_rank_data['losers'] = market_cache.get_top_losers(20)
                st.session_state.home_rank_data['volume'] = market_cache.get_top_volume(20)
                st.session_state.home_rank_data['all_stocks'] = market_cache.get_all_stocks(500)
                st.session_state.home_rank_data['load_time'] = cache_status.get('last_update')
                if isinstance(st.session_state.home_rank_data['load_time'], str):
                    st.session_state.home_rank_data['load_time'] = datetime.strptime(
                        st.session_state.home_rank_data['load_time'], '%Y-%m-%d %H:%M:%S'
                    )
            else:
                # 数据库无缓存，尝试使用API获取（降级方案）
                st.warning("数据库中暂无市场缓存数据，尝试从API获取...")
                st.session_state.home_rank_data['gainers'] = akshare_fetcher.get_top_gainers(20)
                st.session_state.home_rank_data['losers'] = akshare_fetcher.get_top_losers(20)
                st.session_state.home_rank_data['volume'] = akshare_fetcher.get_top_volume(20)
                st.session_state.home_rank_data['all_stocks'] = akshare_fetcher.get_all_stocks(500)
                st.session_state.home_rank_data['load_time'] = datetime.now()
                
        except Exception as e:
            st.error(f"加载市场数据失败: {str(e)}")
        finally:
            st.session_state.home_rank_data['loading'] = False
    
    # 刷新按钮和更新时间
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 刷新", key="refresh_home_rank"):
            st.session_state.home_rank_data = {
                'gainers': None,
                'losers': None,
                'volume': None,
                'all_stocks': None,
                'load_time': None,
                'loading': False
            }
            st.rerun()
    with col2:
        if st.session_state.home_rank_data.get('load_time'):
            st.caption(f"更新时间: {st.session_state.home_rank_data['load_time'].strftime('%H:%M:%S')}")
    
    # 使用Tab切换展示
    tab1, tab2, tab3, tab4 = st.tabs(["📈 涨幅榜", "📉 跌幅榜", "💰 成交额榜", "📋 全部股票"])
    
    with tab1:
        df = st.session_state.home_rank_data.get('gainers')
        if df is not None and not df.empty:
            display_full_rank_table(df, 'gainers')
        else:
            st.info("加载中...")
    
    with tab2:
        df = st.session_state.home_rank_data.get('losers')
        if df is not None and not df.empty:
            display_full_rank_table(df, 'losers')
        else:
            st.info("加载中...")
    
    with tab3:
        df = st.session_state.home_rank_data.get('volume')
        if df is not None and not df.empty:
            display_full_rank_table(df, 'volume')
        else:
            st.info("加载中...")
    
    with tab4:
        df = st.session_state.home_rank_data.get('all_stocks')
        if df is not None and not df.empty:
            display_full_rank_table(df, 'all_stocks')
        else:
            st.info("加载中...")


def display_full_rank_table(df: pd.DataFrame, table_type: str):
    """
    显示完整宽度的市场排行表格（用于首页Tab）
    
    Args:
        df: 股票数据DataFrame
        table_type: 表格类型（gainers/losers/volume/all_stocks）
    """
    # 重命名列
    df = df.rename(columns={'涨跌幅': '涨幅%', '成交额': '总金额'})
    
    # 全部股票显示更多，排行榜只显示前20
    if table_type == 'all_stocks':
        display_df = df.head(200)  # 全部股票显示前200条
    else:
        display_df = df.head(20)
    
    # 显示表头
    if table_type == 'all_stocks':
        header_cols = st.columns([1.5, 1.2, 1.2, 1.2, 1.5])
        headers = ['代码', '名称', '最新价', '涨幅%', '操作']
    else:
        header_cols = st.columns([0.8, 1.5, 1.2, 1.2, 1.2, 1.5])
        headers = ['排名', '代码', '名称', '最新价', '涨幅%' if table_type != 'volume' else '成交额', '操作']
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")
    
    # 为每行显示数据
    for idx, row in display_df.iterrows():
        if table_type == 'all_stocks':
            cols = st.columns([1.5, 1.2, 1.2, 1.2, 1.5])
        else:
            cols = st.columns([0.8, 1.5, 1.2, 1.2, 1.2, 1.5])
        
        if table_type == 'all_stocks':
            # 全部股票视图：无排名，直接显示代码
            col_idx = 0
            with cols[col_idx]:
                st.text(f"{row['代码']}")
            col_idx += 1
            with cols[col_idx]:
                st.text(f"{row['名称']}")
            col_idx += 1
            with cols[col_idx]:
                st.text(f"{row.get('最新价', row.get('价格', '-'))}")
            col_idx += 1
            with cols[col_idx]:
                change = row['涨幅%']
                color = "red" if change > 0 else "green" if change < 0 else "gray"
                st.markdown(f"<span style='color:{color}'>{change:+.2f}%</span>", unsafe_allow_html=True)
            col_idx += 1
            with cols[col_idx]:
                if st.button("📋 详情", key=f"home_kline_{table_type}_{idx}_{row['代码']}"):
                    go_to_kline_page(row['代码'], row['名称'])
        else:
            # 排行榜视图
            with cols[0]:
                # 排名带颜色
                rank = idx + 1
                if rank <= 3:
                    st.markdown(f"**🥇{rank}**" if rank == 1 else f"**🥈{rank}**" if rank == 2 else f"**🥉{rank}**")
                else:
                    st.text(f"{rank}")
            with cols[1]:
                st.text(f"{row['代码']}")
            with cols[2]:
                st.text(f"{row['名称']}")
            with cols[3]:
                st.text(f"{row.get('最新价', row.get('价格', '-'))}")
            with cols[4]:
                if table_type == 'volume':
                    # 格式化成交额
                    amount = row['总金额']
                    if amount >= 10000:
                        st.text(f"{amount/10000:.1f}亿")
                    else:
                        st.text(f"{amount:.0f}万")
                else:
                    change = row['涨幅%']
                    color = "red" if change > 0 else "green" if change < 0 else "gray"
                    st.markdown(f"<span style='color:{color};font-weight:bold'>{change:+.2f}%</span>", unsafe_allow_html=True)
            with cols[5]:
                if st.button("📋 详情", key=f"home_kline_{table_type}_{idx}_{row['代码']}"):
                    go_to_kline_page(row['代码'], row['名称'])


def display_market_table_with_actions(df: pd.DataFrame, table_type: str):
    """
    显示带操作按钮的市场概览表格（使用统一风格）
    
    Args:
        df: 股票数据DataFrame
        table_type: 表格类型（gainers/volume/losers）
    """
    # 重命名列
    df = df.rename(columns={'涨跌幅': '涨幅%', '成交额': '总金额'})
    
    # 显示表头
    cols = st.columns([1.5, 2, 1.2, 1.5, 1.5])
    headers = ['代码', '名称', '涨幅%' if table_type != 'volume' else '总金额', '总金额' if table_type != 'volume' else '涨幅%', '操作']
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    
    # 为每行显示数据和操作按钮
    for idx, row in df.iterrows():
        cols = st.columns([1.5, 2, 1.2, 1.5, 1.5])
        
        with cols[0]:
            st.text(row['代码'])
        with cols[1]:
            st.text(row['名称'])
        with cols[2]:
            if table_type != 'volume':
                change = row['涨幅%']
                color = "red" if change > 0 else "green" if change < 0 else "gray"
                st.markdown(f"<span style='color:{color}'>{change:+.2f}%</span>", unsafe_allow_html=True)
            else:
                # 格式化成交额
                amount = row['总金额']
                if amount >= 10000:
                    st.text(f"{amount/10000:.1f}亿")
                else:
                    st.text(f"{amount:.0f}万")
        with cols[3]:
            if table_type != 'volume':
                amount = row['总金额']
                if amount >= 10000:
                    st.text(f"{amount/10000:.1f}亿")
                else:
                    st.text(f"{amount:.0f}万")
            else:
                change = row['涨幅%']
                color = "red" if change > 0 else "green" if change < 0 else "gray"
                st.markdown(f"<span style='color:{color}'>{change:+.2f}%</span>", unsafe_allow_html=True)
        with cols[4]:
            if st.button("📋 详情", key=f"market_kline_{table_type}_{idx}_{row['代码']}"):
                go_to_kline_page(row['代码'], row['名称'])


def get_display_columns_for_filters(df: pd.DataFrame, filters: list = None) -> tuple:
    """
    根据查询条件确定要显示的列
    
    Args:
        df: 股票数据DataFrame
        filters: 查询条件列表
        
    Returns:
        (display_cols, headers): 要显示的列名列表和表头列表
    """
    # 重命名列（如果存在）
    if '涨跌幅' in df.columns:
        df = df.rename(columns={'涨跌幅': '涨幅%'})
    if '成交额' in df.columns:
        df = df.rename(columns={'成交额': '总金额'})
    
    display_cols = []
    headers = []
    
    # 基础列：代码和名称
    if '代码' in df.columns:
        display_cols.append('代码')
        headers.append('代码')
    if '名称' in df.columns:
        display_cols.append('名称')
        headers.append('名称')
    
    # 根据filters动态添加相关列
    if filters:
        filter_fields = {f.get('field', '') for f in filters}
    else:
        filter_fields = set()
    
    # 涨幅相关
    if '涨幅%' in df.columns:
        display_cols.append('涨幅%')
        headers.append('涨幅%')
    elif '涨幅%' in filter_fields and '涨跌幅' in df.columns:
        display_cols.append('涨跌幅')
        headers.append('涨跌幅')
    
    # 成交额相关
    if '总金额' in df.columns:
        display_cols.append('总金额')
        headers.append('成交额')
    elif '成交额' in filter_fields and '成交额' in df.columns:
        display_cols.append('成交额')
        headers.append('成交额')
    
    # 市值相关
    if '总市值' in df.columns and ('总市值' in filter_fields or '市值' in filter_fields):
        display_cols.append('总市值')
        headers.append('总市值(亿)')
    if '流通市值' in df.columns and ('流通市值' in filter_fields or '市值' in filter_fields):
        display_cols.append('流通市值')
        headers.append('流通市值(亿)')
    
    # 行业相关
    if '细分行业' in df.columns and '细分行业' in filter_fields:
        display_cols.append('细分行业')
        headers.append('细分行业')
    
    # 价格相关
    if '最新价' in df.columns and ('最新价' in filter_fields or '现价' in filter_fields or '价格' in filter_fields):
        display_cols.append('最新价')
        headers.append('最新价')
    
    # 如果没有根据filters添加任何列，添加默认列
    default_cols = ['涨幅%', '总金额', '最新价']
    default_headers = ['涨幅%', '成交额', '最新价']
    for col, header in zip(default_cols, default_headers):
        if col not in display_cols and col in df.columns:
            display_cols.append(col)
            headers.append(header)
    
    return display_cols, headers


def display_stock_table_with_actions(df: pd.DataFrame, table_type: str, filters: list = None):
    """
    显示带操作按钮的股票表格（统一风格）
    
    Args:
        df: 股票数据DataFrame
        table_type: 表格类型（selection/gainers/volume/losers）
        filters: 查询条件列表，用于决定显示哪些列
    """
    if df.empty:
        st.info("暂无数据")
        return
    
    # 获取要显示的列
    display_cols, headers = get_display_columns_for_filters(df, filters)
    
    # 添加操作列
    headers.append('操作')
    display_cols.append('__action__')  # 占位符
    
    # 计算列宽比例
    col_widths = [1.5] * len(display_cols)
    
    # 显示表头
    cols = st.columns(col_widths)
    for col, header in zip(cols, headers):
        col.markdown(f"**{header}**")
    
    # 为每行显示数据和操作按钮
    for idx, row in df.iterrows():
        cols = st.columns(col_widths)
        
        for col_idx, col_name in enumerate(display_cols):
            if col_name == '__action__':
                # 操作按钮
                with cols[col_idx]:
                    code = str(row.get('代码', ''))
                    name = str(row.get('名称', ''))
                    if st.button("📋 详情", key=f"{table_type}_kline_{idx}_{code}"):
                        go_to_kline_page(code, name)
            elif col_name in df.columns:
                value = row[col_name]
                
                # 特殊格式化
                if col_name in ['涨幅%', '涨跌幅']:
                    change = value
                    color = "red" if change > 0 else "green" if change < 0 else "gray"
                    with cols[col_idx]:
                        st.markdown(f"<span style='color:{color}'>{change:+.2f}%</span>", unsafe_allow_html=True)
                elif col_name in ['总金额', '成交额']:
                    amount = value
                    with cols[col_idx]:
                        if amount >= 10000:
                            st.text(f"{amount/10000:.1f}亿")
                        else:
                            st.text(f"{amount:.0f}万")
                elif col_name in ['总市值', '流通市值']:
                    market_cap = value
                    with cols[col_idx]:
                        if market_cap >= 100000000:
                            st.text(f"{market_cap/100000000:.1f}亿")
                        elif market_cap >= 10000:
                            st.text(f"{market_cap/10000:.0f}万")
                        else:
                            st.text(f"{market_cap:.0f}")
                elif col_name in ['最新价', '价格']:
                    with cols[col_idx]:
                        st.text(f"{value:.2f}")
                else:
                    with cols[col_idx]:
                        st.text(str(value) if pd.notna(value) else '-')


def quick_select(selection_type: str):
    """快速筛选 - 直接获取数据不走AI逻辑"""
    try:
        if selection_type == "涨幅榜":
            df = akshare_fetcher.get_top_gainers(20)
            if not df.empty:
                df = df.rename(columns={'涨跌幅': '涨幅%', '成交额': '总金额'})
                st.dataframe(df[['代码', '名称', '涨幅%', '总金额']], hide_index=True)
            else:
                st.warning("暂无数据")
        elif selection_type == "成交额":
            df = akshare_fetcher.get_top_volume(20)
            if not df.empty:
                df = df.rename(columns={'涨跌幅': '涨幅%', '成交额': '总金额'})
                st.dataframe(df[['代码', '名称', '总金额', '涨幅%']], hide_index=True)
            else:
                st.warning("暂无数据")
        elif selection_type == "跌幅榜":
            df = akshare_fetcher.get_top_losers(20)
            if not df.empty:
                df = df.rename(columns={'涨跌幅': '涨幅%', '成交额': '总金额'})
                st.dataframe(df[['代码', '名称', '涨幅%', '总金额']], hide_index=True)
            else:
                st.warning("暂无数据")
    except Exception as e:
        st.error(f"查询失败: {str(e)}")


if __name__ == "__main__":
    main()
