# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - 企业级多智能体情报分析系统

入口文件，提供:
- AgentScope 初始化
- 配置加载
- 模型测试
- 智能体集成测试
"""

import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.types.schemas import GitHubRepoInfo

logger = get_logger(__name__)


def initialize_agentscope() -> str:
    """
    初始化 AgentScope 框架

    加载模型配置并初始化 AgentScope 运行时环境
    支持 Studio 可视化和 Tracing 追踪

    Returns:
        运行 ID (run_id)
    """
    import agentscope
    from agentscope.hooks import _equip_as_studio_hooks
    from functools import partial

    config_manager = ConfigManager()

    # 生成运行 ID（使用时间戳）
    from datetime import datetime
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 构建 studio_url 参数
    studio_url = None
    if config_manager.agentscope_enable_studio:
        studio_url = config_manager.agentscope_studio_url
        logger.info(f"Studio enabled with URL: {studio_url}")

    # 构建 tracing_url 参数
    tracing_url = None
    if config_manager.agentscope_enable_tracing:
        tracing_url = config_manager.agentscope_tracing_url or None
        if tracing_url:
            logger.info(f"Tracing enabled with URL: {tracing_url}")
        else:
            logger.info("Tracing enabled but no tracing URL provided")

    # 初始化 AgentScope (使用配置管理器中的参数)
    agentscope.init(
        project=config_manager.agentscope_project,
        name=config_manager.agentscope_run_name,
        run_id=run_id,
        logging_path=f"{config_manager.log_dir}/agentscope.log",
        logging_level=config_manager.log_level,
        studio_url=studio_url,
        tracing_url=tracing_url,
    )

    # 手动注册 Studio hooks 到 AgentBase
    if studio_url:
        from agentscope.agent import AgentBase
        from agentscope.hooks._studio_hooks import as_studio_forward_message_pre_print_hook
        AgentBase.register_class_hook(
            "pre_print",
            "as_studio_forward_message_pre_print_hook",
            partial(
                as_studio_forward_message_pre_print_hook,
                studio_url=studio_url,
                run_id=run_id,
            ),
        )
        logger.info("Studio hooks registered to AgentBase")

    # 显示 Studio 状态
    if config_manager.agentscope_enable_studio:
        logger.info("AgentScope Studio enabled")
    else:
        logger.info("AgentScope Studio disabled (set AGENTSCOPE_ENABLE_STUDIO=true to enable)")

    # 显示 Tracing 状态
    if config_manager.agentscope_enable_tracing:
        logger.info("AgentScope Tracing enabled")
    else:
        logger.info("AgentScope Tracing disabled (set AGENTSCOPE_ENABLE_TRACING=true to enable)")

    logger.info(f"AgentScope initialized (run_id={run_id})")
    logger.info(f"Log file: {config_manager.log_dir}/agentscope.log")

    return run_id


def _process_config_placeholders(configs: dict) -> dict:
    """
    处理配置中的 ${env:VAR_NAME} 占位符

    Args:
        configs: 原始配置字典

    Returns:
        处理后的配置字典
    """
    import os
    import re

    env_pattern = re.compile(r"\$\{env:(\w+)\}")

    def replace_env_value(value: str) -> str:
        match = env_pattern.match(value)
        if match:
            env_var = match.group(1)
            return os.getenv(env_var, "")
        return value

    def process_dict(d: dict) -> dict:
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = process_dict(value)
            elif isinstance(value, str):
                result[key] = replace_env_value(value)
            else:
                result[key] = value
        return result

    return process_dict(configs)


def test_model_connection() -> bool:
    """
    测试阿里云百炼模型连接

    Returns:
        连接是否成功
    """
    try:
        config_manager = ConfigManager()

        # 从环境变量获取模型名称
        model_name = config_manager.dashscope_model_name
        api_key = config_manager.dashscope_api_key

        logger.info(f"Testing model connection: {model_name}")

        # 检查 API Key 是否配置
        if not api_key:
            logger.error(
                f"API Key not configured for {model_name}. "
                "Please set DASHSCOPE_API_KEY in .env file."
            )
            return False

        # 使用 dashscope 直接测试
        import dashscope
        from dashscope import Generation

        dashscope.api_key = api_key

        logger.info(f"Calling API with key: {api_key[:10]}...")
        logger.info(f"Full API Key in env: {os.getenv('DASHSCOPE_API_KEY', 'NOT SET')}")

        response = Generation.call(
            model=model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=config_manager.model_max_tokens,
        )

        # 打印完整响应以便调试
        logger.info(f"Response status_code: {response.status_code}")
        logger.info(f"Response code: {getattr(response, 'code', 'N/A')}")
        logger.info(f"Response message: {getattr(response, 'message', 'N/A')}")
        logger.info(f"Response output: {getattr(response, 'output', 'N/A')}")

        if response.status_code == 200 and response.output:
            try:
                # 尝试新格式：output.text (dashscope 新版 API)
                output_dict = response.output if isinstance(response.output, dict) else {}
                result = output_dict.get('text', '')

                if not result:
                    # 尝试旧格式：output.choices[0].message.content
                    result = response.output.choices[0].message.content

                logger.info(f"Model test successful! Response: {result[:100]}...")
                return True
            except (AttributeError, TypeError, IndexError) as e:
                logger.error(f"Failed to parse response: {e}")
                logger.error(f"Response.output structure: {response.output}")
                return False

    except ImportError as e:
        logger.error(f"Import error: {e}")
        return False
    except AttributeError as e:
        logger.error(f"API response format error: {e}")
        logger.error(f"Response object: {locals().get('response', 'N/A')}")
        return False
    except Exception as e:
        logger.error(f"Model test failed with exception: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("GitHub Insight Agent - Starting")
    logger.info("=" * 60)

    # 显示配置信息
    config_manager = ConfigManager()
    logger.info(f"Environment loaded: {config_manager.env_loaded}")
    logger.info(f"Project: {config_manager.project_root}")
    logger.info(f"Model: {config_manager.dashscope_model_name}")
    logger.info(f"Log Level: {config_manager.log_level}")
    logger.info(f"Debug Mode: {config_manager.debug_mode}")

    # 初始化 AgentScope
    run_id = initialize_agentscope()

    # 测试模型连接
    logger.info("-" * 40)
    logger.info("Testing model connection...")
    success = test_model_connection()

    if success:
        logger.info("=" * 60)
        logger.info("GitHub Insight Agent - Environment Ready!")
        logger.info(f"Run ID: {run_id}")
        logger.info("=" * 60)
    else:
        logger.warning("-" * 40)
        logger.warning("Model connection test failed.")
        logger.warning("Please check your API Key configuration:")
        logger.warning("1. Check DASHSCOPE_API_KEY in .env")
        logger.warning("2. Verify API Key is valid at https://bailian.console.aliyun.com/")
        logger.warning("=" * 60)

    return success


def show_studio_help():
    """
    显示 AgentScope Studio 使用说明
    """
    help_text = """
