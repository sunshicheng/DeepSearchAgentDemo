"""
Deep Search Agent主类
整合所有模块，实现完整的深度搜索流程
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any

from deep_research.llms import DeepSeekLLM, OpenAILLM, BaseLLM
from deep_research.nodes import (
    ReportStructureNode,
    FirstSearchNode,
    ReflectionNode,
    FirstSummaryNode,
    ReflectionSummaryNode,
    ReportFormattingNode
)
from deep_research.state import State
from deep_research.tools import tavily_search
from deep_research.utils import Config, load_config, format_search_results_for_prompt, logger


class DeepSearchAgent:
    """Deep Search Agent主类"""

    def __init__(self, config: Optional[Config] = None):
        """
        初始化Deep Search Agent
        
        Args:
            config: 配置对象，如果不提供则自动加载
        """
        # 加载配置
        self.config = config or load_config()

        # 初始化LLM客户端
        self.llm_client = self._initialize_llm()

        # 初始化节点
        self._initialize_nodes()

        # 状态
        self.state = State()

        # 确保输出目录存在
        os.makedirs(self.config.output_dir, exist_ok=True)

        logger.info(f"Deep Search Agent 已初始化")
        logger.info(f"使用LLM: {self.llm_client.get_model_info()}")

    def _initialize_llm(self) -> BaseLLM:
        """初始化LLM客户端"""
        if self.config.default_llm_provider == "deepseek":
            return DeepSeekLLM(
                api_key=self.config.deepseek_api_key,
                model_name=self.config.deepseek_model
            )
        elif self.config.default_llm_provider == "openai":
            return OpenAILLM(
                api_key=self.config.openai_api_key,
                model_name=self.config.openai_model
            )
        else:
            raise ValueError(f"不支持的LLM提供商: {self.config.default_llm_provider}")

    def _initialize_nodes(self):
        """初始化处理节点"""
        self.first_search_node = FirstSearchNode(self.llm_client)
        self.reflection_node = ReflectionNode(self.llm_client)
        self.first_summary_node = FirstSummaryNode(self.llm_client)
        self.reflection_summary_node = ReflectionSummaryNode(self.llm_client)
        self.report_formatting_node = ReportFormattingNode(self.llm_client)

    def research(self, query: str, save_report: bool = True) -> str:
        """
        执行深度研究
        
        Args:
            query: 研究查询
            save_report: 是否保存报告到文件
            
        Returns:
            最终报告内容
        """
        print(f"\n{'=' * 60}")
        logger.info(f"开始深度研究: {query}")
        print(f"{'=' * 60}")

        try:
            # Step 1: 生成报告结构
            self._generate_report_structure(query)

            # Step 2: 处理每个段落
            self._process_paragraphs()

            # Step 3: 生成最终报告
            final_report = self._generate_final_report()

            # Step 4: 保存报告
            if save_report:
                self._save_report(final_report)

            print(f"\n{'=' * 60}")
            logger.info(f"深度研究完成！{final_report}")
            print(f"{'=' * 60}")

            return final_report

        except Exception as e:
            logger.error(f"研究过程中发生错误: {str(e)}")
            raise e

    def _generate_report_structure(self, query: str):
        """生成报告结构"""
        logger.info(f"\n[步骤 1] 生成报告结构...")

        # 创建报告结构节点
        report_structure_node = ReportStructureNode(self.llm_client, query)

        # 生成结构并更新状态
        self.state = report_structure_node.mutate_state(state=self.state)

        logger.info(f"报告结构已生成，共 {len(self.state.paragraphs)} 个段落:")
        for i, paragraph in enumerate(self.state.paragraphs, 1):
            logger.info(f"  {i}. {paragraph.title}")

    def _process_paragraphs(self):
        """处理所有段落"""
        total_paragraphs = len(self.state.paragraphs)

        for i in range(total_paragraphs):
            logger.info(f"\n[步骤 2.{i + 1}] 处理段落: {self.state.paragraphs[i].title}")
            print("-" * 50)

            # 初始搜索和总结
            self._initial_search_and_summary(i)

            # 反思循环
            self._reflection_loop(i)

            # 标记段落完成
            self.state.paragraphs[i].research.mark_completed()

            progress = (i + 1) / total_paragraphs * 100
            logger.info(f"段落处理完成 ({progress:.1f}%)")

    def _initial_search_and_summary(self, paragraph_index: int):
        """执行初始搜索和总结"""
        paragraph = self.state.paragraphs[paragraph_index]

        # 准备搜索输入
        search_input = {
            "title": paragraph.title,
            "content": paragraph.content
        }

        # 生成搜索查询
        logger.info("_initial_search_and_summary - 生成搜索查询...")
        search_output = self.first_search_node.run(search_input)
        search_query = search_output["search_query"]
        reasoning = search_output["reasoning"]

        logger.info(f"_initial_search_and_summary - 搜索查询: {search_query}")
        logger.info(f"_initial_search_and_summary - 推理: {reasoning}")

        # 执行搜索
        logger.info("_initial_search_and_summary - 执行网络搜索...")
        search_results = tavily_search(
            search_query,
            max_results=self.config.max_search_results,
            timeout=self.config.search_timeout,
            api_key=self.config.tavily_api_key
        )

        if search_results:
            logger.info(f"_initial_search_and_summary - 找到 {len(search_results)} 个搜索结果")
            for j, result in enumerate(search_results, 1):
                logger.info(f"    {j}. {result['title']}")
        else:
            logger.error("  - 未找到搜索结果")

        # 更新状态中的搜索历史
        paragraph.research.add_search_results(search_query, search_results)

        # 生成初始总结
        logger.info("_initial_search_and_summary - 生成初始总结...")
        summary_input = {
            "title": paragraph.title,
            "content": paragraph.content,
            "search_query": search_query,
            "search_results": format_search_results_for_prompt(
                search_results, self.config.max_content_length
            )
        }

        logger.info(f"_initial_search_and_summary - summary_input {summary_input}")

        # 更新状态
        self.state = self.first_summary_node.mutate_state(
            summary_input, self.state, paragraph_index
        )

        logger.info("_initial_search_and_summary- 初始总结完成")

    def _reflection_loop(self, paragraph_index: int):
        """执行反思循环"""
        paragraph = self.state.paragraphs[paragraph_index]

        for reflection_i in range(self.config.max_reflections):
            logger.info(f"_reflection_loop- 反思 {reflection_i + 1}/{self.config.max_reflections}...")

            # 准备反思输入
            reflection_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "paragraph_latest_state": paragraph.research.latest_summary
            }

            # 生成反思搜索查询
            reflection_output = self.reflection_node.run(reflection_input)
            search_query = reflection_output["search_query"]
            reasoning = reflection_output["reasoning"]

            logger.info(f"_reflection_loop 反思查询: {search_query}")
            logger.info(f"_reflection_loop 反思推理: {reasoning}")

            # 执行反思搜索
            search_results = tavily_search(
                search_query,
                max_results=self.config.max_search_results,
                timeout=self.config.search_timeout,
                api_key=self.config.tavily_api_key
            )

            if search_results:
                logger.info(f"_reflection_loop 找到 {len(search_results)} 个反思搜索结果")

            # 更新搜索历史
            paragraph.research.add_search_results(search_query, search_results)

            # 生成反思总结
            reflection_summary_input = {
                "title": paragraph.title,
                "content": paragraph.content,
                "search_query": search_query,
                "search_results": format_search_results_for_prompt(
                    search_results, self.config.max_content_length
                ),
                "paragraph_latest_state": paragraph.research.latest_summary
            }
            logger.info(f"_reflection_loop reflection_summary_input {reflection_summary_input}")

            # 更新状态
            self.state = self.reflection_summary_node.mutate_state(
                reflection_summary_input, self.state, paragraph_index
            )

            logger.info(f"_reflection_loop 反思 {reflection_i + 1} 完成")

    def _generate_final_report(self) -> str:
        """生成最终报告"""
        logger.info(f"\n[步骤 3] 生成最终报告...")

        # 准备报告数据
        report_data = []
        for paragraph in self.state.paragraphs:
            report_data.append({
                "title": paragraph.title,
                "paragraph_latest_state": paragraph.research.latest_summary
            })

        # 格式化报告
        try:
            final_report = self.report_formatting_node.run(report_data)
        except Exception as e:
            logger.error(f"_generate_final_report LLM格式化失败，使用备用方法: {str(e)}")
            final_report = self.report_formatting_node.format_report_manually(
                report_data, self.state.report_title
            )

        # 更新状态
        self.state.final_report = final_report
        self.state.mark_completed()

        logger.info("_generate_final_report 最终报告生成完成")
        logger.info(f"_generate_final_report 生成的最终报告\n {final_report}")
        return final_report

    def _save_report(self, report_content: str):
        """保存报告到文件"""
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        query_safe = "".join(c for c in self.state.query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        query_safe = query_safe.replace(' ', '_')[:30]

        filename = f"deep_search_report_{query_safe}_{timestamp}.md"
        filepath = os.path.join(self.config.output_dir, filename)

        # 保存报告
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"报告已保存到: {filepath}")

        # 保存状态（如果配置允许）
        if self.config.save_intermediate_states:
            state_filename = f"state_{query_safe}_{timestamp}.json"
            state_filepath = os.path.join(self.config.output_dir, state_filename)
            self.state.save_to_file(state_filepath)
            logger.info(f"状态已保存到: {state_filepath}")

    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        return self.state.get_progress_summary()

    def load_state(self, filepath: str):
        """从文件加载状态"""
        self.state = State.load_from_file(filepath)
        logger.info(f"状态已从 {filepath} 加载")

    def save_state(self, filepath: str):
        """保存状态到文件"""
        self.state.save_to_file(filepath)
        logger.info(f"状态已保存到 {filepath}")


def create_agent(config_file: Optional[str] = None) -> DeepSearchAgent:
    """
    创建Deep Search Agent实例的便捷函数
    
    Args:
        config_file: 配置文件路径
        
    Returns:
        DeepSearchAgent实例
    """
    config = load_config(config_file)
    return DeepSearchAgent(config)
