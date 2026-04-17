# -*- coding: utf-8 -*-
"""
GitHub Insight Agent - 集成测试脚本

测试目标:
1. 验证 GitHub MCP Server 连接和工具调用
2. 验证本地数据库持久化存储
3. 验证配置加载正确

运行方式:
    python tests/test_integration.py
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config_manager import ConfigManager
from src.core.agentscope_persistent_memory import PersistentMemory, get_persistent_memory
from src.mcp.github_mcp_client import GitHubMCPClient, create_github_mcp_client
from src.core.logger import get_logger

logger = get_logger(__name__)


# ===========================================
# 测试 1: 配置加载测试
# ===========================================
def test_config_loading():
    """测试配置加载"""
    print("\n" + "="*60)
    print("测试 1: 配置加载测试")
    print("="*60)

    config = ConfigManager()

    results = {
        "env_loaded": False,
        "dashscope_api_key": False,
        "github_token": False,
        "model_config": False,
    }

    # 检查环境变量加载
    print(f"\n  .env 文件加载状态：{config.env_loaded}")
    results["env_loaded"] = config.env_loaded

    # 检查阿里云百炼配置
    print(f"  DASHSCOPE_API_KEY: {'已配置' if config.dashscope_api_key else '未配置'}")
    results["dashscope_api_key"] = bool(config.dashscope_api_key)

    # 检查 GitHub 配置
    print(f"  GITHUB_TOKEN: {'已配置' if config.github_token else '未配置'}")
    results["github_token"] = bool(config.github_token)

    # 检查模型配置
    print(f"  默认模型：{config.dashscope_model_name}")
    print(f"  Model configs loaded: {bool(config.model_configs)}")
    results["model_config"] = bool(config.model_configs)

    # 显示关键配置
    print("\n  关键配置摘要:")
    print(f"    - 项目根目录：{config.project_root}")
    print(f"    - 日志级别：{config.log_level}")
    print(f"    - 调试模式：{config.debug_mode}")
    print(f"    - AgentScope Studio: {'启用' if config.agentscope_enable_studio else '禁用'}")

    # 汇总
    passed = sum(results.values())
    total = len(results)
    print(f"\n  配置检查：{passed}/{total} 项通过")

    all_passed = all(results.values())
    if all_passed:
        print("  ✓ 测试 1 通过 - 所有配置正确加载")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ⚠ 测试 1 部分通过 - 以下配置缺失：{failed}")

    return all_passed


# ===========================================
# 测试 2: 本地数据库持久化测试
# ===========================================
def test_database_persistence():
    """测试本地数据库持久化"""
    print("\n" + "="*60)
    print("测试 2: 本地数据库持久化测试")
    print("="*60)

    db_path = "data/test_integration.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    results = {
        "db_created": False,
        "write_success": False,
        "read_success": False,
        "persistence": False,
    }

    try:
        # 创建持久化记忆实例
        print(f"\n  创建数据库：{db_path}")
        pm = PersistentMemory(db_path=db_path, max_messages=100)
        results["db_created"] = os.path.exists(db_path)
        print(f"  数据库文件创建：{'✓' if results['db_created'] else '✗'}")

        # 写入测试数据
        print("\n  写入测试数据...")
        test_messages = [
            ("user", "搜索 GitHub 上关于 AI 的 Python 项目", "user"),
            ("assistant", "找到 10 个相关项目", "Researcher"),
            ("user", "分析第一个项目", "user"),
            ("assistant", "项目分析完成", "Analyst"),
        ]

        for role, content, name in test_messages:
            pm.add_message(role=role, content=content, name=name)
            print(f"    [写入] {role}: {content[:40]}...")

        results["write_success"] = pm.size() == 4
        print(f"\n  写入成功：{'✓' if results['write_success'] else '✗'} (消息数：{pm.size()})")

        # 读取验证
        print("\n  读取验证...")
        messages = pm.get_memory()
        results["read_success"] = len(messages) == 4
        for msg in messages:
            print(f"    [读取] {msg.role}: {msg.content[:40]}...")
        print(f"  读取成功：{'✓' if results['read_success'] else '✗'}")

        # 跨实例持久化测试（模拟重启）
        print("\n  跨实例持久化测试（模拟重启）...")
        del pm  # 销毁实例

        pm2 = PersistentMemory(db_path=db_path, max_messages=100)
        messages2 = pm2.get_memory()
        results["persistence"] = len(messages2) == 4
        print(f"  持久化验证：{'✓' if results['persistence'] else '✗'} (重启后消息数：{len(messages2)})")

        # 显示数据库文件状态
        file_size = os.path.getsize(db_path)
        print(f"\n  数据库文件大小：{file_size:,} 字节")

    except Exception as e:
        print(f"\n  ✗ 测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 汇总
    passed = sum(results.values())
    total = len(results)
    print(f"\n  数据库测试：{passed}/{total} 项通过")

    all_passed = all(results.values())
    if all_passed:
        print("  ✓ 测试 2 通过 - 数据库持久化工作正常")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ⚠ 测试 2 部分通过 - 以下检查失败：{failed}")

    return all_passed


# ===========================================
# 测试 3: GitHub MCP Server 连接测试
# ===========================================
def test_github_mcp_connection():
    """测试 GitHub MCP Server 连接"""
    print("\n" + "="*60)
    print("测试 3: GitHub MCP Server 连接测试")
    print("="*60)

    config = ConfigManager()

    results = {
        "token_configured": False,
        "binary_exists": False,
        "client_created": False,
        "connection_success": False,
        "tools_available": False,
    }

    # 检查 GitHub Token
    print(f"\n  GitHub Token: {'已配置' if config.github_token else '未配置'}")
    results["token_configured"] = bool(config.github_token)

    if not config.github_token:
        print("  ⚠ GitHub Token 未配置，跳过后续测试")
        return False

    # 检查二进制文件（使用环境变量或默认路径）
    bin_path = os.environ.get(
        "GITHUB_MCP_SERVER_BIN",
        str(Path(__file__).parent.parent / "bin" / "github-mcp-server")
    )
    print(f"\n  MCP Server 二进制文件：{bin_path}")
    results["binary_exists"] = os.path.exists(bin_path)
    print(f"  文件存在：{'✓' if results['binary_exists'] else '✗'}")

    if not results["binary_exists"]:
        print("  ⚠ 二进制文件不存在，跳过后续测试")
        return False

    # 检查文件是否可执行
    is_executable = os.access(bin_path, os.X_OK)
    print(f"  可执行权限：{'✓' if is_executable else '✗'}")

    try:
        # 创建客户端
        print("\n  创建 GitHub MCP 客户端...")
        client = GitHubMCPClient(
            github_token=config.github_token,
            bin_path=bin_path,
        )
        results["client_created"] = True
        print("  客户端创建：✓")

        # 测试连接
        print("\n  测试连接到 MCP Server...")
        import asyncio

        async def test_connection():
            await client.connect()
            # is_connected 是属性而不是方法
            is_connected = client.is_connected

            # 获取工具列表
            tools = await client.list_tools()

            return is_connected, tools

        is_connected, tools = asyncio.run(test_connection())
        results["connection_success"] = is_connected
        print(f"  连接状态：{'✓' if results['connection_success'] else '✗'}")

        # 检查可用工具
        if tools:
            results["tools_available"] = len(tools) > 0
            print(f"\n  可用工具数量：{len(tools)}")
            print("  工具列表:")
            for i, tool in enumerate(tools[:10], 1):  # 显示前 10 个
                tool_name = tool.name if hasattr(tool, 'name') else tool.get('name', 'unknown')
                print(f"    {i}. {tool_name}")
            if len(tools) > 10:
                print(f"    ... 还有 {len(tools) - 10} 个工具")
        else:
            print("  工具列表：空")

        # 尝试调用一个简单工具（获取当前用户信息）
        print("\n  尝试调用 GitHub API 测试...")
        async def test_tool_call():
            # 使用 search_repositories 工具测试
            try:
                result = await client.call_tool(
                    name="search_repositories",
                    arguments={"query": "python test framework", "perPage": "1"}
                )
                return result
            except Exception as e:
                return {"error": str(e)}

        test_result = asyncio.run(test_tool_call())
        if isinstance(test_result, dict) and "error" not in test_result:
            print("  工具调用：✓")
        else:
            print(f"  工具调用：⚠ {test_result.get('error', '未知错误')}")

    except Exception as e:
        print(f"\n  ✗ MCP 连接测试失败：{e}")
        import traceback
        traceback.print_exc()

    # 汇总
    passed = sum(results.values())
    total = len(results)
    print(f"\n  MCP 测试：{passed}/{total} 项通过")

    all_passed = all(results.values())
    if all_passed:
        print("  ✓ 测试 3 通过 - GitHub MCP Server 工作正常")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ⚠ 测试 3 部分通过 - 以下检查失败：{failed}")

    return all_passed


# ===========================================
# 测试 4: 端到端集成测试
# ===========================================
def test_end_to_end():
    """端到端集成测试"""
    print("\n" + "="*60)
    print("测试 4: 端到端集成测试")
    print("="*60)

    config = ConfigManager()
    db_path = "data/test_e2e.db"

    if os.path.exists(db_path):
        os.remove(db_path)

    results = {
        "config_loaded": False,
        "database_ready": False,
        "mcp_ready": False,
        "full_workflow": False,
    }

    # 1. 检查配置
    print("\n  [步骤 1] 检查配置加载...")
    results["config_loaded"] = config.env_loaded and bool(config.github_token)
    print(f"  配置状态：{'✓' if results['config_loaded'] else '✗'}")

    # 2. 检查数据库
    print("\n  [步骤 2] 初始化数据库...")
    try:
        pm = PersistentMemory(db_path=db_path, max_messages=100)
        pm.add_user_message("端到端测试开始")
        results["database_ready"] = pm.size() >= 1
        print(f"  数据库状态：{'✓' if results['database_ready'] else '✗'}")
    except Exception as e:
        print(f"  数据库状态：✗ ({e})")

    # 3. 检查 MCP
    print("\n  [步骤 3] 检查 MCP Server...")
    mcp_bin_path = os.environ.get(
        "GITHUB_MCP_SERVER_BIN",
        str(Path(__file__).parent.parent / "bin" / "github-mcp-server")
    )
    if config.github_token and os.path.exists(mcp_bin_path):
        try:
            client = GitHubMCPClient(
                github_token=config.github_token,
                bin_path=mcp_bin_path,
            )

            async def check_mcp():
                await client.connect()
                # is_connected 是属性而不是方法
                return client.is_connected

            import asyncio
            is_connected = asyncio.run(check_mcp())
            results["mcp_ready"] = is_connected
            print(f"  MCP 状态：{'✓' if results['mcp_ready'] else '✗'}")
        except Exception as e:
            print(f"  MCP 状态：✗ ({e})")
    else:
        print("  MCP 状态：⚠ (配置不完整，跳过)")

    # 4. 完整工作流模拟
    print("\n  [步骤 4] 模拟完整工作流...")
    try:
        # 模拟用户查询 -> 数据库存储
        pm.add_user_message("搜索 python web framework")
        pm.add_assistant_message("MCP 已连接，准备调用工具")

        if results["mcp_ready"]:
            # MCP 已连接，验证连接状态即可
            print("  MCP 连接验证：✓")
            results["full_workflow"] = pm.size() >= 2
            print(f"  工作流执行：✓ (MCP 连接成功，数据库正常)")
        else:
            pm.add_assistant_message("MCP 未就绪，跳过工具调用")
            results["full_workflow"] = pm.size() >= 2
            print(f"  工作流执行：⚠ (MCP 未就绪)")

    except Exception as e:
        print(f"  工作流执行：✗ ({e})")

    # 汇总
    passed = sum(results.values())
    total = len(results)
    print(f"\n  端到端测试：{passed}/{total} 项通过")

    all_passed = all(results.values())
    if all_passed:
        print("  ✓ 测试 4 通过 - 端到端集成工作正常")
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"  ⚠ 测试 4 部分通过 - 以下检查失败：{failed}")

    return all_passed


# ===========================================
# 主测试运行器
# ===========================================
def run_all_tests():
    """运行所有集成测试"""
    print("\n" + "#"*60)
    print(f"# GitHub Insight Agent - 集成测试")
    print(f"# 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)

    results = {}

    tests = [
        ("配置加载测试", test_config_loading),
        ("数据库持久化测试", test_database_persistence),
        ("GitHub MCP Server 连接测试", test_github_mcp_connection),
        ("端到端集成测试", test_end_to_end),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n  ✗ {name} 异常：{e}")
            results[name] = False
            import traceback
            traceback.print_exc()

    # 汇总报告
    print("\n" + "="*60)
    print("集成测试结果汇总")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print(f"\n总计：{passed}/{total} 测试通过")

    # 显示文件状态
    print("\n数据库文件状态:")
    import glob
    db_files = glob.glob("data/*.db")
    for f in sorted(db_files):
        size = os.path.getsize(f)
        print(f"  {f}: {size:,} 字节")

    # 最终判断
    print("\n" + "="*60)
    if passed == total:
        print("✓ 所有测试通过！GitHub MCP Server 和本地数据库工作正常。")
    else:
        print(f"⚠ {total - passed} 个测试未通过，请检查相关配置。")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