╔══════════════════════════════════════════════════════════════╗
║          AgentScope Studio 使用说明                           ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  AgentScope Studio 是一个可视化调试界面，可以：               ║
║  - 查看 Agent 执行过程                                        ║
║  - 追踪消息流转                                              ║
║  - 分析对话历史                                              ║
║                                                              ║
║  启用方法：                                                   ║
║  1. 设置环境变量：                                            ║
║     export AGENTSCOPE_ENABLE_STUDIO=true                     ║
║                                                              ║
║  2. (可选) 配置 Studio 服务器 URL:                            ║
║     export AGENTSCOPE_STUDIO_URL=http://localhost:5000       ║
║                                                              ║
║  3. 运行应用后，日志会记录在：                                ║
║     logs/agentscope.log                                      ║
║                                                              ║
║  4. 使用以下命令启动 Studio 服务器（如果有）：                 ║
║     as_studio logs/agentscope.log                            ║
║                                                              ║
║  查看日志文件：                                               ║
║     tail -f logs/agentscope.log                              ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(help_text)


def run_agent_demo():
    """
    运行 Agent 演示

    实例化 ResearcherAgent 并执行测试查询
    """
    from src.agents import ResearcherAgent
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    logger.info("=" * 60)
    logger.info("Day 3-4: Agent Integration Test")
    logger.info("=" * 60)

    # 设置 Studio 配置（两个 Agent 模块都需要设置）
    config_manager = ConfigManager()
    if config_manager.agentscope_enable_studio:
        studio_url = config_manager.agentscope_studio_url
        run_id = config_manager.agentscope_run_name
        set_researcher_studio(studio_url, run_id)
        set_analyst_studio(studio_url, run_id)
        logger.info(f"Studio config set for run: {run_id}")

    # 实例化 Agent
    agent = ResearcherAgent(name="Researcher", model_name="qwen-max")

    # 显示 Agent 状态
    status = agent.get_status()
    logger.info(f"Agent Status: {status['name']}")
    logger.info(f"Model: {status['model']}")
    logger.info(f"Tools: {status['tools_available']}")
    logger.info(f"GitHub Token Configured: {status['github_token_configured']}")

    # 测试查询
    test_query = "帮我搜索 GitHub 上关于 'large language model' 最火的 3 个 Python 项目"
    logger.info("-" * 60)
    logger.info(f"Test Query: {test_query}")
    logger.info("-" * 60)

    # 获取 Agent 响应
    print("\n")
    print("=" * 60)
    print("AGENT RESPONSE")
    print("=" * 60)

    response = agent.reply(test_query)
    print(response)

    print("=" * 60)

    # 记录思考过程 (从记忆中提取)
    logger.info("-" * 60)
    logger.info("Agent Memory (Conversation History):")
    for msg in agent.memory:
        logger.info(f"  [{msg['role']}]: {msg['content'][:100]}...")

    return response


