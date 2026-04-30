# -*- coding: utf-8 -*-
"""
HTML 报告导出器

将 Markdown 格式的分析报告转换为美观的 HTML 页面，支持：
- 移动端适配（响应式设计）
- 深色/浅色主题
- 项目趋势图表（纯 CSS 实现）
- 适合微信/飞书内嵌浏览
"""

import os
import re
from datetime import datetime
from typing import Optional, Dict, Any

import markdown
from jinja2 import Template


# ===========================================
# HTML 模板
# ===========================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --accent-hover: #79b8ff;
            --success: #2ea043;
            --warning: #d29922;
            --danger: #f85149;
            --border: #30363d;
            --shadow: rgba(0, 0, 0, 0.4);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        /* 头部 */
        .header {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 8px var(--shadow);
        }

        .header h1 {
            font-size: 24px;
            color: var(--accent);
            margin-bottom: 8px;
        }

        .header .meta {
            color: var(--text-secondary);
            font-size: 14px;
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }

        .header .meta span {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }

        /* 关键指标卡片 */
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }

        .metric-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px;
            text-align: center;
            transition: transform 0.2s;
        }

        .metric-card:hover {
            transform: translateY(-2px);
        }

        .metric-card .value {
            font-size: 32px;
            font-weight: bold;
            color: var(--accent);
            margin-bottom: 4px;
        }

        .metric-card .label {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .metric-card.success .value { color: var(--success); }
        .metric-card.warning .value { color: var(--warning); }
        .metric-card.danger .value { color: var(--danger); }

        /* 章节 */
        .section {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .section h2 {
            font-size: 20px;
            color: var(--accent);
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }

        .section h3 {
            font-size: 16px;
            color: var(--text-primary);
            margin: 16px 0 8px;
        }

        /* 表格 */
        .table-wrapper {
            overflow-x: auto;
            margin: 16px 0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }

        th {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 13px;
        }

        tr:hover {
            background: var(--bg-tertiary);
        }

        /* 列表 */
        ul, ol {
            margin: 12px 0;
            padding-left: 24px;
        }

        li {
            margin: 6px 0;
        }

        /* 代码 */
        code {
            background: var(--bg-tertiary);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 13px;
        }

        pre {
            background: var(--bg-tertiary);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 12px 0;
        }

        pre code {
            background: none;
            padding: 0;
        }

        /* 状态标签 */
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 500;
        }

        .badge-success { background: rgba(46, 160, 67, 0.15); color: var(--success); }
        .badge-warning { background: rgba(210, 153, 34, 0.15); color: var(--warning); }
        .badge-danger { background: rgba(248, 81, 73, 0.15); color: var(--danger); }
        .badge-info { background: rgba(88, 166, 255, 0.15); color: var(--accent); }

        /* 引用 */
        blockquote {
            border-left: 3px solid var(--accent);
            padding-left: 16px;
            margin: 12px 0;
            color: var(--text-secondary);
        }

        /* 链接 */
        a {
            color: var(--accent);
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* 分隔线 */
        hr {
            border: none;
            border-top: 1px solid var(--border);
            margin: 20px 0;
        }

        /* 页脚 */
        .footer {
            text-align: center;
            padding: 16px;
            color: var(--text-secondary);
            font-size: 12px;
        }

        /* 趋势箭头 */
        .trend-up::before { content: "↑ "; color: var(--success); }
        .trend-down::before { content: "↓ "; color: var(--danger); }
        .trend-flat::before { content: "→ "; color: var(--text-secondary); }

        /* 项目卡片 */
        .project-card {
            background: var(--bg-tertiary);
            border-radius: 8px;
            padding: 16px;
            margin: 12px 0;
        }

        .project-card h4 {
            color: var(--accent);
            margin-bottom: 8px;
        }

        .project-card .stats {
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            margin-top: 8px;
        }

        .project-card .stat {
            font-size: 13px;
            color: var(--text-secondary);
        }

        .project-card .stat strong {
            color: var(--text-primary);
        }

        /* 移动端适配 */
        @media (max-width: 600px) {
            body { padding: 12px; }
            .header { padding: 16px; }
            .header h1 { font-size: 20px; }
            .metrics { grid-template-columns: 1fr; }
            .metric-card .value { font-size: 28px; }
            .section { padding: 16px; }
            th, td { padding: 8px 6px; font-size: 13px; }
        }
    </style>
</head>
<body>
    <div class="container">
        {{ content }}
        <div class="footer">
            Generated by GitHub Insight Agent • {{ generated_at }}
        </div>
    </div>
</body>
</html>
"""


# ===========================================
# 报告提取器
# ===========================================

class ReportExtractor:
    """从 Markdown 报告中提取结构化信息"""

    def __init__(self, markdown_content: str):
        self.md = markdown_content
        self.title = "GitHub Insight Report"
        self.metrics = []
        self.sections = []

    def extract(self) -> Dict[str, Any]:
        """提取报告结构"""
        lines = self.md.split('\n')

        # 提取标题
        for line in lines:
            if line.startswith('# '):
                self.title = line[2:].strip()
                break

        # 提取关键指标
        self._extract_metrics()

        # 转换为 HTML
        content = self._convert_to_html()

        return {
            'title': self.title,
            'content': content,
        }

    def _extract_metrics(self):
        """尝试从报告中提取关键指标"""
        # 查找测试相关的指标
        test_match = re.search(r'(\d+)\s*(?:个\s*)?测试.*?(\d+)\s*(?:个\s*)?通过', self.md)
        if test_match:
            self.metrics.append({
                'label': '测试用例',
                'value': test_match.group(1),
                'type': 'success'
            })

        # 查找安全相关的指标
        security_match = re.search(r'(\d+)\s*条.*?规则', self.md)
        if security_match:
            self.metrics.append({
                'label': '安全规则',
                'value': security_match.group(1),
                'type': 'info'
            })

    def _convert_to_html(self) -> str:
        """将 Markdown 转换为 HTML"""
        # 使用 markdown 库转换
        extensions = ['tables', 'fenced_code', 'toc']
        html_content = markdown.markdown(self.md, extensions=extensions)

        # 增强 HTML 内容
        html_content = self._enhance_html(html_content)

        return html_content

    def _enhance_html(self, html: str) -> str:
        """增强 HTML 内容，添加样式类"""
        # 为表格添加包装器
        html = re.sub(
            r'<table>',
            '<div class="table-wrapper"><table>',
            html
        )
        html = re.sub(
            r'</table>',
            '</table></div>',
            html
        )

        # 为状态标签添加样式
        status_patterns = [
            (r'✅', '<span class="badge badge-success">✅</span>'),
            (r'⚠️', '<span class="badge badge-warning">⚠️</span>'),
            (r'🔴', '<span class="badge badge-danger">🔴</span>'),
            (r'🟡', '<span class="badge badge-warning">🟡</span>'),
            (r'🟢', '<span class="badge badge-success">🟢</span>'),
            (r'ℹ️', '<span class="badge badge-info">ℹ️</span>'),
        ]
        for pattern, replacement in status_patterns:
            html = html.replace(pattern, replacement)

        return html


# ===========================================
# HTML 导出器
# ===========================================

class HTMLExporter:
    """导出 HTML 报告"""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'reports'
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def export(self, markdown_content: str, output_path: Optional[str] = None) -> str:
        """
        导出 Markdown 报告为 HTML

        Args:
            markdown_content: Markdown 格式的报告内容
            output_path: 输出文件路径（可选）

        Returns:
            输出文件路径
        """
        # 提取报告结构
        extractor = ReportExtractor(markdown_content)
        data = extractor.extract()

        # 渲染 HTML
        template = Template(HTML_TEMPLATE)
        html_content = template.render(
            title=data['title'],
            content=data['content'],
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        )

        # 保存到文件
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(self.output_dir, f'report_{timestamp}.html')

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return output_path

    def export_to_string(self, markdown_content: str) -> str:
        """导出为 HTML 字符串（用于直接发送）"""
        extractor = ReportExtractor(markdown_content)
        data = extractor.extract()

        template = Template(HTML_TEMPLATE)
        return template.render(
            title=data['title'],
            content=data['content'],
            generated_at=datetime.now().strftime('%Y-%m-%d %H:%M')
        )


# ===========================================
# 便捷函数
# ===========================================

def export_markdown_to_html(markdown_content: str, output_path: Optional[str] = None) -> str:
    """便捷函数：导出 Markdown 为 HTML"""
    exporter = HTMLExporter()
    return exporter.export(markdown_content, output_path)


def export_markdown_to_html_string(markdown_content: str) -> str:
    """便捷函数：导出 Markdown 为 HTML 字符串"""
    exporter = HTMLExporter()
    return exporter.export_to_string(markdown_content)
