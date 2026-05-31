"""
K线图展示页面
用于展示单只股票的K线走势
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import date, timedelta

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from data_layer.akshare_data_fetcher import akshare_fetcher
from presentation_layer.charts.kline_chart import KLineChart


def go_to_backtest_page(stock_code: str, stock_name: str):
    """跳转到回测页面"""
    st.session_state['backtest_preset_code'] = stock_code
    st.session_state['backtest_preset_name'] = stock_name
    st.query_params["page"] = "策略回测"
    st.rerun()


def go_to_value_invest_page(stock_code: str, stock_name: str):
    """跳转到价值投资页面"""
    st.session_state['prev_page'] = st.session_state.get('current_page', '首页')
    st.query_params["page"] = "价值投资"
    st.query_params["code"] = stock_code
    st.query_params["name"] = stock_name
    st.rerun()


def go_to_news_page(stock_code: str, stock_name: str):
    """跳转到新闻页面"""
    st.session_state['prev_page'] = st.session_state.get('current_page', 'K线图')
    st.query_params["page"] = "个股新闻"
    st.query_params["code"] = stock_code
    st.query_params["name"] = stock_name
    st.rerun()


def render_kline_page():
    """渲染K线图页面"""
    st.set_page_config(page_title="K线走势", page_icon="📈", layout="wide")
    
    # 获取股票信息
    query_params = st.query_params
    stock_code = query_params.get("code", "")
    stock_name = query_params.get("name", "")
    
    if not stock_code:
        st.error("未指定股票代码")
        return
    
    # 顶部标题栏：返回 + 标题 + 操作按钮
    col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 1, 1, 1, 1])
    with col1:
        if st.button("← 返回", type="secondary", key="back_btn"):
            prev_page = st.session_state.get('prev_page', '首页')
            st.query_params["page"] = prev_page
            st.query_params.clear()
            st.switch_page("app.py")
    
    with col2:
        st.title(f"📈 {stock_name} ({stock_code}) K线走势")
    
    with col3:
        if st.button("🔄 刷新", type="secondary", key="refresh_btn"):
            st.rerun()
    
    with col4:
        if st.button("🚀 回测", type="primary", key="kline_backtest_btn"):
            go_to_backtest_page(stock_code, stock_name)
    
    with col5:
        if st.button("💰 价值投资", type="secondary", key="kline_value_btn"):
            go_to_value_invest_page(stock_code, stock_name)
    
    with col6:
        if st.button("📰 新闻", type="secondary", key="kline_news_btn"):
            go_to_news_page(stock_code, stock_name)
    
    # 时间范围选择
    st.subheader("选择时间范围")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        period = st.selectbox(
            "时间范围",
            options=["近1周", "近1月", "近3月", "近半年", "近1年", "近3年"],
            index=0,  # 默认近1周
            key="kline_period"
        )
    
    with col2:
        adjust = st.selectbox(
            "复权方式",
            options=[("qfq", "前复权"), ("hfq", "后复权"), ("", "不复权")],
            index=0,
            key="kline_adjust"
        )
        adjust_value = adjust[0]
    
    # 根据选择计算日期
    end_date = date.today()
    period_days = {
        "近1周": 7,
        "近1月": 30,
        "近3月": 90,
        "近半年": 180,
        "近1年": 365,
        "近3年": 1095
    }
    days = period_days.get(period, 7)
    start_date = end_date - timedelta(days=days)
    
    # 加载K线数据
    with st.spinner("正在加载K线数据..."):
        try:
            kline_data = akshare_fetcher.get_kline_dataframe(
                stock_code=stock_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                adjust=adjust_value
            )
            
            if kline_data is not None and not kline_data.empty:
                # 显示股票基本信息
                st.info(f"数据范围: {kline_data['date'].min()} 至 {kline_data['date'].max()}，共 {len(kline_data)} 个交易日")
                
                # 创建K线图 (ECharts)
                chart = KLineChart()
                chart.create_kline_chart(
                    df=kline_data,
                    stock_name=f"{stock_name} ({stock_code})",
                    show_ma=True,
                    height="600px"
                )
                chart.render(height="600px", key=f"kline_{stock_code}")
                
                # 显示最近行情数据
                st.subheader("近期行情")
                display_df = kline_data.tail(10)[['date', 'open', 'high', 'low', 'close', 'volume', 'change_pct']].copy()
                display_df = display_df.rename(columns={
                    'date': '日期',
                    'open': '开盘',
                    'high': '最高',
                    'low': '最低',
                    'close': '收盘',
                    'volume': '成交量',
                    'change_pct': '涨跌幅%'
                })
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.warning("未获取到K线数据，可能网络连接不稳定，请稍后重试")
                if st.button("🔄 重试", key="retry_btn"):
                    st.rerun()
        except Exception as e:
            st.error(f"加载K线数据失败: {str(e)}")
            if st.button("🔄 重试", key="retry_btn"):
                st.rerun()


if __name__ == "__main__":
    render_kline_page()