def run_report_workflow(query: str = "Rust AI framework"):
    """
    运行报告生成工作流 (Day 5-6)

    Args:
        query: 搜索关键词
    """
    from src.workflows import ReportGenerator
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    logger.info("=" * 60)
    logger.info("Day 5-6: Report Generation Workflow")
    logger.info("=" * 60)

    # 设置 Studio 配置（两个 Agent 模块都需要设置）
    config_manager = ConfigManager()
    if config_manager.agentscope_enable_studio:
        studio_url = config_manager.agentscope_studio_url
        run_id = config_manager.agentscope_run_name
        set_researcher_studio(studio_url, run_id)
        set_analyst_studio(studio_url, run_id)
        logger.info(f"Studio config set for run: {run_id}")

    # 初始化报告生成器
    report_gen = ReportGenerator()

    # 显示配置
    logger.info(f"Search Query: {query}")
    logger.info(f"Analyzing top 3 projects...")
    logger.info("-" * 60)

    # 执行工作流
    print("\n")
    print("=" * 60)
    print("GENERATED REPORT")
    print("=" * 60)
    print()

    report = report_gen.execute(query=query, num_projects=3)
    print(report)

    print()
    print("=" * 60)

    # 保存报告到文件
    output_path = "reports/project_analysis_report.md"
    import os
    os.makedirs("reports", exist_ok=True)

    if report_gen.save_report(output_path):
        logger.info(f"Report saved to: {output_path}")

    # 记录工作流结果摘要
    results = report_gen.get_results()
    logger.info("-" * 60)
    logger.info("Workflow Results Summary:")
    logger.info(f"  Search results: {len(results.get('search_results', []))} projects")
    logger.info(f"  Analysis results: {len(results.get('analysis_results', []))} projects")

    return report


