"""
AI投研报告页面
新窗口展示AI生成的投研报告，支持PDF下载
"""

import streamlit as st
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import AI_CONFIG
from config.prompts import VALUE_INVEST_REPORT_PROMPT
from core.llm_client import get_llm_client, is_llm_available
from presentation_layer.pages.value_invest_page import format_financial_data_for_ai


def generate_investment_report(stock_code: str, stock_name: str, df: pd.DataFrame, scores: dict) -> str:
    """
    使用AI生成价值投资报告
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
        model=AI_CONFIG['model'],
        messages=[
            {"role": "system", "content": "你是一个专业的价值投资投研分析师。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    # 提取报告内容
    report = response['choices'][0]['message']['content']
    
    return report


def markdown_to_pdf(markdown_text: str, stock_name: str, stock_code: str) -> bytes:
    """
    将Markdown转换为PDF
    
    需要安装: pip install fpdf2
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("请先安装fpdf2: pip install fpdf2")
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            self.cell(0, 10, f'{stock_name} ({stock_code}) 价值投研报告', ln=True, align='C')
            self.set_font('Helvetica', '', 10)
            self.cell(0, 8, f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}', ln=True, align='C')
            self.ln(5)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'第 {self.page_no()} 页', align='C')
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # 解析Markdown并添加内容
    lines = markdown_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        if not line:
            pdf.ln(3)
            continue
        
        # 标题
        if line.startswith('### '):
            pdf.set_font('Helvetica', 'B', 14)
            pdf.ln(3)
            pdf.multi_cell(0, 8, line[4:])
            pdf.ln(2)
        elif line.startswith('## '):
            pdf.set_font('Helvetica', 'B', 16)
            pdf.ln(5)
            pdf.multi_cell(0, 10, line[3:])
            pdf.ln(2)
        elif line.startswith('# '):
            pdf.set_font('Helvetica', 'B', 18)
            pdf.ln(3)
            pdf.multi_cell(0, 12, line[2:])
            pdf.ln(3)
        # 列表项
        elif line.startswith('- ') or line.startswith('• '):
            pdf.set_font('Helvetica', '', 11)
            pdf.cell(8)
            pdf.multi_cell(0, 6, f"• {line[2:]}")
        # 粗体
        elif '**' in line:
            pdf.set_font('Helvetica', 'B', 11)
            # 简单处理：移除**并输出
            clean_line = line.replace('**', '')
            pdf.multi_cell(0, 6, clean_line)
        else:
            pdf.set_font('Helvetica', '', 11)
            pdf.multi_cell(0, 6, line)
    
    return pdf.output()


def render_report_page():
    """渲染报告页面"""
    st.set_page_config(
        page_title="AI投研报告",
        page_icon="📊",
        layout="wide"
    )
    
    # 检查是否有报告数据
    if 'report_data' not in st.session_state:
        st.error("未找到报告数据，请从价值投资页面生成报告")
        if st.button("返回价值投资页面"):
            st.query_params["page"] = "价值投资"
            st.rerun()
        return
    
    report_data = st.session_state['report_data']
    stock_code = report_data['stock_code']
    stock_name = report_data['stock_name']
    df = pd.DataFrame(report_data['df']) if report_data['df'] else pd.DataFrame()
    scores = report_data['scores']
    
    # 顶部标题栏
    col1, col2, col3 = st.columns([1, 4, 2])
    with col1:
        if st.button("← 返回分析页", type="secondary", key="back_btn"):
            st.query_params["page"] = "价值投资"
            st.query_params["code"] = stock_code
            st.query_params["name"] = stock_name
            st.rerun()
    
    with col2:
        st.title(f"📊 {stock_name} ({stock_code}) AI投研报告")
    
    # 生成报告
    if 'report_content' not in st.session_state:
        with st.spinner("正在生成投研报告，请稍候..."):
            try:
                report = generate_investment_report(stock_code, stock_name, df, scores)
                st.session_state['report_content'] = report
                st.session_state['report_error'] = None
            except Exception as e:
                st.session_state['report_error'] = str(e)
                st.session_state['report_content'] = None
    
    # 显示结果
    if st.session_state.get('report_error'):
        st.error(f"生成报告失败: {st.session_state['report_error']}")
        if st.button("重试", key="retry_btn"):
            st.session_state['report_content'] = None
            st.session_state['report_error'] = None
            st.rerun()
    elif st.session_state.get('report_content'):
        # 下载按钮区域
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
        
        with col_btn1:
            # Markdown下载
            report_text = st.session_state['report_content']
            report_bytes = report_text.encode('utf-8-sig')
            current_date = datetime.now().strftime('%Y%m%d')
            filename_md = f"{stock_name}_{stock_code}_价值投研报告_{current_date}.md"
            st.download_button(
                label="📥 Markdown",
                data=report_bytes,
                file_name=filename_md,
                mime="text/markdown",
                key="download_md_btn"
            )
        
        with col_btn2:
            # PDF下载
            try:
                pdf_bytes = markdown_to_pdf(report_text, stock_name, stock_code)
                filename_pdf = f"{stock_name}_{stock_code}_价值投研报告_{current_date}.pdf"
                st.download_button(
                    label="📥 PDF",
                    data=pdf_bytes,
                    file_name=filename_pdf,
                    mime="application/pdf",
                    key="download_pdf_btn"
                )
            except ImportError as e:
                st.button("📥 PDF (需安装)", disabled=True)
                st.caption(f"提示: {e}")
            except Exception as e:
                st.button("📥 PDF", disabled=True)
                st.caption(f"PDF生成失败: {e}")
        
        st.markdown("---")
        
        # 显示报告内容
        st.markdown(st.session_state['report_content'])


if __name__ == "__main__":
    render_report_page()
