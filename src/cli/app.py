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
from src.core.guardrails import sanitize_user_input  # noqa: E402
from src.core.guardrails import get_approval_manager  # noqa: E402
from src.core.feedback import get_feedback_collector, FeedbackSession  # noqa: E402
import agentscope  # noqa: E402
from src.core.config_manager import ConfigManager  # noqa: E402
from src.workflows.agent_pipeline import AgentPipeline  # noqa: E402
from src.core.agentscope_persistent_memory import get_persistent_memory  # noqa: E402


def _check_studio_reachable(studio_url: str) -> bool:
    """Check if Studio server is reachable."""
    try:
        import requests
        # Try to reach Studio's health endpoint (or just the root)
        resp = requests.get(studio_url, timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _setup_tracing(config: ConfigManager) -> None:
    """Initialize OpenTelemetry tracing (standalone, without Studio).

    Supports external OTel backends like Arize Phoenix, Langfuse, etc.
    """
    tracing_url = config.agentscope_tracing_url
    if not tracing_url:
        return

    try:
        agentscope.init(
            project="GitHub Insight Agent",
            tracing_url=tracing_url,
        )
        # Register span attribute injector for standalone tracing too
        from src.core.span_injector import configure_span_injector
        configure_span_injector(
            config.agentscope_run_name,
            "GitHub Insight Agent",
        )
        print(f"[Tracing] Enabled (endpoint: {tracing_url})")
    except Exception as e:
        print(f"[Tracing] Failed to init: {e}")


def _setup_studio(config: ConfigManager) -> None:
    """Initialize AgentScope Studio connection with tracing."""
    studio_url = config.agentscope_studio_url
    run_name = config.agentscope_run_name

    # Determine tracing URL:
    # 1. User-specified via AGENTSCOPE_TRACING_URL (highest priority)
    # 2. Studio base URL + /v1/traces (OTLP endpoint)
    # 3. None (no tracing)
    if config.agentscope_tracing_url:
        tracing_url = config.agentscope_tracing_url
    elif config.agentscope_enable_tracing:
        tracing_url = studio_url.rstrip("/") + "/v1/traces"
    else:
        # Always enable tracing to Studio when Studio is reachable
        tracing_url = studio_url.rstrip("/") + "/v1/traces"

    # Check if Studio server is reachable before initializing
    studio_reachable = _check_studio_reachable(studio_url)

    init_kwargs = dict(
        project="GitHub Insight Agent",
        name=run_name,
        run_id=run_name,
        studio_url=studio_url,
    )
    if tracing_url:
        init_kwargs["tracing_url"] = tracing_url

    try:
        agentscope.init(**init_kwargs)
    except Exception as e:
        print(f"[Studio] Failed to init: {e}")

    # Register span attribute injector to link spans to the run
    # (gen_ai.conversation.id is required by Studio's trace viewer)
    from src.core.span_injector import configure_span_injector
    configure_span_injector(run_name)

    # Set global studio config for message forwarding
    from src.core.studio_helper import set_global_studio_config
    set_global_studio_config(studio_url, run_name)

    # Set custom studio config for agents
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    set_researcher_studio(studio_url, run_name)
    set_analyst_studio(studio_url, run_name)

    if studio_reachable:
        print(f"[Studio] Enabled and reachable at {studio_url} (run_id: {run_name})")
    else:
        print(
            f"[Studio] Enabled but server unreachable at {studio_url}. "
            f"Messages will not appear in Studio.\n"
            f"  Start Studio: docker compose --profile studio up -d studio"
        )


def _push_to_studio(sender: str, content: str, role: str = "assistant") -> None:
    """Push a message to Studio (uses AgentScope official hook)."""
    try:
        from src.core.studio_integration import push_to_studio
        push_to_studio(sender, content[:8000], role)
    except Exception:
        pass  # Graceful degradation - does not affect main flow


def _approve_tool(prompt: str) -> bool:
    """CLI callback for interactive tool approval.

    Used as prompt_callback for HumanApprovalManager.
    Shows a yes/no prompt via prompt_toolkit.
    """
    try:
        answer = cli.get_input(prompt).strip().lower()
        return answer in ("y", "yes", "是", "y\n")
    except (EOFError, KeyboardInterrupt):
        return False


# Register HITL approval manager with CLI callback at module load
get_approval_manager(prompt_callback=_approve_tool)


def print_welcome():
    """Print welcome message"""
    renderer.print_banner()

    commands = {
        "/analyze <owner/repo>": "分析指定 GitHub 项目",
        "/search <关键词>": "搜索 GitHub 项目",
        "/report <关键词>": "生成详细分析报告",
        "/pr": "审查 Pull Request (粘贴 diff)",
        "/scan <文件>": "安全扫描代码",
        "/rate <good|bad> [理由]": "对上次回复打分",
        "/feedback <文本>": "提交详细反馈",
        "/feedback-stats": "查看反馈统计",
        "/history": "显示对话历史",
        "/clear": "清空对话",
        "/export <路径>": "导出对话记录",
        "/help": "显示帮助",
        "/quit": "退出程序",
    }
    renderer.print_help(commands)

    # P2: Cross-session memory — show recent conversation summary
    _show_cross_session_summary()

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


def _show_cross_session_summary() -> None:
    """P2: Display cross-session memory summary if available."""
    try:
        pm = get_persistent_memory()
        summary = pm.get_messages_summary(max_messages=5)
        if summary:
            renderer.print_panel(
                "🔄 上次会话摘要",
                summary[:500] + ("..." if len(summary) > 500 else ""),
                style="yellow",
            )
    except Exception:
        # Graceful degradation — don't fail startup if memory is unavailable
        pass


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
    config = ConfigManager()

    # Set up Studio connection (registers hooks + custom forwarding)
    if config.agentscope_enable_studio:
        _setup_studio(config)
        studio_enabled = True
    else:
        studio_enabled = False

    # Standalone tracing without Studio (headless / OTel backend)
    if not config.agentscope_enable_studio and config.agentscope_enable_tracing:
        _setup_tracing(config)

    # Initialize report generator
    report_gen = AgentPipeline()

    # Initialize feedback session
    feedback_collector = get_feedback_collector()
    feedback_session = FeedbackSession(run_id=config.agentscope_run_name)

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
                        "/rate <good|bad> [理由]": "对上次回复打分",
                        "/feedback <文本>": "提交详细反馈",
                        "/feedback-stats": "查看反馈统计",
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

                    # Sanitize input
                    try:
                        args = sanitize_user_input(args)
                    except ValueError as e:
                        renderer.print_error("输入被拦截", str(e))
                        continue

                    owner, repo = args.split("/", 1)

                    with renderer.create_progress("分析项目中..."):  # noqa: F841
                        result = report_gen.analyst.analyze_project(owner, repo)

                    if result.get("error"):
                        renderer.print_error("分析失败", result["error"])
                    else:
                        analysis = result.get("analysis", {})
                        tech = analysis.get("tech_stack", {})
                        score = analysis.get("suitability_score", 0)
                        maturity = analysis.get("maturity_assessment", "unknown")
                        risk_flags = analysis.get("risk_flags", [])
                        frameworks = tech.get("frameworks", [])
                        deps = tech.get("key_dependencies", [])

                        # Build detailed display
                        detail_lines = [
                            f"[bold]{result.get('project', f'{owner}/{repo}')}[/]",
                            f"[dim]{result.get('url', '')}[/]",
                            "",
                            f"[cyan]核心功能:[/] {analysis.get('core_function', 'N/A')}",
                            "",
                            f"[cyan]技术栈:[/] {tech.get('language', 'N/A')}",
                        ]
                        if frameworks:
                            detail_lines.append(f"  框架: {', '.join(frameworks)}")
                        if deps:
                            detail_lines.append(f"  依赖: {', '.join(deps)}")

                        detail_lines.extend([
                            "",
                            f"[cyan]架构模式:[/] {analysis.get('architecture_pattern', 'N/A')}",
                            f"[cyan]成熟度:[/] {maturity}",
                            f"[cyan]适配度:[/] {score:.0%}",
                        ])

                        breakdown = analysis.get("score_breakdown", {})
                        if breakdown:
                            score_parts = []
                            for k, v in breakdown.items():
                                score_parts.append(f"{k}: {v:.0%}")
                            detail_lines.append(f"  {' | '.join(score_parts)}")

                        if risk_flags:
                            detail_lines.append(f"\n[yellow]风险标记:[/] {', '.join(risk_flags[:3])}")

                        detail_lines.extend([
                            "",
                            f"[green]推荐意见:[/] {analysis.get('recommendation', 'N/A')}",
                        ])

                        competitive = analysis.get("competitive_analysis", "")
                        if competitive:
                            detail_lines.extend([
                                "",
                                f"[cyan]竞品对比:[/] {competitive}",
                            ])

                        renderer.print_panel("📊 分析结果", "\n".join(detail_lines), style="blue")

                elif command == "/search":
                    if not args:
                        renderer.print_error("用法：/search <关键词>", "例如：/search Python web framework")
                        continue

                    # Sanitize input
                    try:
                        safe_search = sanitize_user_input(args)
                    except ValueError as e:
                        renderer.print_error("输入被拦截", str(e))
                        continue

                    with renderer.create_progress(f"搜索：{safe_search}"):  # noqa: F841
                        search_result = report_gen.researcher.search_and_analyze(
                            query=safe_search, sort="stars", per_page=5,
                        )

                    repos = search_result.get("repositories", [])
                    if repos:
                        renderer.print_info(f"找到 {len(repos)} 个项目")
                        rows = []
                        for i, repo in enumerate(repos[:5], 1):
                            desc = repo.get("description", "") or ""
                            if len(desc) > 50:
                                desc = desc[:47] + "..."
                            rows.append([
                                str(i),
                                repo["full_name"],
                                f"⭐ {repo['stars']:,}",
                                repo.get("language", "") or "N/A",
                                desc or "—",
                            ])
                        renderer.print_table("搜索结果", ["#", "项目", "Stars", "语言", "简介"], rows)
                    else:
                        renderer.print_warning("未找到相关项目")
                    query = args if args else "Rust AI framework"
                    with renderer.create_progress(f"生成报告：{query}"):
                        report = report_gen.execute(
                            query=query,
                            num_projects=3,
                            sort="stars",
                        )
                    renderer.print_success("报告生成完成！")
                    renderer.print_panel("📄 报告", report[:8000])
                    if len(report) > 8000:
                        renderer.print_warning(f"报告已截断（{len(report)} 字符，显示前 8000 字符）")

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
                        "Tracing": "开启" if config.agentscope_enable_tracing else "关闭",
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

                elif command == "/rate":
                    # Usage: /rate good|bad [reason]
                    parts = args.split(maxsplit=1)
                    if not parts:
                        renderer.print_error("用法：/rate good|bad [理由]")
                        renderer.print_info("例：/rate good 分析结果很准确")
                        continue

                    rating = parts[0].lower()
                    reason = parts[1] if len(parts) > 1 else ""

                    if rating not in ("good", "bad", "g", "b"):
                        renderer.print_error("评分必须是 good 或 bad")
                        continue

                    if rating in ("g", "b"):
                        rating = "good" if rating == "g" else "bad"

                    row_id = feedback_collector.record_quick(
                        rating=rating,
                        reason=reason,
                        session_state=feedback_session,
                    )

                    # Also feed into ReportGenerator KPI tracker (P2-9)
                    report_gen.rate_report(rating=rating, reason=reason)

                    emoji = "👍" if rating == "good" else "👎"
                    renderer.print_success(f"已记录反馈 [{emoji} {rating}] (id={row_id})")

                elif command == "/feedback":
                    # Usage: /feedback "text"
                    if not args.strip():
                        renderer.print_error("用法：/feedback <反馈内容>")
                        renderer.print_info("例：/feedback 希望能支持更多语言的分析")
                        continue

                    row_id = feedback_collector.record(
                        rating="neutral",
                        reason=args.strip(),
                        user_input=feedback_session.last_user_input,
                        assistant_output=feedback_session.last_assistant_output,
                        agent=feedback_session.current_agent,
                        run_id=feedback_session.run_id,
                    )
                    renderer.print_success(f"已记录反馈 (id={row_id})")

                elif command == "/feedback-stats":
                    stats = feedback_collector.get_stats()
                    renderer.print_panel(
                        "📊 反馈统计",
                        f"总反馈: {stats['total']}\n"
                        f"👍 好评: {stats['good']}  |  👎 差评: {stats['bad']}\n"
                        f"中立: {stats['neutral']}  |  好评率: {stats['positive_rate']}%",
                        style="green",
                    )

                else:
                    renderer.print_error(f"未知命令：{command}", "输入 /help 查看可用命令")

            else:
                # Natural language input — LLM-based intent understanding
                try:
                    safe_input = sanitize_user_input(user_input)
                except ValueError as e:
                    renderer.print_error("输入被拦截", str(e))
                    continue

                # Use LLM to understand intent
                intent = report_gen.researcher._understand_intent(safe_input)
                action = intent["action"]
                params = intent["params"]

                if action == "search_repositories":
                    # Detect if user explicitly asked to "analyze"
                    query = params.get("query", safe_input)
                    sort = params.get("sort", "stars")
                    limit = min(params.get("limit", 5), 5)

                    if "分析" in safe_input:
                        # User wants a full analysis report
                        feedback_session.set_agent("report")
                        with renderer.create_progress(f"生成报告：{query}"):
                            report = report_gen.execute(
                                query=query, num_projects=limit, sort=sort,
                            )
                        renderer.print_success("报告生成完成！")
                        display_limit = 10000
                        display_report = report[:display_limit] if len(report) > display_limit else report
                        feedback_session.set_last_interaction(safe_input, display_report)
                        if len(report) > display_limit:
                            renderer.print_panel("📄 报告", display_report)
                            renderer.print_warning(f"报告已截断（{len(report)} 字符，显示前 {display_limit} 字符）")
                        else:
                            renderer.print_panel("📄 报告", display_report)
                        if studio_enabled:
                            _push_to_studio("user", user_input, "user")
                            _push_to_studio("Report", display_report[:8000], "assistant")
                    else:
                        # Simple search — just show results table
                        feedback_session.set_agent("researcher")
                        with renderer.create_progress(f"搜索：{query}"):
                            search_result = report_gen.researcher.search_and_analyze(
                                query=query, sort=sort, per_page=limit,
                            )

                        repos = search_result.get("repositories", [])
                        if repos:
                            renderer.print_info(f"找到 {len(repos)} 个项目")
                            rows = []
                            for i, repo in enumerate(repos[:limit], 1):
                                desc = repo.get("description", "") or ""
                                if len(desc) > 50:
                                    desc = desc[:47] + "..."
                                rows.append([
                                    str(i), repo["full_name"],
                                    f"⭐ {repo['stars']:,}",
                                    repo.get("language", "") or "N/A",
                                    desc or "—",
                                ])
                            renderer.print_table("搜索结果", ["#", "项目", "Stars", "语言", "简介"], rows)
                            forwarded_content = "\n".join(
                                f"{i}. **{r['full_name']}** ⭐ {r['stars']:,} "
                                f"{r.get('language', '')} — {r.get('description', '')[:50]}"
                                for i, r in enumerate(repos[:limit], 1)
                            )
                        else:
                            renderer.print_warning("未找到相关项目")
                            forwarded_content = f"搜索「{query}」未找到相关项目"
                        feedback_session.set_last_interaction(safe_input, forwarded_content)
                        if studio_enabled:
                            _push_to_studio("user", user_input, "user")
                            _push_to_studio("Researcher", forwarded_content, "assistant")

                elif action == "get_repo_info":
                    # Single repo lookup
                    feedback_session.set_agent("researcher")
                    owner = params.get("owner", "")
                    repo = params.get("repo", "")
                    with renderer.create_progress(f"查看项目：{owner}/{repo}"):
                        result = report_gen.analyst.analyze_project(owner, repo)
                    if result.get("error"):
                        renderer.print_error("查询失败", result["error"])
                    else:
                        analysis = result.get("analysis", {})
                        tech = analysis.get("tech_stack", {})
                        detail_lines = [
                            f"[bold]{owner}/{repo}[/]",
                            f"[dim]{result.get('url', '')}[/]", "",
                            f"[cyan]核心功能:[/] {analysis.get('core_function', 'N/A')}", "",
                            f"[cyan]技术栈:[/] {tech.get('language', 'N/A')}",
                        ]
                        frameworks = tech.get("frameworks", [])
                        if frameworks:
                            detail_lines.append(f"  框架: {', '.join(frameworks)}")
                        deps = tech.get("key_dependencies", [])
                        if deps:
                            detail_lines.append(f"  依赖: {', '.join(deps)}")
                        detail_lines.extend([
                            "", f"[cyan]架构模式:[/] {analysis.get('architecture_pattern', 'N/A')}",
                            f"[cyan]成熟度:[/] {analysis.get('maturity_assessment', 'unknown')}",
                            f"[cyan]适配度:[/] {analysis.get('suitability_score', 0):.0%}", "",
                            f"[green]推荐:[/] {analysis.get('recommendation', 'N/A')}",
                        ])
                        renderer.print_panel("📊 项目详情", "\n".join(detail_lines), style="blue")
                    resp = result.get("project", f"{owner}/{repo}")
                    feedback_session.set_last_interaction(safe_input, resp)
                    if studio_enabled:
                        _push_to_studio("user", user_input, "user")
                        _push_to_studio("Researcher", resp, "assistant")

                elif action == "analyze_project":
                    # Analyze a single project
                    feedback_session.set_agent("analyst")
                    owner = params.get("owner", "")
                    repo = params.get("repo", "")
                    with renderer.create_progress(f"分析项目：{owner}/{repo}"):
                        result = report_gen.analyst.analyze_project(owner, repo)
                    if result.get("error"):
                        renderer.print_error("分析失败", result["error"])
                    else:
                        analysis = result.get("analysis", {})
                        tech = analysis.get("tech_stack", {})
                        score = analysis.get("suitability_score", 0)
                        maturity = analysis.get("maturity_assessment", "unknown")
                        risk_flags = analysis.get("risk_flags", [])
                        frameworks = tech.get("frameworks", [])
                        deps = tech.get("key_dependencies", [])
                        detail_lines = [
                            f"[bold]{owner}/{repo}[/]", "",
                            f"[cyan]核心功能:[/] {analysis.get('core_function', 'N/A')}", "",
                            f"[cyan]技术栈:[/] {tech.get('language', 'N/A')}",
                        ]
                        if frameworks:
                            detail_lines.append(f"  框架: {', '.join(frameworks)}")
                        if deps:
                            detail_lines.append(f"  依赖: {', '.join(deps)}")
                        detail_lines.extend([
                            "", f"[cyan]架构模式:[/] {analysis.get('architecture_pattern', 'N/A')}",
                            f"[cyan]成熟度:[/] {maturity}",
                            f"[cyan]适配度:[/] {score:.0%}",
                        ])
                        if risk_flags:
                            detail_lines.append(f"\n[yellow]风险标记:[/] {', '.join(risk_flags[:3])}")
                        detail_lines.append(f"\n[green]推荐:[/] {analysis.get('recommendation', 'N/A')}")
                        renderer.print_panel("📊 分析结果", "\n".join(detail_lines), style="blue")
                    resp = f"分析 {owner}/{repo} 完成"
                    feedback_session.set_last_interaction(safe_input, resp)
                    if studio_enabled:
                        _push_to_studio("user", user_input, "user")
                        _push_to_studio("Analyst", resp, "assistant")

                elif action == "compare_repositories":
                    # Compare projects
                    feedback_session.set_agent("researcher")
                    repos_list = params.get("repositories", [])
                    with renderer.create_progress(f"对比项目：{', '.join(repos_list)}"):
                        compare_result = report_gen.researcher._execute_compare(
                            {"repositories": repos_list}, analyst=report_gen.analyst,
                        )
                    renderer.print_panel("📊 项目对比", compare_result)
                    feedback_session.set_last_interaction(safe_input, compare_result)
                    if studio_enabled:
                        _push_to_studio("user", user_input, "user")
                        _push_to_studio("Researcher", compare_result[:8000], "assistant")

                else:
                    # Chat / general Q&A
                    feedback_session.set_agent("chat")
                    with renderer.create_progress("思考中..."):
                        chat_response = report_gen.researcher._call_llm(safe_input)
                    renderer.print_panel("🤖 AI", chat_response, style="cyan")
                    feedback_session.set_last_interaction(safe_input, chat_response)
                    if studio_enabled:
                        _push_to_studio("user", user_input, "user")
                        _push_to_studio("AI", chat_response[:8000], "assistant")

        except KeyboardInterrupt:
            print("\n")
            renderer.print_warning("按 Ctrl+C 中断，输入 /quit 退出程序")
        except EOFError:
            renderer.print_success("再见！")
            break


def main():
    """Main entry point"""
    try:
        # Welcome message
        print_welcome()

        # Environment check
        check_environment()

        # Interactive mode
        print("\n")
        renderer.print_panel("开始使用", "输入命令或直接输入问题开始分析", style="green")
        run_interactive_mode()
    finally:
        # Flush traces to ensure they reach Studio
        try:
            from src.core.studio_integration import flush_traces
            flush_traces()
        except Exception:
            pass


if __name__ == "__main__":
    main()
