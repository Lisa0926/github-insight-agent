# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - Enhanced CLI Entry Point

Features:
- Colored friendly output
- Command auto-completion
- Progress bar display
- Structured report display
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cli.cli_renderer import renderer  # noqa: E402
from src.cli.interactive_cli import cli  # noqa: E402
from src.cli.natural_language_parser import NaturalLanguageParser, IntentType  # noqa: E402
from src.core.config_manager import ConfigManager  # noqa: E402
from src.workflows.agent_pipeline import AgentPipeline  # noqa: E402


def print_welcome():
    """Print welcome message"""
    renderer.print_banner()

    commands = {
        "/analyze <owner/repo>": "分析指定 GitHub 项目",
        "/search <关键词>": "搜索 GitHub 项目",
        "/report <关键词>": "生成详细分析报告",
        "/pr": "审查 Pull Request (粘贴 diff)",
        "/scan <文件>": "安全扫描代码",
        "/history": "显示对话历史",
        "/clear": "清空对话",
        "/export <路径>": "导出对话记录",
        "/help": "显示帮助",
        "/quit": "退出程序",
    }
    renderer.print_help(commands)

    # Natural language hint
    renderer.print_info(
        "💡 支持自然语言输入，例如：\n"
        "  • '为我搜索最近一周内 star 最高的 3 个 Python 项目'\n"
        "  • '分析 microsoft/TypeScript'\n"
        "  • '找一些 Rust web framework'\n"
        "  • '前 5 个最活跃的 AI 框架'\n\n"
        "🔧 快捷操作：\n"
        "  • Tab 补全：输入 / 后按 Tab 可补全命令\n"
        "  • ↑↓ 键：翻阅历史命令\n"
        "  • Ctrl+Q：退出程序"
    )


def check_environment():
    """Check environment configuration"""
    config = ConfigManager()

    has_api_key = bool(config.dashscope_api_key)

    stats = {
        "配置文件": "✅" if config.env_loaded else "⚠️ 未加载",
        "DashScope API Key": "✅" if has_api_key else "❌ 未设置",
        "模型": config.dashscope_model_name or "未设置",
        "日志级别": config.log_level,
        "调试模式": "开启" if config.debug_mode else "关闭",
    }

    renderer.print_stats(stats, title="环境状态")

    if not config.env_loaded:
        renderer.print_warning("未检测到 .env 文件，部分功能可能不可用")
        renderer.print_info("复制 .env.sample 为 .env 并配置 API Key")

    if not has_api_key:
        renderer.print_warning("DashScope API Key 未配置（分析报告功能需要有效的 API Key）")
        renderer.print_info("请检查 ~/.env 中的 GIA_DASHSCOPE_API_KEY 变量")

    # Verify if the API Key is valid (using the same DashScopeWrapper as GIA)
    if has_api_key:
        try:
            from src.core.dashscope_wrapper import DashScopeWrapper
            wrapper = DashScopeWrapper(
                model_name=config.dashscope_model_name,
                api_key=config.dashscope_api_key,
                base_url=config.dashscope_base_url,
            )
            resp = wrapper(messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hi"},
            ], max_tokens=5)
            content = resp.get("content", "")
            if content and not content.startswith("Error"):
                renderer.print_success("DashScope API Key 验证通过")
            else:
                renderer.print_warning(f"DashScope API Key 验证失败: {content}")
        except Exception as e:
            renderer.print_warning(f"API Key 验证失败: {e}")
            renderer.print_info(f"模型: {config.dashscope_model_name}")
            renderer.print_info(f"端点: {config.dashscope_base_url}")


