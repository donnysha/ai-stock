"""
选股页面
提供自然语言选股功能
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from presentation_layer.charts.kline_chart import KLineChart


def get_display_columns(filters):
    """
    根据查询条件动态决定显示哪些列

    Args:
        filters: 查询条件列表

    Returns:
        list: 要显示的列名列表
    """
    # 基础列（始终显示）
    base_columns = ['代码', '名称']

    # 根据条件添加相关列
    dynamic_columns = []

    for f in filters:
        field = f.get('field', '')
        source = f.get('source', 'market')

        # 涨跌幅相关
        if field in ['涨幅%', '涨跌幅', '涨跌额']:
            if '涨跌幅' not in dynamic_columns:
                dynamic_columns.append('涨跌幅')
            if '涨跌额' not in dynamic_columns:
                dynamic_columns.append('涨跌额')

        # 成交额/成交量相关
        if field in ['成交额', '总金额', '成交量']:
            if '成交额' not in dynamic_columns:
                dynamic_columns.append('成交额')
            if '成交量' not in dynamic_columns:
                dynamic_columns.append('成交量')

        # 市值相关
        if field in ['总市值', '流通市值', '市值']:
            if '总市值' not in dynamic_columns:
                dynamic_columns.append('总市值')
            if '流通市值' not in dynamic_columns:
                dynamic_columns.append('流通市值')

        # 价格相关
        if field in ['现价', '价格', '最新价']:
            if '最新价' not in dynamic_columns:
                dynamic_columns.append('最新价')

        # 市盈率/市净率
        if field in ['市盈率', '市净率', '市盈(动)']:
            if '市盈率-动态' not in dynamic_columns:
                dynamic_columns.append('市盈率-动态')
            if '市净率' not in dynamic_columns:
                dynamic_columns.append('市净率')

        # 行业/板块相关
        if field in ['细分行业', '行业', '地区', '板块']:
            if '细分行业' not in dynamic_columns:
                dynamic_columns.append('细分行业')
            if '地区' not in dynamic_columns:
                dynamic_columns.append('地区')

        # 换手率
        if field in ['换手率', '换手%']:
            if '换手率' not in dynamic_columns:
                dynamic_columns.append('换手率')

        # ====== 价值投资/财报列 ======
        if source == 'financial' or field in [
            '净资产收益率ROE', 'ROE', '销售净利率', '净利率', '毛利率',
            '基本每股收益', 'EPS', '资产负债率', '负债率', '流动比率',
            '经营性现金流', '现金流', '营收增速', '净利润增速',
            '归母净利润', '净利润', '股息率'
        ]:
            # 添加常用财报显示列
            fin_show_cols = [
                'ROE(%)', '销售净利率(%)', '资产负债率(%)',
                '净利润增速(%)', '经营性现金流(万)', '每股收益', '财报报告期'
            ]
            for fc in fin_show_cols:
                if fc not in dynamic_columns:
                    dynamic_columns.append(fc)

    # 始终添加常用列（如果数据中存在）
    always_show = ['今开', '最高', '最低', '昨收']
    for col in always_show:
        if col not in dynamic_columns and col not in base_columns:
            dynamic_columns.append(col)

    return base_columns + dynamic_columns


def format_column_value(value, column):
    """
    格式化列值显示

    Args:
        value: 原始值
        column: 列名

    Returns:
        格式化后的值
    """
    if pd.isna(value):
        return '-'

    # 市值格式化（转换为亿）
    if column in ['总市值', '流通市值']:
        if value >= 100000000:
            return f"{value/100000000:.2f}亿"
        elif value >= 10000:
            return f"{value/10000:.0f}万"
        else:
            return f"{value:.0f}"

    # 成交额格式化
    if column == '成交额':
        if value >= 100000000:
            return f"{value/100000000:.2f}亿"
        elif value >= 10000:
            return f"{value/10000:.0f}万"
        else:
            return f"{value:.0f}"

    # 涨跌幅格式化
    if column in ['涨跌幅', '涨幅%']:
        return f"{value:.2f}%"

    # 换手率格式化
    if column == '换手率':
        return f"{value:.2f}%"

    # 价格格式化
    if column in ['最新价', '现价', '今开', '最高', '最低', '昨收']:
        if isinstance(value, (int, float)):
            return f"{value:.2f}"

    # 财报百分比格式化
    if column in ['ROE(%)', '销售净利率(%)', '毛利率(%)', '资产负债率(%)',
                  '营收增速(%)', '净利润增速(%)']:
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"

    # 现金流/利润格式化（万 -> 亿）
    if column in ['经营性现金流(万)', '归母净利润(万)', '营业总收入(万)']:
        if isinstance(value, (int, float)):
            if abs(value) >= 10000:
                return f"{value/10000:.2f}亿"
            else:
                return f"{value:.2f}万"

    # 流动比率
    if column == '流动比率':
        if isinstance(value, (int, float)):
            return f"{value:.2f}"

    # 每股收益
    if column == '每股收益':
        if isinstance(value, (int, float)):
            return f"{value:.2f}"

    return value


def format_intent_description(user_input, filters):
    """
    生成用户友好的意图描述

    Args:
        user_input: 原始用户输入
        filters: 解析出的筛选条件

    Returns:
        str: 格式化的描述
    """
    if not filters:
        return user_input

    # 提取关键条件生成描述
    conditions = []
    for f in filters:
        field = f.get('field', '')
        op = f.get('op', '')
        value = f.get('value', '')

        # 格式化数值
        if isinstance(value, (int, float)):
            if field in ['成交额', '总金额', '流通市值', '总市值']:
                if value >= 100000000:
                    value_str = f"{value/100000000:.0f}亿"
                else:
                    value_str = f"{value/10000:.0f}万"
            elif field in ['涨幅%', '涨跌幅', '换手率']:
                value_str = f"{value:.1f}%"
            else:
                value_str = str(value)
        else:
            value_str = str(value).replace('%', '')

        op_display = {'>': '>', '<': '<', '>=': '≥', '<=': '≤', '=': '=', 'LIKE': '包含'}.get(op, op)

        if op.upper() == 'LIKE':
            conditions.append(f"{field}{op_display}\"{value_str}\"")
        else:
            conditions.append(f"{field}{op_display}{value_str}")

    return f"查询: {user_input}\n条件: {', '.join(conditions[:5])}"


def render_stock_select_page(dispatcher, akshare_fetcher):
    """
    渲染选股页面

    Args:
        dispatcher: 策略调度器
        akshare_fetcher: 数据获取器
    """
    st.subheader("🔍 智能选股")

    # 输入区域
    st.subheader("输入选股条件")
    user_input = st.text_area(
        "用自然语言描述您的选股条件：",
        placeholder="例如：帮我找出成交额大于5000万的科技行业股票，价格在10-50元之间",
        height=100,
        key="stock_select_input"
    )

    col1, col2 = st.columns([1, 4])

    with col1:
        submitted = st.button("🔍 开始选股", type="primary", key="stock_select_submit")

    with col2:
        use_ai = st.checkbox("启用AI增强解析", value=True, key="stock_select_ai")

    if submitted and user_input:
        with st.spinner("正在分析您的需求..."):
            try:
                # 调用调度器处理
                result = dispatcher.process(user_input)

                if result['success']:
                    # 显示意图识别结果 - 使用用户友好的描述
                    params = result.get('params', {})
                    filters = params.get('filters', [])

                    # 生成友好的意图描述
                    intent_desc = format_intent_description(user_input, filters)
                    st.success(f"✅ 识别成功: {intent_desc}")

                    if filters:
                        # 格式化查询条件用于显示
                        conditions_display = []
                        for f in filters:
                            field = f.get('field', '')
                            op = f.get('op', '')
                            value = f.get('value', '')
                            op_display = {
                                '>': '>',
                                '<': '<',
                                '>=': '>=',
                                '<=': '<=',
                                '=': '=',
                                'LIKE': '包含'
                            }.get(op, op)

                            if isinstance(value, (int, float)):
                                # 格式化数值
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

                            condition_str = f"{field} {op_display} {value_display}"
                            conditions_display.append(condition_str)

                        # 保存查询条件到session_state
                        st.session_state.current_filters = conditions_display
                        st.session_state.current_params = params

                        # 用可展开区域显示条件
                        with st.expander("📋 当前查询条件", expanded=True):
                            st.markdown("**查询条件如下：**")
                            for i, cond in enumerate(conditions_display, 1):
                                st.markdown(f"  {i}. **{cond}**")

                            # 添加JSON格式的原始数据（可选，方便调试）
                            with st.expander("查看原始JSON数据"):
                                st.json(params)
                    else:
                        st.warning("⚠️ 未能解析出有效的筛选条件，可能只识别到了意图但没有提取到参数")

                    st.markdown("---")

                    if 'data' in result and result['data'] is not None:
                        # 显示选股结果
                        df = result['data']

                        # 检查是否有截断（默认limit=50）
                        limit = result.get('params', {}).get('limit', 50)
                        actual_total = result.get('total', len(df))

                        # 构建带查询条件提示的标题
                        if 'current_filters' in st.session_state and st.session_state.current_filters:
                            filter_text = " | ".join(st.session_state.current_filters[:3])
                            if len(st.session_state.current_filters) > 3:
                                filter_text += "..."
                            filter_tooltip = "\n".join(st.session_state.current_filters)
                            title = f"📋 选股结果 (展示 {len(df)} 只 / 共约 {actual_total} 只)"
                            st.markdown(f"**{title}**")
                            st.caption(f"查询条件: {filter_tooltip}")
                        elif len(df) >= limit and actual_total > limit:
                            # 结果被截断，添加警告
                            st.warning(f"⚠️ 符合条件共约 {actual_total} 只，已展示前 {limit} 只。如需查看更多，请调整条件缩小范围或提高限制。")
                            st.subheader(f"📋 选股结果 (展示 {len(df)} 只 / 共约 {actual_total} 只)")
                        else:
                            st.subheader(f"📋 选股结果 (共 {len(df)} 只)")

                        # 根据查询条件动态确定显示列
                        if filters:
                            display_cols = get_display_columns(filters)
                        else:
                            # 默认显示常用列
                            display_cols = ['代码', '名称', '涨跌幅', '最新价', '成交额', '细分行业']

                        # 过滤出存在的列
                        available_cols = [col for col in display_cols if col in df.columns]

                        # 如果没有找到任何列，使用全部列
                        if not available_cols:
                            available_cols = list(df.columns)

                        # 准备显示数据（格式化数值列）
                        display_df = df[available_cols].copy()
                        for col in available_cols:
                            if col in ['总市值', '流通市值', '成交额', '涨跌幅', '换手率', '最新价', '涨跌额', '今开', '最高', '最低', '昨收']:
                                display_df[col] = display_df[col].apply(lambda x: format_column_value(x, col))

                        # 显示数据表格
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            hide_index=True
                        )

                        # 显示列说明
                        st.caption(f"显示列: {', '.join(available_cols[2:])}")

                        # 下载按钮（使用原始数据）
                        csv = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            "📥 下载结果 (CSV)",
                            csv,
                            "stock_selection_result.csv",
                            "text/csv",
                            key="stock_select_download"
                        )

                        # 保存选股结果到session_state供回测使用
                        st.session_state.selected_stocks = df
                        st.session_state.selected_stocks_params = {
                            'description': user_input,
                            'count': len(df)
                        }

                        # 回测按钮
                        st.markdown("---")
                        col1, col2, col3 = st.columns([1, 1, 2])
                        with col1:
                            if st.button("📊 批量回测选中股票", type="primary", key="batch_backtest_selected_btn"):
                                st.query_params["page"] = "网格回测"
                                st.query_params["batch"] = "selected"
                                st.rerun()
                        with col2:
                            if st.button("📈 批量回测全部结果", type="secondary", key="batch_backtest_all_btn"):
                                st.query_params["page"] = "网格回测"
                                st.query_params["batch"] = "all"
                                st.rerun()
                        with col3:
                            st.caption(f"已保存 {len(df)} 只股票用于回测")

                    else:
                        st.info("未找到符合条件的股票，请尝试调整条件")
                else:
                    st.error(f"处理失败: {result.get('message', '未知错误')}")

            except Exception as e:
                st.error(f"执行出错: {str(e)}")


def show_kline_chart(stock_code: str, stock_name: str):
    """
    显示K线图弹窗

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
    """
    # 将当前选中的股票存入session_state
    st.session_state['kline_stock_code'] = stock_code
    st.session_state['kline_stock_name'] = stock_name
    st.session_state['show_kline_dialog'] = True
    st.rerun()


def go_to_backtest(stock_code: str, stock_name: str):
    """
    跳转到回测页面并预填充股票

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
    """
    # 设置回测参数
    st.session_state['backtest_preset_code'] = stock_code
    st.session_state['backtest_preset_name'] = stock_name
    # 跳转到回测页面
    st.query_params["page"] = "策略回测"
    st.rerun()


def render_kline_dialog(akshare_fetcher):
    """
    渲染K线图弹窗（默认展示近1周K线走势）

    Args:
        akshare_fetcher: 数据获取器
    """
    if st.session_state.get('show_kline_dialog', False):
        stock_code = st.session_state.get('kline_stock_code', '')
        stock_name = st.session_state.get('kline_stock_name', '')

        # 使用 st.expander 作为弹窗替代
        with st.expander(f"📈 {stock_name} ({stock_code}) K线走势", expanded=True):
            # 加载近1周K线数据（降低失败率）
            end_date = date.today()
            start_date = end_date - timedelta(days=7)

            with st.spinner("正在加载K线数据..."):
                try:
                    kline_data = akshare_fetcher.get_kline_dataframe(
                        stock_code=stock_code,
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d")
                    )

                    if kline_data is not None and not kline_data.empty:
                        chart = KLineChart()
                        chart.create_kline_chart(
                            df=kline_data,
                            stock_name=f"{stock_name} ({stock_code})",
                            show_ma=True,
                            height="500px"
                        )
                        chart.render(height="500px", key=f"dialog_kline_{stock_code}")
                    else:
                        st.warning("未获取到K线数据")
                except Exception as e:
                    st.error(f"加载K线数据失败: {str(e)}")

            if st.button("关闭", key="close_kline"):
                st.session_state['show_kline_dialog'] = False
                st.rerun()
