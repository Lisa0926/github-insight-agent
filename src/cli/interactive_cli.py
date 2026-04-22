# -*- coding: utf-8 -*-
"""
交互式 CLI - 增强版

提供:
- 命令自动补全
- 历史命令记录
- 友好的输入提示
- 彩色输出
"""

import os
import sys
from pathlib import Path
from typing import List, Optional

# 检查并导入 prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.formatted_text import HTML
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


class CommandCompleter(Completer):
    """命令自动补全"""

    COMMANDS = [
        "/analyze",
        "/search",
        "/report",
        "/pr",
        "/scan",
        "/history",
        "/clear",
        "/export",
        "/config",
        "/help",
        "/quit",
        "/exit",
    ]

    COMMAND_DESCRIPTIONS = {
        "/analyze": "分析指定 GitHub 项目 (如：/analyze owner/repo)",
        "/search": "搜索 GitHub 项目",
        "/report": "生成项目分析报告",
        "/pr": "审查 Pull Request (粘贴 diff)",
        "/scan": "安全扫描代码文件",
        "/history": "显示对话历史",
        "/clear": "清空对话历史",
        "/export": "导出对话记录",
        "/config": "显示/修改配置",
        "/help": "显示帮助信息",
        "/quit": "退出程序",
        "/exit": "退出程序",
    }

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()

        if text.startswith("/"):
            for cmd in self.COMMANDS:
                if cmd.startswith(text):
                    description = self.COMMAND_DESCRIPTIONS.get(cmd, "")
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd} - {description}",
                    )


class InteractiveCLI:
    """交互式 CLI 管理器"""

    def __init__(self, history_file: Optional[str] = None):
        self.session = None
        self.history_file = history_file

        if PROMPT_TOOLKIT_AVAILABLE:
            # 设置历史文件
            if history_file:
                history_path = Path(history_file)
                history_path.parent.mkdir(parents=True, exist_ok=True)
                history = FileHistory(str(history_path))
            else:
                history = None

            # 创建会话
            self.session = PromptSession(
                completer=CommandCompleter(),
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                key_bindings=self._create_key_bindings(),
                complete_while_typing=True,
                enable_history_search=True,
            )

    def _create_key_bindings(self) -> KeyBindings:
        """创建快捷键绑定"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return None

        bindings = KeyBindings()

        @bindings.add("c-q")
        def exit_(event):
            """Ctrl+Q 退出"""
            event.app.exit(exception=EOFError())

        @bindings.add("c-c")
        def interrupt_(event):
            """Ctrl+C 中断"""
            event.app.exit(exception=KeyboardInterrupt())

        return bindings

    def get_input(self, prompt: str = "👤 您：") -> Optional[str]:
        """获取用户输入"""
        try:
            if self.session and PROMPT_TOOLKIT_AVAILABLE:
                return self.session.prompt(
                    prompt,
                    rprompt="  [Ctrl+Q 退出 | ↑↓ 历史 | Tab 补全]",
                )
            else:
                return input(prompt)
        except (KeyboardInterrupt, EOFError):
            return None

    def clear_input_buffer(self):
        """清除输入缓冲"""
        pass


# 全局 CLI 实例
cli = InteractiveCLI(
    history_file=str(Path.home() / ".github-insight-agent" / "cli_history.txt")
)
