# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - 增强版 CLI 入口

功能:
- 彩色友好输出
- 命令自动补全
- 进度条显示
- 结构化报告展示
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cli.cli_renderer import renderer
from src.cli.interactive_cli import cli
from src.core.config_manager import ConfigManager


def print_welcome():
    """打印欢迎信息"""
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


def check_environment():
    """检查环境配置"""
    config = ConfigManager()

    stats = {
        "配置文件": "✅" if config.env_loaded else "⚠️ 未加载",
        "模型": config.dashscope_model_name or "未设置",
        "日志级别": config.log_level,
        "调试模式": "开启" if config.debug_mode else "关闭",
    }

    renderer.print_stats(stats, title="环境状态")

    if not config.env_loaded:
        renderer.print_warning("未检测到 .env 文件，部分功能可能不可用")
        renderer.print_info("复制 .env.sample 为 .env 并配置 API Key")


def run_interactive_mode():
    """运行交互模式"""
    from src.workflows.report_generator import ReportGenerator
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    config = ConfigManager()

    # 设置 Studio 配置
    if config.agentscope_enable_studio:
        set_researcher_studio(config.agentscope_studio_url, config.agentscope_run_name)
        set_analyst_studio(config.agentscope_studio_url, config.agentscope_run_name)
        renderer.print_info(f"Studio 已启用 (run_id: {config.agentscope_run_name})")

    # 初始化报告生成器
    report_gen = ReportGenerator()

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

                    with renderer.create_progress("分析项目中...") as progress:
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

                    with renderer.create_progress(f"搜索：{args}") as progress:
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
                    # TODO: 实现报告生成工作流
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
                    # TODO: 实现导出功能
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
                    # TODO: PR 审查功能
                    renderer.print_panel(
                        "💡 提示",
                        "请使用独立命令启动 PR 审查：\n  python run_pr_review.py\n\n"
                        "或粘贴 diff 内容进行审查（功能开发中）",
                        style="blue"
                    )

                elif command == "/scan":
                    # TODO: 安全扫描功能
                    renderer.print_success("安全扫描功能开发中")

                else:
                    renderer.print_error(f"未知命令：{command}", "输入 /help 查看可用命令")

            else:
                # 普通对话
                if not report_gen._current_projects:
                    renderer.print_warning(
                        "请先使用 /search 或 /analyze 命令，然后再追问问题"
                    )
                    continue

                with renderer.create_progress("Agent 思考中..."):
                    response = report_gen.handle_followup(user_input)

                renderer.print_panel("🤖 Agent", response, style="cyan")

        except KeyboardInterrupt:
            print("\n")
            renderer.print_warning("按 Ctrl+C 中断，输入 /quit 退出程序")
        except EOFError:
            renderer.print_success("再见！")
            break


def main():
    """主入口"""
    # 欢迎信息
    print_welcome()

    # 环境检查
    check_environment()

    # 交互模式
    print("\n")
    renderer.print_panel("开始使用", "输入命令或直接输入问题开始分析", style="green")
    run_interactive_mode()


if __name__ == "__main__":
    main()
