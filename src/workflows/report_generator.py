# -*- coding: utf-8 -*-
"""
报告生成器工作流 (支持多轮对话和可视化增强)

功能:
- 输入：用户给出一组搜索关键词
- 步骤 1: 调用 ResearcherAgent 搜索前 N 个项目
- 步骤 2: 遍历项目，调用 AnalystAgent 对每个项目进行深度分析
- 步骤 3: 将所有分析结果汇总成 Markdown 格式的简报
- 步骤 4 (新增): 支持用户追问，进行多轮对话
- 可视化增强：为 Star 数生成文本进度条

这是一个线性工作流，展示了多 Agent 协作的基本模式。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.conversation import ConversationManager
from src.agents.analyst_agent import AnalystAgent
from src.agents.researcher_agent import ResearcherAgent

logger = get_logger(__name__)


class ReportGenerator:
    """
    报告生成器工作流

    协调 ResearcherAgent 和 AnalystAgent，生成项目分析简报。

    Attributes:
        researcher: 研究员 Agent，负责搜索项目
        analyst: 分析师 Agent，负责深度分析项目
        config: 配置管理器
        results: 工作流执行结果
    """

    # 简报模板
    REPORT_TEMPLATE = """# GitHub 项目分析报告

**生成时间**: {timestamp}
**搜索关键词**: {query}
**分析项目数**: {project_count}

---

## 执行摘要

{executive_summary}

---

## 项目对比总览

| 排名 | 项目 | Stars | 语言 | 成熟度 | 推荐度 |
|------|------|-------|------|--------|--------|
{comparison_table}

---

## 项目详情

{project_details}

---

## 综合评估

{overall_assessment}

---

