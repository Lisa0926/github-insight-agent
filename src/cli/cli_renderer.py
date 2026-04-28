# -*- coding: utf-8 -*-
"""
CLI Beautification Module

Provides:
- Colored output
- Emoji icons
- Table/panel rendering
- Progress bars
- Friendly error messages
"""

from typing import Any, Dict, List, Optional

# Check and import the rich library
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.box import ROUNDED
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class CLIRenderer:
    """CLI renderer - provides friendly terminal output"""

    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self._use_rich = RICH_AVAILABLE and self.console is not None

    # ========== Icon dictionary ==========
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

    # ========== Basic output methods ==========
    def print(self, *args, **kwargs):
        """Print text"""
        if self._use_rich:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_panel(self, title: str, content: str, style: str = "blue"):
        """Print a panel"""
        if self._use_rich:
            self.console.print(Panel(content, title=title, border_style=style))
        else:
            print(f"\n{'=' * 60}")
            print(f" {title}")
            print(f"{'=' * 60}")
            print(content)
            print(f"{'=' * 60}\n")

    def print_success(self, message: str):
        """Print success message"""
        icon = self.ICONS["success"] if self._use_rich else "[OK]"
        self.print(f"[green]{icon} {message}[/]" if self._use_rich else f"✅ {message}")

    def print_error(self, message: str, details: Optional[str] = None):
        """Print error message"""
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
        """Print warning message"""
        icon = self.ICONS["warning"] if self._use_rich else "[WARN]"
        self.print(f"[yellow]{icon} {message}[/]" if self._use_rich else f"⚠️ {message}")

    def print_info(self, message: str):
        """Print info message"""
        icon = self.ICONS["info"] if self._use_rich else "[INFO]"
        self.print(f"[cyan]{icon} {message}[/]" if self._use_rich else f"ℹ️ {message}")

    # ========== Progress bars ==========
    def create_progress(self, description: str = "处理中..."):
        """Create a progress bar"""
        if self._use_rich:
            return Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=self.console,
            )
        else:
            # Simple text progress
            print(f"→ {description}")
            return None

    def print_loading(self, message: str):
        """Print loading hint"""
        if self._use_rich:
            self.print(f"[cyan]⠋ {message}...[/]")
        else:
            print(f"⏳ {message}...")

    # ========== Table rendering ==========
    def create_table(self, title: str = "", columns: Optional[List[str]] = None) -> Any:
        """Create a table"""
        if not self._use_rich:
            return None

        table = Table(title=title, box=ROUNDED, show_header=True, header_style="bold")
        if columns:
            for col in columns:
                table.add_column(col)
        return table

    def print_table(self, title: str, headers: List[str], rows: List[List[str]]):
        """Print a table"""
        if self._use_rich:
            table = Table(title=title, box=ROUNDED, show_header=True, header_style="bold cyan")
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)
        else:
            # Simple text table
            print(f"\n{title}")
            print("-" * 80)
            print(" | ".join(headers))
            print("-" * 80)
            for row in rows:
                print(" | ".join(str(cell) for cell in row))
            print("-" * 80)

    # ========== Project info card ==========
    def print_repo_card(self, repo: Dict[str, Any]):
        """Print project info card"""
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

    # ========== Code block rendering ==========
    def print_code(self, code: str, language: str = "python"):
        """Print a code block"""
        if self._use_rich:
            self.console.print(Syntax(code, language, theme="monokai", line_numbers=True))
        else:
            print(f"\n```{language}")
            print(code)
            print("```\n")

    # ========== Markdown rendering ==========
    def print_markdown(self, content: str):
        """Print Markdown content"""
        if self._use_rich:
            self.console.print(Markdown(content))
        else:
            print(content)

    # ========== Startup banner ==========
    def print_banner(self, version: str = "v1.1.0"):
        """Print startup banner"""
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

    # ========== Help information ==========
    def print_help(self, commands: Dict[str, str]):
        """Print help information"""
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

    # ========== Statistics ==========
    def print_stats(self, stats: Dict[str, Any], title: str = "统计"):
        """Print statistics"""
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


# Global renderer instance
renderer = CLIRenderer()
