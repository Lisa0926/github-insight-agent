# -*- coding: utf-8 -*-
"""
Agent orchestration pipeline (based on AgentScope SequentialPipeline)

Features:
- Use AgentScope SequentialPipeline to orchestrate search-to-analysis workflow
- Delegate ReportGenerator for report formatting
- Maintain compatible interface with CLI
"""

from typing import Any, Dict, List, Optional

from agentscope.pipeline import SequentialPipeline

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.agents.researcher_agent import ResearcherAgent
from src.agents.analyst_agent import AnalystAgent
from src.workflows.report_generator import ReportGenerator

# Import AgentScope tracing
try:
    from agentscope.tracing import trace
except ImportError:
    def trace(name=None):
        def decorator(func):
            return func
        return decorator

logger = get_logger(__name__)


class AgentPipeline:
    """
    Orchestrate GIA workflow using AgentScope SequentialPipeline

    Orchestration flow:
        CLI → AgentPipeline.execute()
            ├── SequentialPipeline([researcher]) → search
            ├── analyst.analyze_project() x N     → analyze
            └── ReportGenerator._generate_report() → format

    Attributes:
        researcher: Researcher Agent
        analyst: Analyst Agent
        config: Configuration manager
        _search_pipeline: AgentScope search orchestration pipeline
        _report_gen: Report formatting engine (delegated)
    """

    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        researcher: Optional[ResearcherAgent] = None,
        analyst: Optional[AnalystAgent] = None,
        conversation_storage_path: Optional[str] = None,
    ):
        """
        Initialize the Agent orchestration pipeline

        Args:
            config: Configuration manager
            researcher: Researcher Agent (optional)
            analyst: Analyst Agent (optional)
            conversation_storage_path: Conversation history storage path (optional)
        """
        self.config = config or ConfigManager()
        self.researcher = researcher or ResearcherAgent(config=self.config)
        self.analyst = analyst or AnalystAgent(config=self.config)

        # AgentScope orchestration: search pipeline
        self._search_pipeline = SequentialPipeline(agents=[self.researcher])

        # Delegate to ReportGenerator for report formatting
        self._report_gen = ReportGenerator(
            config=self.config,
            researcher=self.researcher,
            analyst=self.analyst,
            conversation_storage_path=conversation_storage_path,
        )

        logger.info("AgentPipeline initialized with SequentialPipeline")

    @property
    def _current_projects(self) -> List[Dict[str, Any]]:
        """Expose current project list to CLI (delegated to internal ReportGenerator)"""
        return self._report_gen._current_projects

    @trace(name="pipeline.execute")
    def execute(
        self,
        query: str,
        num_projects: int = 3,
        sort: str = "stars",
    ) -> str:
        """
        Execute the report generation workflow

        Args:
            query: Search keyword
            num_projects: Number of projects to analyze
            sort: Sort method (stars/forks/updated)

        Returns:
            Report in Markdown format
        """
        logger.info(f"AgentPipeline executing: '{query}' (num_projects={num_projects})")

        # Clear previous conversation and projects
        self.clear_conversation()

        # Step 1: Search projects via SequentialPipeline
        logger.info("[Step 1/3] Searching via SequentialPipeline...")
        search_results = self._search_via_pipeline(query, num_projects, sort)

        if not search_results:
            return self._report_gen._generate_empty_report(query)

        # Step 2: In-depth analysis of each project
        logger.info("[Step 2/3] Analyzing projects...")
        analysis_results = self._analyze_projects(search_results)

        # Save current analyzed projects (used for follow-up context)
        self._report_gen._current_projects = analysis_results

        # Step 3: Generate summary report (delegated to ReportGenerator)
        logger.info("[Step 3/3] Generating report...")
        report = self._report_gen._generate_report(query, search_results, analysis_results)

        self.results = {
            "query": query,
            "search_results": search_results,
            "analysis_results": analysis_results,
            "report": report,
        }

        # Record to conversation history
        self._report_gen.conversation.add_user_message(f"分析项目：{query}")
        self._report_gen.conversation.add_assistant_message(
            f"已分析 {len(analysis_results)} 个项目，生成了详细报告。",
            metadata={"type": "report_generated", "project_count": len(analysis_results)},
        )

        logger.info("AgentPipeline execution completed")
        return report

    def _search_via_pipeline(
        self,
        query: str,
        num_projects: int,
        sort: str,
    ) -> List[Dict[str, Any]]:
        """
        Execute search via AgentScope SequentialPipeline

        Args:
            query: Search keyword
            num_projects: Number of projects
            sort: Sort method

        Returns:
            List of search results
        """
        from agentscope.message import Msg

        # Trigger researcher.reply() via SequentialPipeline
        search_msg = Msg(name="user", content=query, role="user")
        self._search_pipeline(search_msg)

        # Get results from researcher.search_and_analyze()
        repos_result = self.researcher.search_and_analyze(
            query=query,
            sort=sort,
            per_page=num_projects,
        )

        results = []
        for repo in repos_result.get("repositories", [])[:num_projects]:
            full_name = repo["full_name"]
            results.append({
                "full_name": full_name,
                "html_url": repo["html_url"],
                "stars": repo["stars"],
                "language": repo["language"],
                "description": repo["description"],
                "owner": full_name.split("/")[0],
                "repo": full_name.split("/")[1],
            })

        logger.info(f"Pipeline search found {len(results)} projects")
        return results

    def _analyze_projects(
        self,
        projects: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Analyze a list of projects"""
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

    @trace(name="pipeline.handle_followup")
    def handle_followup(self, user_query: str) -> str:
        """Handle user follow-up questions"""
        return self._report_gen.handle_followup(user_query)

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self._report_gen.clear_conversation()

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self._report_gen.get_conversation_history()

    def export_conversation(self, output_path: str) -> bool:
        """Export conversation records"""
        return self._report_gen.export_conversation(output_path)

    def get_results(self) -> Dict[str, Any]:
        """Get workflow execution results"""
        return getattr(self, "results", {})

    # ---- Feedback integration (delegated to ReportGenerator) ----

    def rate_report(self, rating: str, reason: str = "") -> bool:
        """Rate the last generated report (delegated to internal ReportGenerator)"""
        return self._report_gen.rate_report(rating=rating, reason=reason)

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get aggregate feedback statistics."""
        return self._report_gen.get_feedback_stats()

    def get_recent_feedback(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent feedback entries."""
        return self._report_gen.get_recent_feedback(limit=limit)

    def get_north_star_metric(self) -> Dict[str, Any]:
        """Return north-star metric: overall positive feedback rate."""
        return self._report_gen.get_north_star_metric()

    def get_feedback_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return daily feedback trends for the last N days."""
        return self._report_gen.get_feedback_trends(days=days)

    def get_trend_summary(self) -> str:
        """Return human-readable trend summary."""
        return self._report_gen.get_trend_summary()

    def get_report_stats(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent feedback entries with derived metrics."""
        return self._report_gen.get_report_stats(limit=limit)

    def save_report(self, output_path: str) -> bool:
        """Save report to file"""
        results = self.get_results()
        if not results.get("report"):
            logger.warning("No report to save")
            return False

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(results["report"])
            logger.info(f"Report saved to: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return False
