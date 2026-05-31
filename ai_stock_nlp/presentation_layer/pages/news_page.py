"""
个股新闻页面

功能：
1. 使用 akshare.stock_news_em 获取指定个股的新闻
2. 同时展示财新网财经精选（stock_news_main_cx）
3. 支持新闻筛选和详情查看

数据来源：
- 东方财富个股新闻：ak.stock_news_em(symbol="000001")
- 财新网财经精选：ak.stock_news_main_cx()
"""

import streamlit as st
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import time
import re

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def fetch_news(stock_code: str, max_retries: int = 3) -> pd.DataFrame:
    """
    获取个股新闻

    Args:
        stock_code: 股票代码
        max_retries: 最大重试次数

    Returns:
        DataFrame 包含新闻数据
    """
    import akshare as ak

    for attempt in range(max_retries):
        try:
            df = ak.stock_news_em(symbol=stock_code)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            continue

    return pd.DataFrame()


def fetch_main_news(max_retries: int = 3) -> pd.DataFrame:
    """
    获取财新网财经精选

    Args:
        max_retries: 最大重试次数

    Returns:
        DataFrame 包含财新新闻
    """
    import akshare as ak

    for attempt in range(max_retries):
        try:
            df = ak.stock_news_main_cx()
            if df is not None and not df.empty:
                return df
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            continue

    return pd.DataFrame()


def clean_html(text: str) -> str:
    """清理 HTML 标签"""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def highlight_keywords(text: str, keywords: list = None) -> str:
    """在文本中高亮关键词"""
    if not text or not keywords:
        return text

    result = str(text)
    for kw in keywords:
        result = result.replace(kw, f"<mark>{kw}</mark>")
    return result


def render_news_page():
    """渲染个股新闻页面"""
    st.set_page_config(page_title="个股新闻", page_icon="📰", layout="wide")

    # 获取股票信息
    query_params = st.query_params
    stock_code = query_params.get("code", "")
    stock_name = query_params.get("name", "")

    if not stock_code:
        st.error("未指定股票代码")
        return

    # 顶部标题栏
    col1, col2, col3, col4 = st.columns([1, 5, 1, 1])
    with col1:
        if st.button("← 返回", type="secondary", key="news_back_btn"):
            # 返回K线图页面
            st.query_params["page"] = "K线图"
            st.query_params["code"] = stock_code
            st.query_params["name"] = stock_name
            st.rerun()

    with col2:
        st.title(f"📰 {stock_name} ({stock_code}) 新闻资讯")

    with col3:
        if st.button("🔄 刷新新闻", type="primary", key="news_refresh_btn"):
            st.session_state.pop("news_cache", None)
            st.rerun()

    with col4:
        if st.button("📈 K线图", type="secondary", key="news_kline_btn"):
            st.query_params["page"] = "K线图"
            st.query_params["code"] = stock_code
            st.query_params["name"] = stock_name
            st.rerun()

    # 使用缓存避免重复请求
    if "news_cache" not in st.session_state:
        st.session_state.news_cache = {}

    cache_key = f"news_{stock_code}"

    # Tab 切换：个股新闻 / 财经精选
    tab1, tab2 = st.tabs([f"📋 {stock_name} 个股新闻", "🌐 财新财经精选"])

    # ========== Tab 1: 个股新闻 ==========
    with tab1:
        # 获取个股新闻
        if cache_key not in st.session_state.news_cache:
            with st.spinner(f"正在获取 {stock_name} 的最新新闻..."):
                news_df = fetch_news(stock_code)
                st.session_state.news_cache[cache_key] = news_df
        else:
            news_df = st.session_state.news_cache[cache_key]

        if news_df.empty:
            st.warning(f"未获取到 {stock_name} 的新闻数据，可能网络不稳定或该股票暂无新闻")
        else:
            # 显示新闻统计
            st.caption(f"共获取 {len(news_df)} 条新闻")

            # 搜索过滤
            search_keyword = st.text_input(
                "🔍 搜索新闻标题/内容",
                placeholder="输入关键词过滤新闻...",
                key="stock_news_search"
            )

            # 过滤数据
            display_df = news_df.copy()

            if search_keyword:
                # 标题或内容包含关键词
                title_col = "新闻标题" if "新闻标题" in display_df.columns else display_df.columns[0]
                content_col = "新闻内容" if "新闻内容" in display_df.columns else None

                mask = display_df[title_col].astype(str).str.contains(
                    search_keyword, case=False, na=False
                )
                if content_col and content_col in display_df.columns:
                    mask = mask | display_df[content_col].astype(str).str.contains(
                        search_keyword, case=False, na=False
                    )
                display_df = display_df[mask]

                st.caption(f"搜索结果: {len(display_df)} 条")

            if display_df.empty:
                st.info("没有匹配的新闻")
            else:
                # 渲染新闻列表
                render_stock_news_list(display_df, stock_name)

    # ========== Tab 2: 财新财经精选 ==========
    with tab2:
        main_cache_key = "cx_news"
        if main_cache_key not in st.session_state.news_cache:
            with st.spinner("正在获取财新财经精选..."):
                cx_df = fetch_main_news()
                st.session_state.news_cache[main_cache_key] = cx_df
        else:
            cx_df = st.session_state.news_cache[main_cache_key]

        if cx_df.empty:
            st.warning("未获取到财新财经精选，可能网络不稳定")
        else:
            st.caption(f"共获取 {len(cx_df)} 条精选内容")
            render_cx_news_list(cx_df)


