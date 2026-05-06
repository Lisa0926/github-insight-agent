# -*- coding: utf-8 -*-
"""
微信/飞书推送报告优化器

将完整的分析报告转换为适合即时通讯工具推送的精简格式：
- 微信：短文本 + 关键指标（不超过 2000 字）
- 飞书：富文本卡片（支持 Markdown 子集）
"""

import re


class PushReportOptimizer:
    """推送报告优化器"""

    def __init__(self, full_report: str):
        self.full_report = full_report

    def optimize_for_wechat(self, max_length: int = 1800) -> str:
        """
        优化为微信推送格式

        微信消息限制：
        - 文本消息最大 2048 字符
        - 建议控制在 1500 字符以内，确保完整显示
        """
        sections = self._extract_key_sections()
        report_parts = ["\U0001f4ca " + sections.get('title', 'GitHub 项目分析报告'), ""]
        report_parts.extend(self._build_wechat_sections(sections))
        report = '\n'.join(report_parts)

        if len(report) > max_length:
            report = report[:max_length - 3] + "..."

        return report

    def optimize_for_feishu(self, max_length: int = 3000) -> str:
        """
        优化为飞书推送格式

        飞书支持更丰富的 Markdown 格式，但仍需控制长度
        """
        sections = self._extract_key_sections()
        report_parts = ["**" + sections.get('title', 'GitHub 项目分析报告') + "**", ""]
        report_parts.extend(self._build_feishu_sections(sections))
        report = '\n'.join(report_parts)

        if len(report) > max_length:
            report = report[:max_length - 3] + "..."

        return report

    def _build_wechat_sections(self, sections: dict) -> list:
        """Build WeChat-formatted section parts from extracted sections."""
        parts = []
        if sections.get('metrics'):
            parts.append("\U0001f4c8 关键指标")
            for m in sections['metrics']:
                parts.append(f"  • {m['label']}: {m['value']}")
            parts.append("")

        if sections.get('findings'):
            parts.append("\U0001f4a1 核心发现")
            for i, finding in enumerate(sections['findings'][:3], 1):
                parts.append(f"  {i}. {finding}")
            parts.append("")

        if sections.get('competitors'):
            parts.append("\U0001f525 竞品动态")
            for comp in sections['competitors'][:2]:
                parts.append(f"  • {comp}")
            parts.append("")

        if sections.get('actions'):
            parts.append("\U0001f4cb 行动建议")
            for i, action in enumerate(sections['actions'][:3], 1):
                parts.append(f"  {i}. {action}")
            parts.append("")

        if sections.get('html_url'):
            parts.append(f"\U0001f4c4 查看完整报告: {sections['html_url']}")

        return parts

    def _build_feishu_sections(self, sections: dict) -> list:
        """Build Feishu-formatted section parts from extracted sections."""
        parts = []
        if sections.get('metrics'):
            parts.append("**\U0001f4c8 关键指标**")
            parts.append("| 指标 | 数值 |")
            parts.append("|------|------|")
            for m in sections['metrics']:
                parts.append(f"| {m['label']} | {m['value']} |")
            parts.append("")

        if sections.get('findings'):
            parts.append("**\U0001f4a1 核心发现**")
            for finding in sections['findings'][:5]:
                parts.append(f"• {finding}")
            parts.append("")

        if sections.get('competitors'):
            parts.append("**\U0001f525 竞品动态**")
            for comp in sections['competitors'][:3]:
                parts.append(f"• {comp}")
            parts.append("")

        if sections.get('actions'):
            parts.append("**\U0001f4cb 行动建议**")
            for i, action in enumerate(sections['actions'][:5], 1):
                parts.append(f"{i}. {action}")
            parts.append("")

        if sections.get('html_url'):
            parts.append(f"[📄 查看完整报告]({sections['html_url']})")

        return parts

    def _extract_key_sections(self) -> dict:
        """提取报告中的关键部分"""
        content = self.full_report
        return {
            'title': self._extract_title(content),
            'metrics': self._extract_metrics(content),
            'findings': self._extract_findings(content),
            'competitors': self._extract_competitors(content),
            'actions': self._extract_actions(content),
            'html_url': None,
        }

    def _extract_title(self, content: str) -> str:
        """Extract the title (first # heading)."""
        title_match = re.search(r'# (.+?)(?:\n|$)', content)
        return title_match.group(1).strip() if title_match else ''

    def _extract_metrics(self, content: str) -> list:
        """Extract key metrics (numeric patterns with descriptions)."""
        metrics = []
        metric_patterns = [
            (r'(\d+)\s*(?:个\s*)?测试.*?(\d+)\s*(?:个\s*)?通过', '测试用例',
             lambda g: f"{g[0]} 个（{g[1]} 通过）"),
            (r'(\d+)\s*条.*?规则', '安全规则',
             lambda g: f"{g[0]} 条"),
            (r'(\d+)\s*\+\s*(\d+)', '代码变更',
             lambda g: f"+{g[0]} -{g[1]}"),
        ]

        for item in metric_patterns:
            if len(item) == 3:
                pattern, label, fmt_value = item
                matches = re.finditer(pattern, content)
                for match in matches:
                    groups = match.groups()
                    if len(groups) == item[0].count('(') + 1:
                        metrics.append({'label': label, 'value': fmt_value(groups)})
        return metrics

    def _extract_findings(self, content: str) -> list:
        """Extract core findings from summary/discovery sections."""
        findings = []
        for keyword in ['总结', '发现', '洞察', '结论']:
            pattern = rf'##? .*?{keyword}.*?\n(.*?)(?=\n##? |\Z)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                for line in match.group(1).strip().split('\n'):
                    line = line.strip().lstrip('•-1234567890. ')
                    if line and len(line) > 10:
                        findings.append(line)
        return findings

    def _extract_competitors(self, content: str) -> list:
        """Extract competitor dynamics from competitor section."""
        competitors = []
        competitor_section = re.search(
            r'##? .?竞品.*?\n(.*?)(?=\n##? |\Z)',
            content, re.DOTALL,
        )
        if competitor_section:
            comp_keywords = {'CodeRabbit', 'Qodo', 'Sonar', 'Copilot', 'Sweep'}
            for line in competitor_section.group(1).split('\n'):
                line = line.strip()
                if line and any(kw in line for kw in comp_keywords):
                    competitors.append(line)
        return competitors

    def _extract_actions(self, content: str) -> list:
        """Extract action items from action/suggestion sections."""
        actions = []
        for keyword in ['行动', '建议', '待办', 'TODO', '下一步']:
            pattern = rf'##? .?{keyword}.*?\n(.*?)(?=\n##? |\Z)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                for line in match.group(1).strip().split('\n'):
                    line = line.strip().lstrip('•-1234567890. ')
                    if line and len(line) > 10:
                        actions.append(line)
        return actions


# ===========================================
# 便捷函数
# ===========================================

def optimize_for_wechat(report_content: str, max_length: int = 1800) -> str:
    """便捷函数：优化为微信推送格式"""
    optimizer = PushReportOptimizer(report_content)
    return optimizer.optimize_for_wechat(max_length)


def optimize_for_feishu(report_content: str, max_length: int = 3000) -> str:
    """便捷函数：优化为飞书推送格式"""
    optimizer = PushReportOptimizer(report_content)
    return optimizer.optimize_for_feishu(max_length)