*报告由 GitHub Insight Agent 自动生成*
"""

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        researcher: Optional[ResearcherAgent] = None,
        analyst: Optional[AnalystAgent] = None,
        conversation_storage_path: Optional[str] = None,
    ):
        """
        初始化报告生成器

        Args:
            config: 配置管理器
            researcher: 研究员 Agent（可选，不传则自动创建）
            analyst: 分析师 Agent（可选，不传则自动创建）
            conversation_storage_path: 对话历史存储路径（可选）
        """
        self.config = config or ConfigManager()
        self.researcher = researcher or ResearcherAgent(config=self.config)
        self.analyst = analyst or AnalystAgent(config=self.config)
        self.results: Dict[str, Any] = {}

        # 对话管理器（支持多轮对话）
        self.conversation = ConversationManager(
            max_turns=5,
            storage_path=conversation_storage_path,
            auto_save=False,
        )

        # 当前分析的项目列表（用于追问上下文）
        self._current_projects: List[Dict[str, Any]] = []

        # Star 进度条基准值（默认以最高项目为 100%）
        self._star_bar_max: int = 0

        logger.info("ReportGenerator initialized (with conversation support)")

    def execute(
        self,
        query: str,
        num_projects: int = 3,
        sort: str = "stars",
    ) -> str:
        """
        执行报告生成工作流

        Args:
            query: 搜索关键词
            num_projects: 分析的项目数量
            sort: 排序方式 (stars/forks/updated)

        Returns:
            Markdown 格式的报告
        """
        logger.info(f"Starting report generation: '{query}' (num_projects={num_projects})")

        # 清空之前的对话和项目（开始新的会话）
        self.clear_conversation()

        # 步骤 1: 搜索项目
        logger.info("[Step 1/3] Searching for projects...")
        search_results = self._search_projects(query, num_projects, sort)

        if not search_results:
            return self._generate_empty_report(query)

        # 步骤 2: 深度分析每个项目
        logger.info("[Step 2/3] Analyzing projects...")
        analysis_results = self._analyze_projects(search_results)

        # 保存当前分析的项目（用于追问上下文）
        self._current_projects = analysis_results

        # 步骤 3: 生成汇总报告
        logger.info("[Step 3/3] Generating report...")
        report = self._generate_report(query, search_results, analysis_results)

        self.results = {
            "query": query,
            "search_results": search_results,
            "analysis_results": analysis_results,
            "report": report,
        }

        # 记录到对话历史
        self.conversation.add_user_message(f"分析项目：{query}")
        self.conversation.add_assistant_message(
            f"已分析 {len(analysis_results)} 个项目，生成了详细报告。",
            metadata={"type": "report_generated", "project_count": len(analysis_results)},
        )

        logger.info("Report generation completed")
        return report

    def _search_projects(
        self,
        query: str,
        num_projects: int,
        sort: str,
    ) -> List[Dict[str, Any]]:
        """
        搜索项目

        Args:
            query: 搜索关键词
            num_projects: 项目数量
            sort: 排序方式

        Returns:
            搜索结果列表
        """
        try:
            repos = self.researcher.search_and_analyze(
                query=query,
                sort=sort,
                per_page=num_projects,
            )

            # 转换为字典列表
            results = []
            for repo in repos.get("repositories", [])[:num_projects]:
                results.append({
                    "full_name": repo["full_name"],
                    "html_url": repo["html_url"],
                    "stars": repo["stars"],
                    "language": repo["language"],
                    "description": repo["description"],
                    "owner": repo["full_name"].split("/")[0],
                    "repo": repo["full_name"].split("/")[1],
                })

            logger.info(f"Found {len(results)} projects")
            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _analyze_projects(
        self,
        projects: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        分析项目列表

        Args:
            projects: 项目列表

        Returns:
            分析结果列表
        """
        results = []
        for i, project in enumerate(projects, 1):
            logger.info(f"[{i}/{len(projects)}] Analyzing: {project['full_name']}")

            try:
                analysis = self.analyst.analyze_project(
                    owner=project["owner"],
                    repo=project["repo"],
                )
                results.append(analysis)
            except Exception as e:
                logger.error(f"Failed to analyze {project['full_name']}: {e}")
                results.append({
                    "project": project["full_name"],
                    "error": str(e),
                    "analysis": None,
                })

        return results

    def _generate_report(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        analysis_results: List[Dict[str, Any]],
    ) -> str:
        """
        生成 Markdown 格式报告

        Args:
            query: 搜索关键词
            search_results: 搜索结果
            analysis_results: 分析结果

        Returns:
            Markdown 报告字符串
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 生成执行摘要
        executive_summary = self._generate_executive_summary(
            search_results, analysis_results
        )

        # 生成项目对比表格
        comparison_table = self._generate_comparison_table(analysis_results)

        # 生成项目详情
        project_details = self._generate_project_details(analysis_results)

        # 生成综合评估
        overall_assessment = self._generate_overall_assessment(analysis_results)

        # 填充模板
        report = self.REPORT_TEMPLATE.format(
            timestamp=timestamp,
            query=query,
            project_count=len(search_results),
            executive_summary=executive_summary,
            comparison_table=comparison_table,
            project_details=project_details,
            overall_assessment=overall_assessment,
        )

        return report

    def _generate_executive_summary(
        self,
        search_results: List[Dict[str, Any]],
        analysis_results: List[Dict[str, Any]],
    ) -> str:
        """生成执行摘要"""
        if not analysis_results:
            return "未能获取到有效的分析结果。"

        # 统计成功分析的项目数
        successful = sum(
            1 for r in analysis_results if r.get("analysis") and not r.get("error")
        )

        # 计算总 stars
        total_stars = sum(r.get("stars", 0) for r in search_results)
        avg_stars = total_stars // len(search_results) if search_results else 0
        max_stars = max((r.get("stars", 0) for r in search_results), default=0)
        top_project = next(
            (r.get("project", r.get("full_name", ""))
             for r in search_results if r.get("stars") == max_stars),
            ""
        )

        # 提取主要编程语言
        languages = {}
        for r in search_results:
            lang = r.get("language", "Unknown")
            if lang and lang != "Unknown":
                languages[lang] = languages.get(lang, 0) + 1

        # 成熟度统计
        maturity_counts = {}
        for r in analysis_results:
            analysis = r.get("analysis", {})
            if analysis:
                mat = analysis.get("maturity_assessment", "unknown")
                if mat and mat != "unknown":
                    maturity_counts[mat] = maturity_counts.get(mat, 0) + 1

        summary_lines = [
            f"本次搜索共找到 **{len(search_results)}** 个项目，成功深度分析 **{successful}** 个。",
            f"这些项目的总 Star 数超过 **{total_stars:,}** 颗，平均 **{avg_stars:,}** 颗。",
        ]

        if top_project:
            summary_lines.append(f"🏆 最受关注项目：**{top_project}**（⭐ {max_stars:,}）")

        # 语言分布
        if languages:
            lang_str = ", ".join(
                f"{lang} ({count})" for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)
            )
            summary_lines.append(f"主要编程语言：{lang_str}")

        # 成熟度概览
        if maturity_counts:
            mat_labels = {
                "mature": "🔵成熟",
                "stable": "🟢稳定",
                "beta": "🟠Beta",
                "early": "🟡早期",
            }
            mat_str = ", ".join(
                f"{mat_labels.get(k, k)} ({v})" for k, v in maturity_counts.items()
            )
            summary_lines.append(f"成熟度分布：{mat_str}")

        summary_lines.extend([
            "",
            "以下是各项目的详细分析：",
        ])

        return "\n".join(summary_lines)

    def _generate_comparison_table(
        self,
        analysis_results: List[Dict[str, Any]],
    ) -> str:
        """生成项目对比表格"""
        maturity_map = {
            "early": "🟡 Early",
            "beta": "🟠 Beta",
            "stable": "🟢 Stable",
            "mature": "🔵 Mature",
        }

        rows = []
        for i, result in enumerate(analysis_results, 1):
            project = result.get("project", "Unknown")
            stars = result.get("stars", 0)
            language = result.get("language", "N/A")
            analysis = result.get("analysis", {})

            maturity = analysis.get("maturity_assessment", "unknown")
            maturity_display = maturity_map.get(maturity, f"? {maturity}")

            rec = analysis.get("recommendation", "")
            if isinstance(rec, str):
                rec_lower = rec.lower()
                if "recommend" in rec_lower:
                    rec_display = "✅ 推荐"
                elif "avoid" in rec_lower:
                    rec_display = "❌ 谨慎"
                else:
                    rec_display = "⚠️ 可考虑"
            else:
                rec_display = "⚠️ 可考虑"

            rows.append(
                f"| {i} | {project} | ⭐ {stars:,} | {language} | {maturity_display} | {rec_display} |"
            )

        return "\n".join(rows)

    def _generate_project_details(
        self,
        analysis_results: List[Dict[str, Any]],
    ) -> str:
        """生成项目详情部分（带 Star 进度条可视化）"""
        details = []

        # 计算 Star 进度条基准值（最高 Star 数为 100%）
        max_stars = max((r.get("stars", 0) for r in analysis_results), default=1)
        self._star_bar_max = max_stars

        for i, result in enumerate(analysis_results, 1):
            project_name = result.get("project", "Unknown")
            url = result.get("url", "")
            stars = result.get("stars", 0)
            language = result.get("language", "N/A")
            analysis = result.get("analysis", {})

            if result.get("error"):
                details.append(f"### {i}. {project_name}\n⚠️ 分析失败：{result['error']}\n")
                continue

            # 提取分析结果
            core_function = analysis.get("core_function", "Unknown")
            tech_stack = analysis.get("tech_stack", {})
            pain_points = analysis.get("pain_points_solved", [])
            unique_value = analysis.get("unique_value", "")
            recommendation = analysis.get("recommendation", "Unknown")
            competitive = analysis.get("competitive_analysis", "")

            # 构建技术栈文本
            frameworks = tech_stack.get("frameworks", [])
            dependencies = tech_stack.get("key_dependencies", [])
            lang = tech_stack.get("language", "N/A")

            # 生成 Star 进度条
            star_bar = self._generate_star_bar(stars, max_stars)

            # 构建项目详情
            detail_lines = [
                f"### {i}. [{project_name}]({url})",
                "",
                "| 指标 | 值 |",
                "|------|-----|",
                f"| Stars | {star_bar} ⭐ {stars:,} |",
                f"| 语言 | {language} |",
                "",
                "#### 核心功能",
                core_function,
                "",
                "#### 技术栈",
                f"- **语言**: {lang}",
            ]

            if frameworks:
                detail_lines.append(f"- **框架**: {', '.join(frameworks)}")
            if dependencies:
                detail_lines.append(f"- **关键依赖**: {', '.join(dependencies)}")

            detail_lines.extend([
                "",
                "#### 解决的痛点",
                self._format_list(pain_points),
            ])

            if unique_value:
                detail_lines.extend([
                    "",
                    "#### 独特价值",
                    unique_value,
                ])

            if competitive:
                detail_lines.extend([
                    "",
                    "#### 竞品对比",
                    competitive,
                ])

            detail_lines.extend([
                "",
                "#### 推荐意见",
                recommendation,
                "",
                "---",
            ])

            detail = "\n".join(detail_lines)
            details.append(detail)

        return "\n".join(details)

    def _generate_star_bar(self, stars: int, max_stars: int, bar_length: int = 20) -> str:
        """
        生成 Star 文本进度条

        Args:
            stars: 当前 Star 数
            max_stars: 最大 Star 数（作为 100% 基准）
            bar_length: 进度条长度

        Returns:
            进度条字符串，例如：[██████████----------] 60%
        """
        if max_stars <= 0 or stars <= 0:
            return f"[{'-' * bar_length}] 0%"

        # 计算百分比
        percentage = min(stars / max_stars, 1.0)
        percentage_display = int(percentage * 100)

        # 计算填充和空白部分
        filled_length = int(bar_length * percentage)
        empty_length = bar_length - filled_length

        # 生成进度条
        bar = "█" * filled_length + "-" * empty_length

        return f"[{bar}] {percentage_display}%"

    def _generate_overall_assessment(
        self,
        analysis_results: List[Dict[str, Any]],
    ) -> str:
        """生成综合评估部分"""
        # 提取所有推荐意见
        recommendations = []
        for result in analysis_results:
            analysis = result.get("analysis")
            if analysis and isinstance(analysis, dict):
                rec = analysis.get("recommendation", "")
                if rec:
                    recommendations.append(rec)

        # 提取成熟度评估
        maturities = []
        for result in analysis_results:
            analysis = result.get("analysis")
            if analysis and isinstance(analysis, dict):
                mat = analysis.get("maturity_assessment", "")
                if mat:
                    maturities.append(mat)

        assessment_lines = [
            "基于以上分析，给出以下综合评估：",
            "",
            "#### 推荐统计",
        ]

        # 统计推荐类型
        rec_counts = {"recommend": 0, "consider": 0, "avoid": 0}
        for rec in recommendations:
            rec_lower = rec.lower()
            if "recommend" in rec_lower:
                rec_counts["recommend"] += 1
            elif "avoid" in rec_lower:
                rec_counts["avoid"] += 1
            else:
                rec_counts["consider"] += 1

        assessment_lines.extend([
            f"- 🟢 推荐 (Recommend): {rec_counts['recommend']} 个",
            f"- 🟡 可考虑 (Consider): {rec_counts['consider']} 个",
            f"- 🔴 谨慎 (Avoid): {rec_counts['avoid']} 个",
        ])

        # 成熟度分布
        if maturities:
            mat_counts = {}
            for mat in maturities:
                mat_lower = mat.lower() if isinstance(mat, str) else str(mat)
                mat_counts[mat_lower] = mat_counts.get(mat_lower, 0) + 1
            mat_display = {
                "mature": "🔵 成熟 (Mature)",
                "stable": "🟢 稳定 (Stable)",
                "beta": "🟠 Beta",
                "early": "🟡 早期 (Early)",
            }
            assessment_lines.extend([
                "",
                "#### 成熟度分布",
            ])
            for mat_key, mat_label in mat_display.items():
                count = mat_counts.get(mat_key, 0)
                if count > 0:
                    assessment_lines.append(f"- {mat_label}: {count} 个")

        # 按 Star 排名
        assessment_lines.extend([
            "",
            "#### 综合排名",
            "（综合 Star 数、成熟度、推荐度）",
            "",
        ])

        for i, result in enumerate(analysis_results, 1):
            project = result.get("project", "Unknown")
            stars = result.get("stars", 0)
            analysis = result.get("analysis", {})
            maturity = analysis.get("maturity_assessment", "unknown")
            rec = analysis.get("recommendation", "")
            rec_label = "✅" if "recommend" in rec.lower() else ("❌" if "avoid" in rec.lower() else "⚠️")
            assessment_lines.append(
                f"{i}. **{project}** - ⭐ {stars:,} | {maturity} | {rec_label}"
            )

        # 技术栈分析
        languages = {}
        frameworks = {}
        for result in analysis_results:
            analysis = result.get("analysis", {})
            tech = analysis.get("tech_stack", {})
            if tech:
                lang = tech.get("language", "")
                if lang and lang != "N/A":
                    languages[lang] = languages.get(lang, 0) + 1
                for fw in tech.get("frameworks", []):
                    frameworks[fw] = frameworks.get(fw, 0) + 1

        if languages:
            assessment_lines.extend([
                "",
                "#### 技术生态",
                "",
                "**编程语言分布**:",
            ])
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                assessment_lines.append(f"- {lang}: {count} 个项目")

        if frameworks:
            assessment_lines.append("")
            assessment_lines.append("**常用框架**:")
            for fw, count in sorted(frameworks.items(), key=lambda x: x[1], reverse=True)[:5]:
                assessment_lines.append(f"- {fw} ({count})")

        assessment_lines.extend([
            "",
            "#### 整体建议",
            "根据项目 Star 数量、技术栈成熟度、文档完整性等因素综合评估，",
            "建议优先关注高 Star 且文档完善的项目。",
        ])

        return "\n".join(assessment_lines)

    def _generate_empty_report(self, query: str) -> str:
        """生成空报告（搜索失败时）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return f"""# GitHub 项目分析报告

**生成时间**: {timestamp}
**搜索关键词**: {query}

---

## 执行摘要

未能找到匹配的项目。请尝试：
1. 更换搜索关键词
2. 检查 GitHub Token 配置
3. 确认网络连接正常

---

*报告由 GitHub Insight Agent 自动生成*
"""

    @staticmethod
    def _format_list(items: List[str], indent: str = "- ") -> str:
        """格式化列表为字符串"""
        if not items:
            return "暂无相关信息"
        return "\n".join(f"{indent}{item}" for item in items)

    def handle_followup(
        self,
        user_query: str,
    ) -> str:
        """
        处理用户追问（多轮对话支持）

        Args:
            user_query: 用户追问

        Returns:
            助手回复
        """
        logger.info(f"Handling followup: {user_query}")

        # 记录用户问题
        self.conversation.add_user_message(user_query)

        # 构建上下文
        context = self._build_followup_context()

        # 调用 LLM 生成回答
        response = self._answer_followup(user_query, context)

        # 记录助手回答
        self.conversation.add_assistant_message(response)

        return response

    def _build_followup_context(self) -> str:
        """
        构建追问上下文

        Returns:
            格式化的上下文字符串
        """
        context_parts = []

        # 添加当前分析的项目信息
        if self._current_projects:
            context_parts.append("## 当前分析的项目：")
            for proj in self._current_projects:
                context_parts.append(
                    f"- {proj.get('project', 'Unknown')}: "
                    f"{proj.get('analysis', {}).get('core_function', 'N/A')}"
                )

        # 添加对话历史（如果有）
        conversation_history = self.conversation.get_context_for_prompt()
        if conversation_history:
            context_parts.append("\n## 对话历史：")
            context_parts.append(conversation_history)

        return "\n".join(context_parts)

    def _answer_followup(
        self,
        user_query: str,
        context: str,
    ) -> str:
        """
        调用 LLM 回答追问

        Args:
            user_query: 用户问题
            context: 上下文信息

        Returns:
            助手回答
        """
        try:
            from dashscope import Generation
            import dashscope

            api_key = self.config.dashscope_api_key
            if api_key:
                dashscope.api_key = api_key

            prompt = f"""你是一个专业的 GitHub 项目分析助手。请根据以下上下文回答用户的问题。

{context}

## 用户问题
{user_query}

请给出简洁、专业的回答。如果上下文中没有相关信息，请如实告知。"""

            response = Generation.call(
                model="qwen-max",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.model_max_tokens,
                temperature=0.7,  # 稍高温度，让回答更有创造性
            )

            if response.status_code == 200:
                content = response.output.get("text", "")
                logger.info(f"Followup answer generated: {len(content)} chars")

                # 记录 ReAct 思考过程（可选）
                self.conversation.add_assistant_message(
                    content,
                    metadata={"type": "followup_response"},
                )

                return content
            else:
                logger.error(f"LLM API error: {response.message}")
                return f"抱歉，生成回答时出错：{response.message}"

        except Exception as e:
            logger.error(f"Failed to generate followup answer: {e}")
            return f"抱歉，处理您的问题时出错：{e}"

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取对话历史"""
        return self.conversation.get_full_history()

    def export_conversation(self, output_path: str) -> bool:
        """导出对话记录"""
        return self.conversation.export_markdown(output_path)

    def clear_conversation(self) -> None:
        """清空对话历史"""
        self.conversation.clear_history()
        self._current_projects.clear()
        logger.info("Conversation cleared")

    def get_results(self) -> Dict[str, Any]:
        """获取工作流执行结果"""
        return self.results

    def save_report(self, output_path: str) -> bool:
        """
        保存报告到文件

        Args:
            output_path: 输出文件路径

        Returns:
            是否成功
        """
        if not self.results.get("report"):
            logger.warning("No report to save")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(self.results["report"])
            logger.info(f"Report saved to: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return False
