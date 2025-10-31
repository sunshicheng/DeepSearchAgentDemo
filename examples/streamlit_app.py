"""
Streamlit Web界面
为Deep Search Agent提供友好的Web界面
"""

import os
import sys
import streamlit as st
from datetime import datetime
import warnings
import json
import hashlib
from pathlib import Path

# 忽略 Streamlit 媒体文件存储错误（这是 Streamlit 的内部问题，不影响功能）
warnings.filterwarnings('ignore', category=UserWarning, module='streamlit')

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from deep_research import DeepSearchAgent, Config


def get_historical_reports(output_dir="streamlit_reports"):
    """获取历史报告列表"""
    reports = []
    if not os.path.exists(output_dir):
        return reports
    
    for file in Path(output_dir).glob("deep_search_report_*.md"):
        # 获取文件信息
        stat = file.stat()
        file_info = {
            'filename': file.name,
            'filepath': str(file),
            'modified_time': datetime.fromtimestamp(stat.st_mtime),
            'size': stat.st_size
        }
        
        # 尝试找到对应的状态文件
        state_file = file.with_name(file.name.replace('deep_search_report_', 'state_').replace('.md', '.json'))
        if state_file.exists():
            file_info['state_file'] = str(state_file)
        
        reports.append(file_info)
    
    # 按修改时间倒序排列
    reports.sort(key=lambda x: x['modified_time'], reverse=True)
    return reports


def update_status_info(container):
    """更新状态信息显示"""
    if 'agent' in st.session_state and hasattr(st.session_state.agent, 'state'):
        progress = st.session_state.agent.get_progress_summary()
        with container.container():
            st.metric("总段落数", progress['total_paragraphs'])
            st.metric("已完成", progress['completed_paragraphs'])
            st.progress(progress['progress_percentage'] / 100)
    else:
        container.info("尚未开始研究")


def main():
    """主函数"""
    st.set_page_config(
        page_title="Deep Search Agent",
        page_icon="🔍",
        layout="wide"
    )

    st.title("Deep Search Agent")
    st.markdown("基于DeepSeek的无框架深度搜索AI代理")
    
    # 顶部导航选项卡
    main_tab, history_tab = st.tabs(["🔍 新建研究", "📚 历史报告"])

    # 历史报告标签页
    with history_tab:
        show_historical_reports()
    
    # 新建研究标签页
    with main_tab:
        run_new_research()


