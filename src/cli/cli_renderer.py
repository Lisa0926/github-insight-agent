# -*- coding: utf-8 -*-
"""
CLI 美化模块

提供:
- 彩色输出
- Emoji 图标
- 表格/面板渲染
- 进度条
- 友好错误提示
"""

import sys
from typing import Any, Dict, List, Optional

# 检查并导入 rich 库
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.live import Live
    from rich.text import Text
    from rich.box import ROUNDED
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class CLIRenderer:
    """CLI 渲染器 - 提供友好的终端输出"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self._use_rich = RICH_AVAILABLE and self.console is not None

    # ========== 图标字典 ==========
    ICONS = {
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
        "star": "⭐",
        "fork": "🍴",
        "eye": "👁️",
        "code": "💻",
        "rocket": "🚀",
        "check": "✓",
        "cross": "✗",
        "arrow": "→",
        "search": "🔍",
        "report": "📊",
        "file": "📄",
        "folder": "📁",
        "link": "🔗",
        "clock": "🕐",
        "lightbulb": "💡",
        "fire": "🔥",
        "heart": "❤️",
        "party": "🎉",
    }

    # ========== 基础输出方法 ==========
    def print(self, *args, **kwargs):
        """打印文本"""
        if self._use_rich:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_panel(self, title: str, content: str, style: str = "blue"):
        """打印面板"""
        if self._use_rich:
            self.console.print(Panel(content, title=title, border_style=style))
        else:
            print(f"\n{'=' * 60}")
            print(f" {title}")
            print(f"{'=' * 60}")
            print(content)
            print(f"{'=' * 60}\n")

    def print_success(self, message: str):
        """打印成功消息"""
        icon = self.ICONS["success"] if self._use_rich else "[OK]"
        self.print(f"[green]{icon} {message}[/]" if self._use_rich else f"✅ {message}")

    def print_error(self, message: str, details: Optional[str] = None):
        """打印错误消息"""
        icon = self.ICONS["error"] if self._use_rich else "[ERROR]"
        if self._use_rich:
            self.print(f"[bold red]{icon} {message}[/]")
            if details:
                self.print(f"[dim]{details}[/]")
        else:
            print(f"❌ {message}")
            if details:
                print(f"   详情：{details}")

    def print_warning(self, message: str):
        """打印警告消息"""
        icon = self.ICONS["warning"] if self._use_rich else "[WARN]"
        self.print(f"[yellow]{icon} {message}[/]" if self._use_rich else f"⚠️ {message}")

    def print_info(self, message: str):
        """打印信息"""
        icon = self.ICONS["info"] if self._use_rich else "[INFO]"
        self.print(f"[cyan]{icon} {message}[/]" if self._use_rich else f"ℹ️ {message}")

    # ========== 进度条 ==========
    def create_progress(self, description: str = "处理中..."):
        """创建进度条"""
        if self._use_rich:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
            )
        else:
            # 简单文本进度
            print(f"→ {description}")
            return None

    def print_loading(self, message: str):
        """打印加载中提示"""
        if self._use_rich:
            self.print(f"[cyan]⠋ {message}...[/]")
        else:
            print(f"⏳ {message}...")

    # ========== 表格渲染 ==========
    def create_table(self, title: str = "", columns: Optional[List[str]] = None) -> Any:
        """创建表格"""
        if not self._use_rich:
            return None

        table = Table(title=title, box=ROUNDED, show_header=True, header_style="bold")
        if columns:
            for col in columns:
                table.add_column(col)
        return table

    def print_table(self, title: str, headers: List[str], rows: List[List[str]]):
        """打印表格"""
        if self._use_rich:
            table = Table(title=title, box=ROUNDED, show_header=True, header_style="bold cyan")
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)
        else:
            # 简单文本表格
            print(f"\n{title}")
            print("-" * 80)
            print(" | ".join(headers))
            print("-" * 80)
            for row in rows:
                print(" | ".join(str(cell) for cell in row))
            print("-" * 80)

    # ========== 项目信息卡片 ==========
    def print_repo_card(self, repo: Dict[str, Any]):
        """打印项目信息卡片"""
        name = repo.get("full_name", "Unknown")
        description = repo.get("description", "无描述")
        stars = repo.get("stars", 0)
        forks = repo.get("forks", 0)
        language = repo.get("language", "Unknown")
        url = repo.get("html_url", "")

        if self._use_rich:
            card = Panel(
                f"[bold]{name}[/]\n\n"
                f"{description}\n\n"
                f"[yellow]⭐ {stars:,}[/]  [green]🍴 {forks:,}[/]  [blue]{language}[/]\n"
                f"[dim]{url}[/]",
                border_style="blue",
            )
            self.console.print(card)
        else:
            print(f"\n{'=' * 50}")
            print(f" {name}")
            print(f"{'=' * 50}")
            print(f" {description}")
            print(f" ⭐ {stars:,} | 🍴 {forks:,} | {language}")
            print(f" 🔗 {url}\n")

    # ========== 代码块渲染 ==========
    def print_code(self, code: str, language: str = "python"):
        """打印代码块"""
        if self._use_rich:
            self.console.print(Syntax(code, language, theme="monokai", line_numbers=True))
        else:
            print(f"\n```{language}")
            print(code)
            print("```\n")

    # ========== Markdown 渲染 ==========
    def print_markdown(self, content: str):
        """打印 Markdown 内容"""
        if self._use_rich:
            self.console.print(Markdown(content))
        else:
            print(content)

    # ========== 启动横幅 ==========
    def print_banner(self, version: str = "v1.1.0"):
        """打印启动横幅"""
        banner = f"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ███╗   ██╗███████╗██╗    ██╗██╗   ██╗███████╗         ║
║   ████╗  ██║██╔════╝██║    ██║██║   ██║██╔════╝         ║
║   ██╔██╗ ██║█████╗  ██║ █╗ ██║██║   ██║███████╗         ║
║   ██║╚██╗██║██╔══╝  ██║███╗██║██║   ██║╚════██║         ║
║   ██║ ╚████║███████╗╚███╔███╔╝╚██████╔╝███████║         ║
║   ╚═╝  ╚═══╝╚══════╝ ╚══╝╚══╝  ╚═════╝ ╚══════╝         ║
║                                                          ║
║        GitHub Insight Agent - {version:<15}║
║     企业级多智能体 GitHub 项目分析系统                       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
        if self._use_rich:
            self.console.print(f"[bold cyan]{banner}[/]")
        else:
            print(banner)

    # ========== 帮助信息 ==========
    def print_help(self, commands: Dict[str, str]):
        """打印帮助信息"""
        if self._use_rich:
            table = Table(title="可用命令", box=ROUNDED, header_style="bold cyan")
            table.add_column("命令", style="yellow", width=20)
            table.add_column("描述", style="white")

            for cmd, desc in commands.items():
                table.add_row(cmd, desc)

            self.console.print(table)
        else:
            print("\n可用命令:")
            print("-" * 50)
            for cmd, desc in commands.items():
                print(f"  {cmd:<20} {desc}")
            print("-" * 50)

    # ========== 统计信息 ==========
    def print_stats(self, stats: Dict[str, Any], title: str = "统计"):
        """打印统计信息"""
        if self._use_rich:
            grid = Table.grid(padding=(0, 2))
            grid.add_column(style="cyan", width=20)
            grid.add_column(style="white")

            for key, value in stats.items():
                grid.add_row(f"{key}:", str(value))

            self.console.print(f"[bold]{title}[/]")
            self.console.print(grid)
        else:
            print(f"\n{title}:")
            for key, value in stats.items():
                print(f"  {key}: {value}")


# 全局渲染器实例
renderer = CLIRenderer()
