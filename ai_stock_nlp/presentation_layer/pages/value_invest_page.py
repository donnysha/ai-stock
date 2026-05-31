"""
价值投资页面
展示股票的财务数据和分析
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
import pymysql
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import DB_CONFIG, AI_CONFIG
from config.prompts import VALUE_INVEST_REPORT_PROMPT
from core.llm_client import get_llm_client, is_llm_available


def get_financial_data(stock_code: str):
    """从数据库获取股票财务数据"""
    # 去除股票代码的交易所前缀（如 sz000001 -> 000001）
    import re
    match = re.search(r'(\d{6})', stock_code)
    if match:
        stock_code = match.group(1)
    
    conn = pymysql.connect(**DB_CONFIG)
    try:
        sql = """
            SELECT 
                report_date as 报告期,
                report_type as 类型,
                fiscal_year as 年份,
                fiscal_quarter as 季度,
                revenue as 营收_万元,
                net_profit as 净利润_万元,
                total_assets as 总资产_万元,
                total_liabilities as 总负债_万元,
                equity as 净资产_万元,
                operating_cash_flow as 经营现金流_万元,
                roe as ROE_百分比,
                gross_margin as 毛利率_百分比,
                net_margin as 净利率_百分比,
                revenue_growth as 营收增速_百分比,
                profit_growth as 净利润增速_百分比,
                debt_ratio as 资产负债率_百分比,
                basic_eps as 每股收益
            FROM stock_financial_data
            WHERE stock_code = %s
            ORDER BY fiscal_year DESC, fiscal_quarter DESC
            LIMIT 20
        """
        df = pd.read_sql(sql, conn, params=(stock_code,))
        return df
    finally:
        conn.close()


def calculate_valuation_score(df: pd.DataFrame) -> dict:
    """计算估值评分"""
    if df.empty:
        return {}
    
    scores = {}
    
    # ROE评分 (越高越好)
    latest_roe = df['ROE_百分比'].dropna().iloc[0] if len(df['ROE_百分比'].dropna()) > 0 else 0
    scores['ROE'] = min(100, max(0, latest_roe * 10))  # 10%以上得满分
    
    # 毛利率评分
    latest_gm = df['毛利率_百分比'].dropna().iloc[0] if len(df['毛利率_百分比'].dropna()) > 0 else 0
    scores['毛利率'] = min(100, max(0, latest_gm * 3))  # 30%以上得满分
    
    # 净利率评分
    latest_nm = df['净利率_百分比'].dropna().iloc[0] if len(df['净利率_百分比'].dropna()) > 0 else 0
    scores['净利率'] = min(100, max(0, latest_nm * 5))  # 20%以上得满分
    
    # 营收增速评分
    latest_rg = df['营收增速_百分比'].dropna().iloc[0] if len(df['营收增速_百分比'].dropna()) > 0 else 0
    scores['营收增速'] = min(100, max(0, (latest_rg + 20) * 3))  # 增长20%以上得满分
    
    # 净利润增速评分
    latest_pg = df['净利润增速_百分比'].dropna().iloc[0] if len(df['净利润增速_百分比'].dropna()) > 0 else 0
    scores['净利润增速'] = min(100, max(0, (latest_pg + 20) * 3))
    
    # 资产负债率评分 (越低越好)
    latest_dr = df['资产负债率_百分比'].dropna().iloc[0] if len(df['资产负债率_百分比'].dropna()) > 0 else 50
    scores['资产负债率'] = max(0, 100 - latest_dr * 2)  # 50%以下得满分
    
    # 综合评分
    scores['综合评分'] = sum(scores.values()) / len(scores)
    
    return scores


def format_financial_data_for_ai(df: pd.DataFrame, scores: dict) -> tuple:
    """
    格式化财务数据为AI报告可用的文本格式
    
    Returns:
        (financial_data_str, score_data_str)
    """
    if df.empty:
        return "暂无财务数据", "暂无评分数据"
    
    # 格式化财务数据
    financial_lines = []
    
    # 最新一期数据
    latest = df.iloc[0]
    financial_lines.append(f"【最新报告期】{latest.get('报告期', '未知')} ({latest.get('年份', '')}年 第{latest.get('季度', '')}季度)")
    financial_lines.append("")
    
    # 营收和利润
    revenue = latest.get('营收_万元', 0)
    profit = latest.get('净利润_万元', 0)
    if revenue:
        revenue_str = f"{abs(revenue)/10000:.2f}亿" if abs(revenue) >= 10000 else f"{revenue:.2f}万"
    else:
        revenue_str = "未知"
    if profit:
        profit_str = f"{abs(profit)/10000:.2f}亿" if abs(profit) >= 10000 else f"{profit:.2f}万"
    else:
        profit_str = "未知"
    
    financial_lines.append(f"营业收入: {revenue_str}")
    financial_lines.append(f"净利润: {profit_str}")
    
    # 盈利能力指标
    roe = latest.get('ROE_百分比')
    gross_margin = latest.get('毛利率_百分比')
    net_margin = latest.get('净利率_百分比')
    eps = latest.get('每股收益')
    
    financial_lines.append("")
    financial_lines.append("【盈利能力】")
    if pd.notna(roe):
        financial_lines.append(f"ROE(净资产收益率): {roe:.2f}%")
    if pd.notna(gross_margin):
        financial_lines.append(f"毛利率: {gross_margin:.2f}%")
    if pd.notna(net_margin):
        financial_lines.append(f"净利率: {net_margin:.2f}%")
    if pd.notna(eps):
        financial_lines.append(f"每股收益(EPS): {eps:.2f}元")
    
    # 成长性指标
    revenue_growth = latest.get('营收增速_百分比')
    profit_growth = latest.get('净利润增速_百分比')
    
    financial_lines.append("")
    financial_lines.append("【成长性】")
    if pd.notna(revenue_growth):
        financial_lines.append(f"营收增速: {revenue_growth:.2f}%")
    if pd.notna(profit_growth):
        financial_lines.append(f"净利润增速: {profit_growth:.2f}%")
    
    # 财务安全指标
    debt_ratio = latest.get('资产负债率_百分比')
    cash_flow = latest.get('经营现金流_万元')
    
    financial_lines.append("")
    financial_lines.append("【财务安全】")
    if pd.notna(debt_ratio):
        financial_lines.append(f"资产负债率: {debt_ratio:.2f}%")
    if pd.notna(cash_flow):
        cash_str = f"{abs(cash_flow)/10000:.2f}亿" if abs(cash_flow) >= 10000 else f"{cash_flow:.2f}万"
        financial_lines.append(f"经营现金流: {cash_str}")
    
    # 资产负债情况
    total_assets = latest.get('总资产_万元')
    total_liabilities = latest.get('总负债_万元')
    equity = latest.get('净资产_万元')
    
    financial_lines.append("")
    financial_lines.append("【资产负债情况】")
    if pd.notna(total_assets):
        financial_lines.append(f"总资产: {total_assets/10000:.2f}亿")
    if pd.notna(total_liabilities):
        financial_lines.append(f"总负债: {total_liabilities/10000:.2f}亿")
    if pd.notna(equity):
        financial_lines.append(f"净资产: {equity/10000:.2f}亿")
    
    # 历史趋势（近4期）
    financial_lines.append("")
    financial_lines.append("【历史财务数据(近4期)】")
    for i, (_, row) in enumerate(df.head(4).iterrows()):
        period = f"{int(row.get('年份', 0))}年第{int(row.get('季度', 0))}季"
        revenue_val = row.get('营收_万元', 0)
        revenue_trend = f"{revenue_val/10000:.2f}亿" if pd.notna(revenue_val) and abs(revenue_val) >= 10000 else (f"{revenue_val:.2f}万" if pd.notna(revenue_val) else "N/A")
        roe_val = f"{row.get('ROE_百分比'):.2f}%" if pd.notna(row.get('ROE_百分比')) else "N/A"
        revenue_growth_val = f"{row.get('营收增速_百分比'):.2f}%" if pd.notna(row.get('营收增速_百分比')) else "N/A"
        financial_lines.append(f"  {period}: 营收={revenue_trend}, ROE={roe_val}, 营收增速={revenue_growth_val}")
    
    financial_data_str = "\n".join(financial_lines)
    
    # 格式化评分数据
    score_lines = ["【价值投资评分】"]
    for key, value in scores.items():
        if key != '综合评分':
            score_lines.append(f"  {key}: {value:.1f}分")
    score_lines.append(f"  综合评分: {scores.get('综合评分', 0):.1f}分")
    score_data_str = "\n".join(score_lines)
    
    return financial_data_str, score_data_str


def generate_investment_report(stock_code: str, stock_name: str, df: pd.DataFrame, scores: dict) -> str:
    """
    使用AI生成价值投资报告
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        df: 财务数据DataFrame
        scores: 评分数据
    
    Returns:
        生成的报告文本
    """
    # 格式化数据
    financial_data, score_data = format_financial_data_for_ai(df, scores)
    
    # 构建提示词
    prompt = VALUE_INVEST_REPORT_PROMPT.format(
        stock_code=stock_code,
        stock_name=stock_name,
        financial_data=financial_data,
        score_data=score_data
    )
    
    # 调用AI
    client = get_llm_client()
    
    response = client.chat(
        model=AI_CONFIG['model'],  # 使用配置中的模型
        messages=[
            {"role": "system", "content": "你是一个专业的价值投资投研分析师。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3  # 使用稍高的temperature以保持专业性的同时有一定灵活性
    )
    
    # 提取报告内容
    report = response['choices'][0]['message']['content']
    
    return report


def render_value_invest_page():
    """渲染价值投资页面"""
    st.set_page_config(page_title="价值投资", page_icon="💰", layout="wide")
    
    # 获取股票信息
    query_params = st.query_params
    stock_code = query_params.get("code", "")
    stock_name = query_params.get("name", "")
    
    if not stock_code:
        st.error("未指定股票代码")
        return
    
    # 顶部标题栏
    col1, col2, col3 = st.columns([1, 4, 2])
    with col1:
        if st.button("← 返回", type="secondary", key="back_btn"):
            prev_page = st.session_state.get('prev_page', '首页')
            st.query_params["page"] = prev_page
            st.rerun()
    
    with col2:
        st.title(f"💰 {stock_name} ({stock_code}) 价值投资分析")
    
    with col3:
        col3a, col3b = st.columns(2)
        with col3a:
            if st.button("🔄 刷新", type="secondary", key="refresh_btn"):
                st.rerun()
        with col3b:
            pass  # 报告按钮移至数据加载之后
    
    # 获取财务数据
    with st.spinner("加载财务数据..."):
        try:
            df = get_financial_data(stock_code)
            
            if df.empty:
                st.warning("暂无财务数据，请先同步该股票的财务数据")
                st.info("提示：运行 `python sync_financial_data.py [股票代码]` 同步财务数据")
                return
            
            # 计算评分
            scores = calculate_valuation_score(df)
            
            # 评分概览
            st.subheader("📊 价值评分")
            
            if scores:
                col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
                
                with col1:
                    st.metric("ROE", f"{scores.get('ROE', 0):.1f}分")
                with col2:
                    st.metric("毛利率", f"{scores.get('毛利率', 0):.1f}分")
                with col3:
                    st.metric("净利率", f"{scores.get('净利率', 0):.1f}分")
                with col4:
                    st.metric("营收增速", f"{scores.get('营收增速', 0):.1f}分")
                with col5:
                    st.metric("净利润增速", f"{scores.get('净利润增速', 0):.1f}分")
                with col6:
                    st.metric("资产负债率", f"{scores.get('资产负债率', 0):.1f}分")
                with col7:
                    st.metric("综合评分", f"{scores.get('综合评分', 0):.1f}分", 
                              delta="优秀" if scores.get('综合评分', 0) >= 70 else "良好" if scores.get('综合评分', 0) >= 50 else "一般")
            
            # AI报告按钮（放在数据加载之后）
            col_btn1, col_btn2 = st.columns([1, 5])
            with col_btn1:
                if st.button("📝 AI生成报告", type="primary", key="generate_report_btn"):
                    if not is_llm_available():
                        st.error("AI功能未配置")
                    else:
                        # 保存数据到session_state，跳转到报告页面
                        st.session_state['report_data'] = {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'df': df.to_dict() if not df.empty else None,
                            'scores': scores
                        }
                        st.query_params["page"] = "AI投研报告"
                        st.rerun()
            
            st.markdown("---")
            
            # 财务指标详情
            st.subheader("📈 核心财务指标")
            
            # 最新数据
            latest = df.iloc[0] if not df.empty else None
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if latest is not None and pd.notna(latest.get('营收_万元')):
                    revenue = latest['营收_万元']
                    if abs(revenue) >= 10000:
                        st.metric("营收", f"{revenue/10000:.2f}亿", help="营业总收入(万元)")
                    else:
                        st.metric("营收", f"{revenue:.2f}万")
            
            with col2:
                if latest is not None and pd.notna(latest.get('净利润_万元')):
                    profit = latest['净利润_万元']
                    if abs(profit) >= 10000:
                        st.metric("净利润", f"{profit/10000:.2f}亿")
                    else:
                        st.metric("净利润", f"{profit:.2f}万")
            
            with col3:
                if latest is not None and pd.notna(latest.get('ROE_百分比')):
                    st.metric("ROE", f"{latest['ROE_百分比']:.2f}%")
            
            with col4:
                if latest is not None and pd.notna(latest.get('每股收益')):
                    st.metric("每股收益", f"{latest['每股收益']:.2f}元")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if latest is not None and pd.notna(latest.get('毛利率_百分比')):
                    st.metric("毛利率", f"{latest['毛利率_百分比']:.2f}%")
            
            with col2:
                if latest is not None and pd.notna(latest.get('净利率_百分比')):
                    st.metric("净利率", f"{latest['净利率_百分比']:.2f}%")
            
            with col3:
                if latest is not None and pd.notna(latest.get('资产负债率_百分比')):
                    st.metric("资产负债率", f"{latest['资产负债率_百分比']:.2f}%")
            
            with col4:
                if latest is not None and pd.notna(latest.get('经营现金流_万元')):
                    cash = latest['经营现金流_万元']
                    if abs(cash) >= 10000:
                        st.metric("经营现金流", f"{cash/10000:.2f}亿")
                    else:
                        st.metric("经营现金流", f"{cash:.2f}万")
            
            st.markdown("---")
            
            # 成长性分析
            st.subheader("📈 成长性分析")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if latest is not None and pd.notna(latest.get('营收增速_百分比')):
                    st.metric("营收增速", f"{latest['营收增速_百分比']:.2f}%", 
                              delta="增长" if latest['营收增速_百分比'] > 0 else "下降")
            
            with col2:
                if latest is not None and pd.notna(latest.get('净利润增速_百分比')):
                    st.metric("净利润增速", f"{latest['净利润增速_百分比']:.2f}%",
                              delta="增长" if latest['净利润增速_百分比'] > 0 else "下降")
            
            with col3:
                if len(df) >= 4:
                    avg_revenue_growth = df['营收增速_百分比'].dropna().head(4).mean()
                    st.metric("近4期平均营收增速", f"{avg_revenue_growth:.2f}%")
            
            with col4:
                if len(df) >= 4:
                    avg_profit_growth = df['净利润增速_百分比'].dropna().head(4).mean()
                    st.metric("近4期平均净利润增速", f"{avg_profit_growth:.2f}%")
            
            st.markdown("---")
            
            # 历史财务数据表格
            st.subheader("📋 历史财务数据")
            
            # 格式化显示数据
            display_df = df.copy()
            for col in display_df.columns:
                if '百分比' in col:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "-")
                elif '万元' in col:
                    display_df[col] = display_df[col].apply(lambda x: f"{x/10000:.2f}亿" if pd.notna(x) and abs(x) >= 10000 else (f"{x:.2f}万" if pd.notna(x) else "-"))
                elif col == '每股收益':
                    display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "-")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 投资建议
            st.markdown("---")
            st.subheader("💡 投资建议")
            
            if scores:
                overall = scores.get('综合评分', 0)
                
                if overall >= 80:
                    st.success("⭐⭐⭐ 优秀：该股票财务指标表现优秀，具有较强的投资价值。建议关注。")
                elif overall >= 60:
                    st.info("⭐⭐ 良好：该股票财务指标整体良好，可适当关注。")
                elif overall >= 40:
                    st.warning("⭐ 一般：该股票部分指标表现一般，建议谨慎考虑。")
                else:
                    st.error("⚠️ 欠佳：该股票财务指标表现欠佳，建议回避。")
                
                # 具体建议
                if latest is not None:
                    suggestions = []
                    
                    if pd.notna(latest.get('ROE_百分比')) and latest['ROE_百分比'] >= 15:
                        suggestions.append("✓ ROE表现优秀（≥15%），盈利能力较强")
                    elif pd.notna(latest.get('ROE_百分比')):
                        suggestions.append("○ ROE偏低，需关注盈利能力提升")
                    
                    if pd.notna(latest.get('毛利率_百分比')) and latest['毛利率_百分比'] >= 30:
                        suggestions.append("✓ 毛利率较高（≥30%），具有竞争优势")
                    
                    if pd.notna(latest.get('营收增速_百分比')) and latest['营收增速_百分比'] > 0:
                        suggestions.append("✓ 营收保持增长，成长性良好")
                    elif pd.notna(latest.get('营收增速_百分比')):
                        suggestions.append("○ 营收出现下降，需关注原因")
                    
                    if pd.notna(latest.get('净利润增速_百分比')) and latest['净利润增速_百分比'] > latest.get('营收增速_百分比', 0):
                        suggestions.append("✓ 净利润增速超过营收增速，效益提升")
                    
                    if pd.notna(latest.get('资产负债率_百分比')) and latest['资产负债率_百分比'] <= 50:
                        suggestions.append("✓ 资产负债率健康（≤50%），财务风险较低")
                    elif pd.notna(latest.get('资产负债率_百分比')):
                        suggestions.append("○ 资产负债率偏高，需关注债务风险")
                    
                    if pd.notna(latest.get('经营现金流_万元')) and latest['经营现金流_万元'] > latest.get('净利润_万元', 0):
                        suggestions.append("✓ 经营现金流优于净利润，利润质量高")
                    
                    for s in suggestions:
                        st.write(s)
            
        except Exception as e:
            st.error(f"加载财务数据失败: {str(e)}")
            st.info("请确保数据库连接正常，且已同步该股票的财务数据。")


if __name__ == "__main__":
    render_value_invest_page()