def run_interactive_mode():  # noqa: C901
    """Run interactive mode"""
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    config = ConfigManager()
    nl_parser = NaturalLanguageParser()

    # Set up Studio configuration
    if config.agentscope_enable_studio:
        set_researcher_studio(config.agentscope_studio_url, config.agentscope_run_name)
        set_analyst_studio(config.agentscope_studio_url, config.agentscope_run_name)
        renderer.print_info(f"Studio 已启用 (run_id: {config.agentscope_run_name})")

    # Initialize report generator
    report_gen = AgentPipeline()

    while True:
        try:
            user_input = cli.get_input()

            if not user_input:
                continue

            if user_input.startswith("/"):
                command_parts = user_input.split(maxsplit=1)
                command = command_parts[0].lower()
                args = command_parts[1] if len(command_parts) > 1 else ""

                if command in ["/quit", "/exit"]:
                    renderer.print_success("再见！")
                    break

                elif command == "/help":
                    commands = {
                        "/analyze <owner/repo>": "分析指定 GitHub 项目",
                        "/search <关键词>": "搜索 GitHub 项目",
                        "/report <关键词>": "生成详细分析报告",
                        "/pr": "审查 Pull Request (粘贴 diff)",
                        "/scan <文件>": "安全扫描代码",
                        "/history": "显示对话历史",
                        "/clear": "清空对话",
                        "/export <路径>": "导出对话记录",
                        "/config": "显示配置",
                        "/quit": "退出程序",
                    }
                    renderer.print_help(commands)

                elif command == "/analyze":
                    if not args:
                        renderer.print_error("用法：/analyze <owner/repo>", "例如：/analyze iii-hq/iii")
                        continue

                    if "/" not in args:
                        renderer.print_error("请输入完整的项目名", "格式：owner/repo")
                        continue

                    owner, repo = args.split("/", 1)

                    with renderer.create_progress("分析项目中..."):  # noqa: F841
                        result = report_gen.analyst.analyze_project(owner, repo)

                    if result.get("error"):
                        renderer.print_error("分析失败", result["error"])
                    else:
                        analysis = result.get("analysis", {})
                        renderer.print_panel(
                            "📊 分析结果",
                            f"核心功能：{analysis.get('core_function', 'N/A')}\n"
                            f"技术栈：{analysis.get('tech_stack', {}).get('language', 'N/A')}\n"
                            f"推荐意见：{analysis.get('recommendation', 'N/A')}",
                            style="green"
                        )

                elif command == "/search":
                    if not args:
                        renderer.print_error("用法：/search <关键词>", "例如：/search Python web framework")
                        continue

                    with renderer.create_progress(f"搜索：{args}"):  # noqa: F841
                        search_result = report_gen.researcher.search_and_analyze(query=args, sort="stars", per_page=5)

                    repos = search_result.get("repositories", [])
                    if repos:
                        renderer.print_info(f"找到 {len(repos)} 个项目")
                        rows = []
                        for i, repo in enumerate(repos[:5], 1):
                            rows.append([
                                str(i),
                                repo["full_name"],
                                f"⭐ {repo['stars']:,}",
                                repo.get("language", ""),
                            ])
                        renderer.print_table("搜索结果", ["#", "项目", "Stars", "语言"], rows)
                    else:
                        renderer.print_warning("未找到相关项目")

                elif command == "/report":
                    query = args if args else "Rust AI framework"
                    renderer.print_loading(f"生成报告：{query}")
                    # TODO: Implement report generation workflow
                    renderer.print_success("报告生成中...（功能开发中）")

                elif command == "/history":
                    history = report_gen.get_conversation_history()
                    if history:
                        renderer.print_info(f"对话历史 ({len(history)} 条)")
                        for msg in history[-5:]:
                            role = msg["role"]
                            content = msg["content"][:80] + "..." if len(msg["content"]) > 80 else msg["content"]
                            renderer.print(f"  [{role}] {content}")
                    else:
                        renderer.print_info("暂无对话历史")

                elif command == "/clear":
                    report_gen.clear_conversation()
                    renderer.print_success("对话历史已清空")

                elif command == "/export":
                    path = args if args else "reports/conversation.md"
                    # TODO: Implement export functionality
                    renderer.print_success(f"对话已导出到：{path}（功能开发中）")

                elif command == "/config":
                    stats = {
                        "模型": config.dashscope_model_name or "未设置",
                        "API Key": "已配置" if config.dashscope_api_key else "未配置",
                        "调试模式": "开启" if config.debug_mode else "关闭",
                        "Studio": "开启" if config.agentscope_enable_studio else "关闭",
                    }
                    renderer.print_stats(stats, title="当前配置")

                elif command == "/pr":
                    # TODO: PR review functionality
                    renderer.print_panel(
                        "💡 提示",
                        "请使用独立命令启动 PR 审查：\n  python run_pr_review.py\n\n"
                        "或粘贴 diff 内容进行审查（功能开发中）",
                        style="blue"
                    )

                elif command == "/scan":
                    # TODO: Security scanning functionality
                    renderer.print_success("安全扫描功能开发中")

                else:
                    renderer.print_error(f"未知命令：{command}", "输入 /help 查看可用命令")

            else:
                # Natural language input - intelligent intent recognition
                has_context = bool(report_gen._current_projects)
                parsed = nl_parser.parse(user_input, has_context=has_context)

                if parsed.intent == IntentType.FOLLOWUP and has_context:
                    # Follow-up mode
                    with renderer.create_progress("Agent 思考中..."):
                        response = report_gen.handle_followup(user_input)
                    renderer.print_panel("🤖 Agent", response, style="cyan")

                elif parsed.intent == IntentType.ANALYZE:
                    # Analyze a single project
                    query_parts = parsed.query.split("/")
                    if len(query_parts) == 2:
                        owner, repo = query_parts
                        with renderer.create_progress(f"分析项目：{owner}/{repo}"):
                            result = report_gen.analyst.analyze_project(owner, repo)

                        if result.get("error"):
                            renderer.print_error("分析失败", result["error"])
                        else:
                            analysis = result.get("analysis", {})
                            renderer.print_panel(
                                "📊 分析结果",
                                f"核心功能：{analysis.get('core_function', 'N/A')}\n"
                                f"技术栈：{analysis.get('tech_stack', {}).get('language', 'N/A')}\n"
                                f"推荐意见：{analysis.get('recommendation', 'N/A')}",
                                style="green"
                            )
                    else:
                        renderer.print_warning("无法识别项目名，请使用 owner/repo 格式")

                elif parsed.intent == IntentType.SEARCH:
                    # Search projects
                    query = parsed.query
                    time_desc = f" ({parsed.time_range})" if parsed.time_range else ""
                    with renderer.create_progress(f"搜索：{query}{time_desc}"):
                        search_result = report_gen.researcher.search_and_analyze(
                            query=query,
                            sort=parsed.sort_by,
                            per_page=parsed.num_results,
                        )

                    repos = search_result.get("repositories", [])
                    if repos:
                        renderer.print_info(f"找到 {len(repos)} 个项目")
                        rows = []
                        for i, repo in enumerate(repos[:parsed.num_results], 1):
                            rows.append([
                                str(i),
                                repo["full_name"],
                                f"⭐ {repo['stars']:,}",
                                repo.get("language", ""),
                            ])
                        renderer.print_table("搜索结果", ["#", "项目", "Stars", "语言"], rows)
                    else:
                        renderer.print_warning("未找到相关项目")

                elif parsed.intent == IntentType.REPORT:
                    # Generate detailed report
                    query = parsed.query
                    time_desc = f" ({parsed.time_range})" if parsed.time_range else ""
                    with renderer.create_progress(f"生成报告：{query}{time_desc}"):
                        report = report_gen.execute(
                            query=query,
                            num_projects=parsed.num_results,
                            sort=parsed.sort_by,
                        )
                    renderer.print_success("报告生成完成！")
                    # Display full report (truncate reports exceeding 10,000 characters)
                    display_limit = 10000
                    if len(report) > display_limit:
                        renderer.print_panel("📄 报告", report[:display_limit])
                        renderer.print_warning(f"报告已截断（{len(report)} 字符，显示前 {display_limit} 字符）")
                    else:
                        renderer.print_panel("📄 报告", report)

                else:
                    # Unknown intent, try to handle as search
                    with renderer.create_progress(f"搜索：{user_input}"):
                        search_result = report_gen.researcher.search_and_analyze(
                            query=user_input,
                            sort="stars",
                            per_page=5,
                        )

                    repos = search_result.get("repositories", [])
                    if repos:
                        renderer.print_info(f"找到 {len(repos)} 个项目")
                        renderer.print_panel("💡 提示", "使用 '分析第一个' 或 '对比前 3 个' 继续交互")
                    else:
                        renderer.print_warning("未找到相关项目，请尝试其他关键词")

        except KeyboardInterrupt:
            print("\n")
            renderer.print_warning("按 Ctrl+C 中断，输入 /quit 退出程序")
        except EOFError:
            renderer.print_success("再见！")
            break


def main():
    """Main entry point"""
    # Welcome message
    print_welcome()

    # Environment check
    check_environment()

    # Interactive mode
    print("\n")
    renderer.print_panel("开始使用", "输入命令或直接输入问题开始分析", style="green")
    run_interactive_mode()


if __name__ == "__main__":
    main()
