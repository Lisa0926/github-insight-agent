# -*- coding: utf-8 -*-
"""
Interactive CLI - Enhanced Version

Provides:
- Command auto-completion
- Command history recording
- Friendly input prompts
- Colored output
"""

from pathlib import Path
from typing import Optional

# Check and import prompt_toolkit
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.key_binding import KeyBindings
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False


class CommandCompleter(Completer):
    """Command auto-completion"""

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
    """Interactive CLI manager"""

    def __init__(self, history_file: Optional[str] = None):
        self.session = None
        self.history_file = history_file

        if PROMPT_TOOLKIT_AVAILABLE:
            # Set up history file
            if history_file:
                history_path = Path(history_file)
                history_path.parent.mkdir(parents=True, exist_ok=True)
                history = FileHistory(str(history_path))
            else:
                history = None

            # Create session
            self.session = PromptSession(
                completer=CommandCompleter(),
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                key_bindings=self._create_key_bindings(),
                complete_while_typing=True,
                enable_history_search=True,
            )

    def _create_key_bindings(self) -> KeyBindings:
        """Create keyboard shortcut bindings"""
        if not PROMPT_TOOLKIT_AVAILABLE:
            return None

        bindings = KeyBindings()

        @bindings.add("c-q")
        def exit_(event):
            """Ctrl+Q to exit"""
            event.app.exit(exception=EOFError())

        @bindings.add("c-c")
        def interrupt_(event):
            """Ctrl+C to interrupt"""
            event.app.exit(exception=KeyboardInterrupt())

        return bindings

    def get_input(self, prompt: str = "👤 您：") -> Optional[str]:
        """Get user input"""
        try:
            if self.session and PROMPT_TOOLKIT_AVAILABLE:
                return self.session.prompt(prompt)
            else:
                return input(prompt)
        except KeyboardInterrupt:
            raise
        except EOFError:
            raise

    def clear_input_buffer(self):
        """Clear input buffer"""
        pass


# Global CLI instance
cli = InteractiveCLI(
    history_file=str(Path.home() / ".github-insight-agent" / "cli_history.txt")
)