def show_historical_reports():
    """显示历史报告"""
    st.header("📚 历史报告")
    
    # 获取历史报告
    reports = get_historical_reports()
    
    if not reports:
        st.info("暂无历史报告。开始一个新研究来生成你的第一份报告！")
        return
    
    st.markdown(f"共找到 **{len(reports)}** 份历史报告")
    
    # 添加搜索和筛选功能
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 搜索报告", placeholder="输入关键词搜索...")
    with col2:
        sort_by = st.selectbox("排序方式", ["最新优先", "最旧优先", "文件名"])
    
    # 筛选报告
    filtered_reports = reports
    if search_term:
        filtered_reports = [r for r in reports if search_term.lower() in r['filename'].lower()]
    
    # 排序
    if sort_by == "最旧优先":
        filtered_reports.sort(key=lambda x: x['modified_time'])
    elif sort_by == "文件名":
        filtered_reports.sort(key=lambda x: x['filename'])
    
    if not filtered_reports:
        st.warning("没有找到匹配的报告")
        return
    
    # 显示报告列表
    for i, report in enumerate(filtered_reports):
        with st.expander(
            f"📄 {report['filename']} | {report['modified_time'].strftime('%Y-%m-%d %H:%M:%S')} | {report['size'] / 1024:.1f} KB",
            expanded=(i == 0)  # 默认展开第一个
        ):
            # 读取报告内容
            try:
                with open(report['filepath'], 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 创建子标签
                if 'state_file' in report:
                    report_tab, state_tab, download_tab = st.tabs(["报告内容", "状态信息", "下载"])
                else:
                    report_tab, download_tab = st.tabs(["报告内容", "下载"])
                
                with report_tab:
                    st.markdown(content)
                
                # 状态信息标签
                if 'state_file' in report:
                    with state_tab:
                        try:
                            with open(report['state_file'], 'r', encoding='utf-8') as f:
                                state_data = json.load(f)
                            
                            # 显示基本信息
                            st.subheader("基本信息")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("查询", state_data.get('query', 'N/A'))
                            with col2:
                                st.metric("段落数", len(state_data.get('paragraphs', [])))
                            with col3:
                                st.metric("状态", state_data.get('status', 'N/A'))
                            
                            # 显示段落详情
                            if 'paragraphs' in state_data:
                                st.subheader("段落详情")
                                for j, para in enumerate(state_data['paragraphs']):
                                    with st.expander(f"段落 {j+1}: {para.get('title', 'N/A')}"):
                                        st.write("**预期内容:**", para.get('content', 'N/A'))
                                        if 'research' in para:
                                            research = para['research']
                                            st.write("**搜索次数:**", len(research.get('search_history', [])))
                                            st.write("**反思次数:**", research.get('reflection_iteration', 0))
                                            latest_summary = research.get('latest_summary', '')
                                            if latest_summary:
                                                st.write("**最终总结:**", latest_summary[:300] + "..." if len(latest_summary) > 300 else latest_summary)
                        except Exception as e:
                            st.error(f"读取状态文件失败: {str(e)}")
                
                # 下载标签
                with download_tab:
                    col1, col2 = st.columns(2)
                    
                    # 为每个下载按钮生成唯一的 key，使用时间戳和索引避免冲突
                    unique_id = f"{report['modified_time'].timestamp()}_{i}"
                    
                    with col1:
                        # 每次都重新编码数据，避免缓存问题
                        report_data = content.encode('utf-8')
                        st.download_button(
                            label="📄 下载Markdown报告",
                            data=report_data,
                            file_name=report['filename'],
                            mime="text/markdown",
                            key=f"dl_md_{unique_id}",
                            use_container_width=True
                        )
                    
                    with col2:
                        if 'state_file' in report:
                            try:
                                with open(report['state_file'], 'r', encoding='utf-8') as f:
                                    state_content = f.read()
                                state_data = state_content.encode('utf-8')
                                st.download_button(
                                    label="📊 下载状态文件",
                                    data=state_data,
                                    file_name=os.path.basename(report['state_file']),
                                    mime="application/json",
                                    key=f"dl_json_{unique_id}",
                                    use_container_width=True
                                )
                            except Exception as e:
                                st.warning(f"状态文件下载暂时不可用")
                        else:
                            st.info("无状态文件")
                    
                    # 删除按钮
                    st.divider()
                    if st.button(f"🗑️ 删除此报告", key=f"del_{unique_id}", type="secondary", use_container_width=True):
                        try:
                            os.remove(report['filepath'])
                            if 'state_file' in report and os.path.exists(report['state_file']):
                                os.remove(report['state_file'])
                            st.success("报告已删除！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败: {str(e)}")
                            
            except Exception as e:
                st.error(f"读取报告失败: {str(e)}")


def run_new_research():
    """运行新研究的界面"""
    # 侧边栏配置
    with st.sidebar:
        st.header("配置")

        # API密钥配置
        st.subheader("API密钥")
        deepseek_key = st.text_input("DeepSeek API Key", type="password",
                                   value="")

        tavily_key = st.text_input("Tavily API Key", type="password",
                                 value="")

        # 高级配置
        st.subheader("高级配置")
        max_reflections = st.slider("反思次数", 1, 5, 2)
        max_search_results = st.slider("搜索结果数", 1, 10, 3)
        max_content_length = st.number_input("最大内容长度", 1000, 50000, 20000)

        # 模型选择
        llm_provider = st.selectbox("LLM提供商", ["deepseek", "openai"])

        if llm_provider == "deepseek":
            model_name = st.selectbox("DeepSeek模型", ["deepseek-chat"])
        else:
            model_name = st.selectbox("OpenAI模型", ["gpt-4o-mini", "gpt-4o"])
            openai_key = st.text_input("OpenAI API Key", type="password",
                                     value="")

    # 主界面
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("研究查询")
        query = st.text_area(
            "请输入您要研究的问题",
            placeholder="例如：2025年人工智能发展趋势",
            height=100
        )

        # 预设查询示例
        st.subheader("示例查询")
        example_queries = [
            "2025年人工智能发展趋势",
            "深度学习在医疗领域的应用",
            "区块链技术的最新发展",
            "可持续能源技术趋势",
            "量子计算的发展现状"
        ]

        selected_example = st.selectbox("选择示例查询", ["自定义"] + example_queries)
        if selected_example != "自定义":
            query = selected_example

    with col2:
        st.header("状态信息")
        # 使用 empty 容器以便在执行过程中更新状态信息
        status_container = st.empty()
        # 初始化显示状态信息
        update_status_info(status_container)

    # 执行按钮
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        start_research = st.button("开始研究", type="primary", use_container_width=True)

    # 如果研究已完成，显示结果（页面重新加载后也能显示）
    if st.session_state.get('research_completed', False) and 'agent' in st.session_state:
        agent = st.session_state.agent
        final_report = st.session_state.get('final_report', '')
        if final_report:
            display_results(agent, final_report)

    # 验证配置
    if start_research:
        # 清除之前的研究结果状态，避免显示旧结果
        if 'research_completed' in st.session_state:
            st.session_state.research_completed = False
        if 'download_timestamp' in st.session_state:
            del st.session_state.download_timestamp
        if 'download_key_base' in st.session_state:
            del st.session_state.download_key_base

        if not query.strip():
            st.error("请输入研究查询")
            return

        if not deepseek_key and llm_provider == "deepseek":
            st.error("请提供DeepSeek API Key")
            return

        if not tavily_key:
            st.error("请提供Tavily API Key")
            return

        if llm_provider == "openai" and not openai_key:
            st.error("请提供OpenAI API Key")
            return

        # 创建配置
        config = Config(
            deepseek_api_key=deepseek_key if llm_provider == "deepseek" else None,
            openai_api_key=openai_key if llm_provider == "openai" else None,
            tavily_api_key=tavily_key,
            default_llm_provider=llm_provider,
            deepseek_model=model_name if llm_provider == "deepseek" else "deepseek-chat",
            openai_model=model_name if llm_provider == "openai" else "gpt-4o-mini",
            max_reflections=max_reflections,
            max_search_results=max_search_results,
            max_content_length=max_content_length,
            output_dir="streamlit_reports"
        )

        # 执行研究（传入状态容器用于实时更新）
        execute_research(query, config, status_container)


def execute_research(query: str, config: Config, status_container=None):
    """执行研究"""
    try:
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 初始化Agent
        status_text.text("正在初始化Agent...")
        agent = DeepSearchAgent(config)
        st.session_state.agent = agent

        # 立即更新状态信息面板
        if status_container:
            update_status_info(status_container)

        progress_bar.progress(10)

        # 生成报告结构
        status_text.text("正在生成报告结构...")
        agent._generate_report_structure(query)

        # 更新状态信息（报告结构已生成，段落数已确定）
        if status_container:
            update_status_info(status_container)

        progress_bar.progress(20)

        # 处理段落
        total_paragraphs = len(agent.state.paragraphs)
        for i in range(total_paragraphs):
            status_text.text(f"正在处理段落 {i+1}/{total_paragraphs}: {agent.state.paragraphs[i].title}")

            # 初始搜索和总结
            agent._initial_search_and_summary(i)
            progress_value = 20 + (i + 0.5) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

            # 更新状态信息
            if status_container:
                update_status_info(status_container)

            # 反思循环
            agent._reflection_loop(i)
            agent.state.paragraphs[i].research.mark_completed()

            progress_value = 20 + (i + 1) / total_paragraphs * 60
            progress_bar.progress(int(progress_value))

            # 更新状态信息（段落处理完成）
            if status_container:
                update_status_info(status_container)

        # 生成最终报告
        status_text.text("正在生成最终报告...")
        final_report = agent._generate_final_report()
        progress_bar.progress(90)

        # 保存报告
        status_text.text("正在保存报告...")
        agent._save_report(final_report)
        progress_bar.progress(100)

        status_text.text("研究完成！")

        # 将结果保存到会话状态，避免重复生成下载按钮
        st.session_state.final_report = final_report
        st.session_state.research_completed = True
        # 设置下载时间戳，确保下载按钮使用稳定的key
        st.session_state.download_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # 显示结果
        display_results(agent, final_report)

    except Exception as e:
        st.error(f"研究过程中发生错误: {str(e)}")
        st.session_state.research_completed = False


def display_results(agent: DeepSearchAgent, final_report: str):
    """显示研究结果"""
    # 只在研究完成时显示结果
    if not st.session_state.get('research_completed', False):
        return

    # 从会话状态获取报告，避免重复创建下载按钮
    final_report = st.session_state.get('final_report', final_report)

    st.header("研究结果")

    # 结果标签页
    tab1, tab2, tab3 = st.tabs(["最终报告", "详细信息", "下载"])

    with tab1:
        st.markdown(final_report)

    with tab2:
        # 段落详情
        st.subheader("段落详情")
        for i, paragraph in enumerate(agent.state.paragraphs):
            with st.expander(f"段落 {i+1}: {paragraph.title}"):
                st.write("**预期内容:**", paragraph.content)
                st.write("**最终内容:**", paragraph.research.latest_summary[:300] + "..."
                        if len(paragraph.research.latest_summary) > 300
                        else paragraph.research.latest_summary)
                st.write("**搜索次数:**", paragraph.research.get_search_count())
                st.write("**反思次数:**", paragraph.research.reflection_iteration)

        # 搜索历史
        st.subheader("搜索历史")
        all_searches = []
        for paragraph in agent.state.paragraphs:
            all_searches.extend(paragraph.research.search_history)

        if all_searches:
            for i, search in enumerate(all_searches):
                with st.expander(f"搜索 {i+1}: {search.query}"):
                    st.write("**URL:**", search.url)
                    st.write("**标题:**", search.title)
                    st.write("**内容预览:**", search.content[:200] + "..." if len(search.content) > 200 else search.content)
                    if search.score:
                        st.write("**相关度评分:**", search.score)

    with tab3:
        # 下载选项
        st.subheader("下载报告")

        # 获取时间戳，如果没有则生成新的
        timestamp = st.session_state.get('download_timestamp', datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        if final_report:
            # 每次都重新生成下载数据，避免缓存问题
            col1, col2 = st.columns(2)
            
            # 生成唯一ID用于按钮key，确保唯一性
            unique_key = hashlib.md5(f"{timestamp}_{id(final_report)}".encode()).hexdigest()[:8]
            
            with col1:
                # Markdown报告下载
                try:
                    report_bytes = final_report.encode('utf-8')
                    st.download_button(
                        label="📄 下载Markdown报告",
                        data=report_bytes,
                        file_name=f"deep_search_report_{timestamp}.md",
                        mime="text/markdown",
                        key=f"new_dl_md_{unique_key}",
                        use_container_width=True
                    )
                except Exception as e:
                    st.warning("下载按钮暂时不可用")
                    if hasattr(agent, 'config'):
                        output_dir = getattr(agent.config, 'output_dir', 'streamlit_reports')
                        st.info(f"报告已保存到: {output_dir}/deep_search_report_*.md")
            
            with col2:
                # JSON状态下载
                try:
                    if 'agent' in st.session_state and hasattr(st.session_state.agent, 'state'):
                        state_json = agent.state.to_json()
                        if state_json:
                            state_bytes = state_json.encode('utf-8')
                            st.download_button(
                                label="📊 下载状态文件",
                                data=state_bytes,
                                file_name=f"deep_search_state_{timestamp}.json",
                                mime="application/json",
                                key=f"new_dl_json_{unique_key}",
                                use_container_width=True
                            )
                except Exception as e:
                    st.warning("状态文件下载暂时不可用")
            
            # 显示文件保存位置
            st.divider()
            if hasattr(agent, 'config'):
                output_dir = getattr(agent.config, 'output_dir', 'streamlit_reports')
                st.success(f"✅ 报告已保存到本地: `{output_dir}/`")
                st.info("💡 提示: 如果下载按钮不可用，可以在「历史报告」标签页中查看和下载")


if __name__ == "__main__":
    # 当直接使用 `python streamlit_app.py` 运行时，自动以 `streamlit run` 启动，避免缺失 ScriptRunContext 警告
    try:
        import streamlit.web.cli as stcli
        sys.argv = ["streamlit", "run", os.path.abspath(__file__)]
        sys.exit(stcli.main())
    except Exception:
        # 回退到裸运行（不会打开浏览器，可能出现 ScriptRunContext 提示）
        main()