def run_interactive_cli():
    """
    运行交互式 CLI（支持多轮对话和 ReAct 展示）

    Day 8-10 集成测试入口：
    - 测试用例 1: 分析 iii-hq/iii，展示 ReAct 思考过程
    - 测试用例 2: 容错测试，模拟 404 错误
    """
    from src.workflows.report_generator import ReportGenerator
    from src.agents.researcher_agent import set_studio_config as set_researcher_studio
    from src.agents.analyst_agent import set_studio_config as set_analyst_studio

    print("\n" + "=" * 60)
    print("GitHub Insight Agent - 交互式 CLI (Day 8-10)")
    print("=" * 60)
    print("\n欢迎使用 GitHub Insight Agent！")
    print("支持以下命令：")
    print("  /analyze <项目名>  - 分析指定 GitHub 项目（如：/analyze iii-hq/iii）")
    print("  /search <关键词>   - 搜索项目并生成报告")
    print("  /report <关键词>   - 生成详细分析报告")
    print("  /history           - 显示对话历史")
    print("  /clear             - 清空对话历史")
    print("  /export <路径>     - 导出对话记录")
    print("  /test-error        - 容错测试（模拟 404 错误）")
    print("  /quit 或 /exit     - 退出程序")
    print("\n直接输入问题进行追问，Agent 会展示 ReAct 思考过程。")
    print("-" * 60)

    # 设置 Studio 配置（两个 Agent 模块都需要设置）
    config_manager = ConfigManager()
    if config_manager.agentscope_enable_studio:
        studio_url = config_manager.agentscope_studio_url
        run_id = config_manager.agentscope_run_name
        set_researcher_studio(studio_url, run_id)
        set_analyst_studio(studio_url, run_id)
        print(f"\nStudio 已启用 (run_id: {run_id})")

    # 初始化报告生成器（带对话管理）
    report_gen = ReportGenerator()

    # 测试模式标志
    test_mode = False
    test_error_mode = False

    while True:
        try:
            user_input = input("\n👤 您：").strip()

            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                command_parts = user_input.split(maxsplit=1)
                command = command_parts[0].lower()
                args = command_parts[1] if len(command_parts) > 1 else ""

                if command in ["/quit", "/exit"]:
                    print("\n再见！")
                    break

                elif command == "/analyze":
                    if not args:
                        print("用法：/analyze <owner/repo>，例如：/analyze iii-hq/iii")
                        continue

                    # 解析项目名
                    if "/" not in args:
                        print("请输入完整的项目名，格式：owner/repo")
                        continue

                    owner, repo = args.split("/", 1)
                    print(f"\n🤖 Agent 分析中...")

                    # 执行分析（展示 ReAct 思考过程）
                    result = report_gen.analyst.analyze_project(owner, repo)

                    # 显示 ReAct 思考过程
                    if result.get("analysis") and result.get("analysis").get("react_thoughts"):
                        print("\n" + "-" * 40)
                        print("【ReAct 思考过程】")
                        print("-" * 40)
                        for thought in result["analysis"]["react_thoughts"]:
                            print(thought)
                        print("-" * 40)

                    # 显示分析结果
                    if result.get("error"):
                        print(f"\n❌ 分析失败：{result['error']}")
                    else:
                        analysis = result.get("analysis", {})
                        print(f"\n📊 分析结果：")
                        print(f"  核心功能：{analysis.get('core_function', 'N/A')}")
                        print(f"  技术栈：{analysis.get('tech_stack', {}).get('language', 'N/A')}")
                        print(f"  推荐意见：{analysis.get('recommendation', 'N/A')}")

                elif command == "/search":
                    if not args:
                        print("用法：/search <关键词>，例如：/search Python web framework")
                        continue

                    query = args
                    print(f"\n🤖 搜索中：{query}")

                    # 搜索并显示结果
                    search_result = report_gen.researcher.search_and_analyze(
                        query=query,
                        sort="stars",
                        per_page=5,
                    )

                    repos = search_result.get("repositories", [])
                    if repos:
                        print(f"\n📈 找到 {len(repos)} 个项目：")
                        for i, repo in enumerate(repos[:5], 1):
                            print(f"  {i}. {repo['full_name']} - ⭐ {repo['stars']:,}")
                            print(f"     {repo['description'] or 'N/A'}")
                    else:
                        print("\n未找到相关项目。")

                elif command == "/report":
                    query = args if args else "Rust AI framework"
                    print(f"\n🤖 生成报告中：{query}")
                    report = run_report_workflow(query)
                    print("\n报告已生成，查看上方输出。")

                elif command == "/history":
                    history = report_gen.get_conversation_history()
                    if history:
                        print(f"\n📜 对话历史 ({len(history)} 条):")
                        for msg in history[-5:]:  # 显示最近 5 条
                            print(f"  [{msg['role']}] {msg['content'][:80]}...")
                    else:
                        print("\n暂无对话历史。")

                elif command == "/clear":
                    report_gen.clear_conversation()
                    print("\n✓ 对话历史已清空。")

                elif command == "/export":
                    path = args if args else "reports/conversation.md"
                    if report_gen.export_conversation(path):
                        print(f"\n✓ 对话已导出到：{path}")
                    else:
                        print("\n❌ 导出失败。")

                elif command == "/test-error":
                    print("\n🧪 容错测试：模拟 404 错误")
                    test_error_mode = True

                    # 测试不存在的项目
                    print("\n尝试分析不存在的项目：openai/gpt-7-nonexistent")
                    result = report_gen.analyst.analyze_project("openai", "gpt-7-nonexistent")

                    print("\n【ReAct 思考过程】")
                    if result.get("react_thoughts"):
                        for thought in result["react_thoughts"]:
                            print(thought)

                    if result.get("error"):
                        print(f"\n⚠️ 预期错误：{result['error']}")
                        print("Agent 成功捕获错误，没有崩溃。")
                    else:
                        print("\n⚠️ 注意：项目可能存在，或者错误处理未按预期工作。")

                    test_error_mode = False
                    print("\n✓ 容错测试完成。")

                else:
                    print(f"\n未知命令：{command}")
                    print("输入 /help 查看可用命令。")

            else:
                # 普通对话输入（追问）
                # 检查是否有当前分析的项目
                if not report_gen._current_projects:
                    print("\n请先使用 /search 或 /report 命令搜索项目，然后再追问。")
                    continue

                print("\n🤖 Agent 思考中...")
                response = report_gen.handle_followup(user_input)
                print(f"\n🤖 Agent: {response}")

        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except EOFError:
            print("\n\n再见！")
            break


if __name__ == "__main__":
    # 检查是否传入参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            run_agent_demo()
        elif sys.argv[1] == "--report":
            # 获取搜索关键词（可选参数）
            query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Rust AI framework"
            run_report_workflow(query)
        elif sys.argv[1] == "--cli":
            # 交互式 CLI 模式（Day 8-10）
            run_interactive_cli()
        elif sys.argv[1] == "--studio":
            # 显示 Studio 使用说明
            show_studio_help()
        else:
            main()
    else:
        main()
        main()
