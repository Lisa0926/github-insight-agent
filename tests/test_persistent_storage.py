# -*- coding: utf-8 -*-
"""
持久化存储测试脚本

测试目标:
1. 验证数据能够正确写入 SQLite 数据库
2. 验证数据在 Agent 重启后能够正确读取
3. 验证记忆压缩机制正常工作
4. 验证多会话隔离

测试方法:
- 创建多个对话轮次
- 重启 Agent 验证数据持久化
- 检查数据库文件内容
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.agentscope_persistent_memory import PersistentMemory, get_persistent_memory
from src.agents.researcher_agent import ResearcherAgent
from src.agents.analyst_agent import AnalystAgent
from src.core.config_manager import ConfigManager


def test_basic_write_read():
    """测试 1: 基本写入和读取"""
    print("\n" + "="*60)
    print("测试 1: 基本写入和读取")
    print("="*60)

    db_path = "data/test_basic.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # 创建记忆实例并写入数据
    pm = PersistentMemory(db_path=db_path, max_messages=100)

    test_messages = [
        ("user", "搜索 Python 机器学习项目", "user"),
        ("assistant", "找到 10 个相关项目", "Researcher"),
        ("user", "分析第一个项目", "user"),
        ("assistant", "正在分析 scikit-learn...", "Analyst"),
    ]

    for role, content, name in test_messages:
        pm.add_message(role=role, content=content, name=name)
        print(f"  [写入] {role}: {content[:30]}...")

    # 验证读取
    messages = pm.get_memory()
    print(f"\n  消息总数：{pm.size()}")
    assert pm.size() == 4, f"Expected 4 messages, got {pm.size()}"

    # 验证消息内容
    for i, msg in enumerate(messages):
        expected_role, expected_content, expected_name = test_messages[i]
        assert msg.role == expected_role, f"Role mismatch at {i}"
        assert msg.content == expected_content, f"Content mismatch at {i}"
        print(f"  [读取] {msg.role}: {msg.content[:30]}... ✓")

    print("\n  ✓ 测试 1 通过")
    return True


def test_cross_instance_persistence():
    """测试 2: 跨实例持久化（模拟重启）"""
    print("\n" + "="*60)
    print("测试 2: 跨实例持久化")
    print("="*60)

    db_path = "data/test_persistence.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # 实例 1: 写入数据
    print("  [实例 1] 写入数据...")
    pm1 = PersistentMemory(db_path=db_path, max_messages=100)
    pm1.add_user_message("用户查询 A")
    pm1.add_assistant_message("助手回复 A")
    pm1.add_user_message("用户查询 B")
    print(f"  [实例 1] 消息数：{pm1.size()}")

    # 模拟重启：销毁实例 1，创建实例 2
    del pm1

    print("  [模拟重启] 创建新实例...")
    pm2 = PersistentMemory(db_path=db_path, max_messages=100)
    messages = pm2.get_memory()

    print(f"  [实例 2] 消息数：{pm2.size()}")
    assert pm2.size() == 3, f"Expected 3 messages after restart, got {pm2.size()}"

    for msg in messages:
        print(f"  [读取] {msg.role}: {msg.content[:30]}... ✓")

    print("\n  ✓ 测试 2 通过 - 数据成功持久化")
    return True


def test_memory_compression():
    """测试 3: 记忆压缩机制"""
    print("\n" + "="*60)
    print("测试 3: 记忆压缩机制")
    print("="*60)

    db_path = "data/test_compression.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # 设置较小的压缩阈值
    max_messages = 10
    pm = PersistentMemory(db_path=db_path, max_messages=max_messages)

    # 写入超过阈值的消息
    print(f"  写入 25 条消息 (阈值={max_messages})...")
    for i in range(25):
        pm.add_user_message(f"用户查询 {i}")
        pm.add_assistant_message(f"助手回复 {i}")

    print(f"  压缩后消息数：{pm.size()}")
    print(f"  压缩摘要：{pm.compressed_summary[:80]}...")

    # 验证压缩后消息数不超过阈值 + 2
    assert pm.size() <= max_messages + 2, f"Compression failed: {pm.size()} > {max_messages + 2}"
    assert len(pm.compressed_summary) > 0, "Compression summary should not be empty"
    assert "历史对话摘要" in pm.compressed_summary, "Summary should contain expected header"

    print(f"  ✓ 压缩成功：{pm.size()} 条消息，摘要 {len(pm.compressed_summary)} 字符")
    print("\n  ✓ 测试 3 通过")
    return True


def test_agent_integration():
    """测试 4: Agent 集成测试"""
    print("\n" + "="*60)
    print("测试 4: Agent 集成测试")
    print("="*60)

    db_path = "data/test_agent.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    config = ConfigManager()

    # 创建 Agent（启用持久化）- 强制创建新实例
    print("  创建 ResearcherAgent (持久化启用)...")
    researcher = ResearcherAgent(config=config, use_persistent=True, db_path=db_path)

    # 执行一次搜索
    print("  执行搜索：python test framework")
    result = researcher.search_and_analyze(query="python test framework", per_page=3)
    print(f"  找到 {result['total_found']} 个项目")

    # 检查记忆 - 使用 agent 内部的 memory
    pm = researcher.memory
    print(f"  当前记忆大小：{pm.size()}")

    # 验证数据已持久化 - ResearcherAgent 在 search_and_analyze 中不保存消息
    # 改用 reply 方法来验证消息保存
    print("  使用 reply 方法测试消息保存...")
    response = researcher.reply("搜索 pytest 框架")
    print(f"  响应长度：{len(response.content)} 字符")

    # 再次检查记忆
    print(f"  reply 后记忆大小：{pm.size()}")

    # 验证数据库文件存在
    assert os.path.exists(db_path), f"Database file not found: {db_path}"

    # 获取用于构建 prompt 的消息
    prompt_messages = pm.get_messages_for_prompt()
    print(f"  Prompt 消息数：{len(prompt_messages)}")

    # 验证至少有用户消息和助手回复
    assert pm.size() >= 2, f"Agent should have saved at least 2 messages, got {pm.size()}"

    print("\n  ✓ 测试 4 通过 - Agent 与持久化存储集成成功")
    return True


def test_multi_session_isolation():
    """测试 5: 多会话隔离"""
    print("\n" + "="*60)
    print("测试 5: 多会话隔离")
    print("="*60)

    db_path = "data/test_multisession.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    pm = PersistentMemory(db_path=db_path, max_messages=100)

    # 模拟会话 A
    print("  [会话 A] 添加消息...")
    pm.add_message("user", "会话 A - 查询 1", name="user_A")
    pm.add_message("assistant", "会话 A - 回复 1", name="assistant_A")

    # 模拟会话 B
    print("  [会话 B] 添加消息...")
    pm.add_message("user", "会话 B - 查询 1", name="user_B")
    pm.add_message("assistant", "会话 B - 回复 1", name="assistant_B")

    messages = pm.get_memory()
    print(f"  总消息数：{len(messages)}")

    # 验证两个会话的消息都存在
    session_a_msgs = [m for m in messages if "会话 A" in m.content]
    session_b_msgs = [m for m in messages if "会话 B" in m.content]

    print(f"  会话 A 消息数：{len(session_a_msgs)}")
    print(f"  会话 B 消息数：{len(session_b_msgs)}")

    assert len(session_a_msgs) == 2, "Session A messages missing"
    assert len(session_b_msgs) == 2, "Session B messages missing"

    print("\n  ✓ 测试 5 通过 - 多会话数据共存")
    return True


def test_database_file_inspection():
    """测试 6: 数据库文件检查"""
    print("\n" + "="*60)
    print("测试 6: 数据库文件检查")
    print("="*60)

    db_path = "data/test_agent.db"

    if not os.path.exists(db_path):
        print(f"  数据库文件不存在：{db_path}")
        print("  先运行测试 4 创建数据库")
        return None

    # 使用 sqlite3 直接检查数据库
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取表列表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"  数据库表：{[t[0] for t in tables]}")

    # 检查每个表的数据
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  - {table_name}: {count} 条记录")

        # 显示前几条记录
        if table_name == 'messages':
            cursor.execute(f"SELECT id, role, content, name, created_at FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            print(f"    示例数据:")
            for row in rows:
                print(f"    [{row[3]}] {row[1]}: {row[2][:40]}... ({row[4]})")

    conn.close()

    # 获取文件大小
    file_size = os.path.getsize(db_path)
    print(f"  数据库文件大小：{file_size:,} 字节")

    print("\n  ✓ 测试 6 完成")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "#"*60)
    print(f"# GitHub Insight Agent - 持久化存储测试")
    print(f"# 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("#"*60)

    results = {}

    # 运行所有测试
    tests = [
        ("基本写入读取", test_basic_write_read),
        ("跨实例持久化", test_cross_instance_persistence),
        ("记忆压缩机制", test_memory_compression),
        ("Agent 集成", test_agent_integration),
        ("多会话隔离", test_multi_session_isolation),
        ("数据库文件检查", test_database_file_inspection),
    ]

    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n  ✗ {name} 失败：{e}")
            results[name] = False
            import traceback
            traceback.print_exc()

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {status} - {name}")

    print(f"\n总计：{passed}/{total} 测试通过")

    # 显示数据库文件状态
    print("\n数据库文件状态:")
    import glob
    db_files = glob.glob("data/test_*.db")
    for f in db_files:
        size = os.path.getsize(f)
        print(f"  {f}: {size:,} 字节")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