def render_stock_news_list(df: pd.DataFrame, stock_name: str):
    """渲染个股新闻列表（支持展开详情）"""
    # 获取列名
    columns = df.columns.tolist()

    title_col = "新闻标题" if "新闻标题" in columns else columns[0]
    content_col = "新闻内容" if "新闻内容" in columns else None
    time_col = "发布时间" if "发布时间" in columns else None
    source_col = "文章来源" if "文章来源" in columns else None
    link_col = "新闻链接" if "新闻链接" in columns else None

    # 每页显示数量
    page_size = st.slider("每页显示", 5, 50, 15, key="news_page_size")
    total_pages = max(1, (len(df) + page_size - 1) // page_size)
    page = st.number_input(
        "页码", min_value=1, max_value=total_pages, value=1, key="news_page"
    )

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, len(df))
    page_df = df.iloc[start_idx:end_idx]

    st.markdown(f"**第 {page}/{total_pages} 页**（共 {len(df)} 条）")
    st.divider()

    for idx, (_, row) in enumerate(page_df.iterrows()):
        global_idx = start_idx + idx

        title = str(row.get(title_col, ""))
        content = str(row.get(content_col, "")) if content_col and pd.notna(row.get(content_col)) else ""
        pub_time = str(row.get(time_col, "")) if time_col and pd.notna(row.get(time_col)) else ""
        source = str(row.get(source_col, "")) if source_col and pd.notna(row.get(source_col)) else ""
        link = str(row.get(link_col, "")) if link_col and pd.notna(row.get(link_col)) else ""

        # 清理内容
        title = clean_html(title)
        content = clean_html(content)

        # 使用 expander 展示每一条新闻
        expander_title = f"📌 {title[:80]}{'...' if len(title) > 80 else ''}"
        if pub_time:
            expander_title += f"  `{pub_time}`"

        with st.expander(expander_title, expanded=False):
            # 元信息行
            meta_cols = st.columns([2, 2, 1])
            with meta_cols[0]:
                if source:
                    st.caption(f"📢 来源: {source}")
            with meta_cols[1]:
                if pub_time:
                    st.caption(f"🕐 时间: {pub_time}")
            with meta_cols[2]:
                if link:
                    st.markdown(f"[🔗 查看原文]({link})")

            # 新闻内容
            if content:
                # 截取前 500 字符展示，避免过长
                display_content = content[:500]
                if len(content) > 500:
                    display_content += "..."

                st.markdown(
                    f"""<div style="background-color: #f5f5f5; padding: 12px; 
                    border-radius: 6px; line-height: 1.8; font-size: 14px;">
                    {display_content}</div>""",
                    unsafe_allow_html=True,
                )

        st.divider()


def render_cx_news_list(df: pd.DataFrame):
    """渲染财新财经精选列表"""
    columns = df.columns.tolist()

    tag_col = "tag" if "tag" in columns else columns[0]
    summary_col = "summary" if "summary" in columns else None
    url_col = "url" if "url" in columns else None

    # 每页显示
    page_size = st.slider("每页显示", 5, 30, 10, key="cx_page_size")
    total_pages = max(1, (len(df) + page_size - 1) // page_size)
    page = st.number_input(
        "页码", min_value=1, max_value=total_pages, value=1, key="cx_page"
    )

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, len(df))
    page_df = df.iloc[start_idx:end_idx]

    st.markdown(f"**第 {page}/{total_pages} 页**")
    st.divider()

    for _, row in page_df.iterrows():
        tag = str(row.get(tag_col, ""))
        summary = str(row.get(summary_col, "")) if summary_col and pd.notna(row.get(summary_col)) else ""
        url = str(row.get(url_col, "")) if url_col and pd.notna(row.get(url_col)) else ""

        # 标签颜色
        tag_color_map = {
            "今日热点": "#e74c3c",
            "市场动态": "#3498db",
            "市场洞察": "#2ecc71",
            "深度分析": "#9b59b6",
            "宏观要闻": "#e67e22",
        }
        tag_color = tag_color_map.get(tag, "#95a5a6")

        col_left, col_right = st.columns([5, 1])
        with col_left:
            st.markdown(
                f"""<span style="background-color:{tag_color}; color:white; 
                padding:2px 8px; border-radius:3px; font-size:12px; margin-right:8px;">
                {tag}</span> <span style="font-size:15px;">{summary}</span>""",
                unsafe_allow_html=True,
            )
        with col_right:
            if url:
                st.markdown(f"[📎 阅读]({url})", unsafe_allow_html=False)

        st.divider()


if __name__ == "__main__":
    render_news_page()
