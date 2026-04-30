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
        lines = self.full_report.split('\n')

        # 提取关键部分
        sections = self._extract_key_sections(lines)

        # 构建精简报告
        report_parts = []

        # 标题
        title = sections.get('title', 'GitHub 项目分析报告')
        report_parts.append(f"📊 {title}")
        report_parts.append("")

        # 关键指标
        metrics = sections.get('metrics', [])
        if metrics:
            report_parts.append("📈 关键指标")
            for m in metrics:
                report_parts.append(f"  • {m['label']}: {m['value']}")
            report_parts.append("")

        # 核心发现
        findings = sections.get('findings', [])
        if findings:
            report_parts.append("💡 核心发现")
            for i, finding in enumerate(findings[:3], 1):  # 最多取 3 条
                report_parts.append(f"  {i}. {finding}")
            report_parts.append("")

        # 竞品动态（如果有）
        competitors = sections.get('competitors', [])
        if competitors:
            report_parts.append("🔥 竞品动态")
            for comp in competitors[:2]:  # 最多取 2 条
                report_parts.append(f"  • {comp}")
            report_parts.append("")

        # 行动建议
        actions = sections.get('actions', [])
        if actions:
            report_parts.append("📋 行动建议")
            for i, action in enumerate(actions[:3], 1):  # 最多取 3 条
                report_parts.append(f"  {i}. {action}")
            report_parts.append("")

        # 完整报告链接（如果有 HTML 版本）
        if sections.get('html_url'):
            report_parts.append(f"📄 查看完整报告: {sections['html_url']}")

        # 拼接并截断
        report = '\n'.join(report_parts)

        # 确保不超过最大长度
        if len(report) > max_length:
            report = report[:max_length - 3] + "..."

        return report

    def optimize_for_feishu(self, max_length: int = 3000) -> str:
        """
        优化为飞书推送格式

        飞书支持更丰富的 Markdown 格式，但仍需控制长度
        """
        lines = self.full_report.split('\n')
        sections = self._extract_key_sections(lines)

        report_parts = []

        # 标题
        title = sections.get('title', 'GitHub 项目分析报告')
        report_parts.append(f"**{title}**")
        report_parts.append("")

        # 关键指标（用表格形式）
        metrics = sections.get('metrics', [])
        if metrics:
            report_parts.append("**📈 关键指标**")
            report_parts.append("| 指标 | 数值 |")
            report_parts.append("|------|------|")
            for m in metrics:
                report_parts.append(f"| {m['label']} | {m['value']} |")
            report_parts.append("")

        # 核心发现
        findings = sections.get('findings', [])
        if findings:
            report_parts.append("**💡 核心发现**")
            for finding in findings[:5]:  # 最多取 5 条
                report_parts.append(f"• {finding}")
            report_parts.append("")

        # 竞品动态
        competitors = sections.get('competitors', [])
        if competitors:
            report_parts.append("**🔥 竞品动态**")
            for comp in competitors[:3]:  # 最多取 3 条
                report_parts.append(f"• {comp}")
            report_parts.append("")

        # 行动建议
        actions = sections.get('actions', [])
        if actions:
            report_parts.append("**📋 行动建议**")
            for i, action in enumerate(actions[:5], 1):  # 最多取 5 条
                report_parts.append(f"{i}. {action}")
            report_parts.append("")

        # 完整报告链接
        if sections.get('html_url'):
            report_parts.append(f"[📄 查看完整报告]({sections['html_url']})")

        report = '\n'.join(report_parts)

        if len(report) > max_length:
            report = report[:max_length - 3] + "..."

        return report

    def _extract_key_sections(self, lines: list) -> dict:
        """提取报告中的关键部分"""
        result = {
            'title': '',
            'metrics': [],
            'findings': [],
            'competitors': [],
            'actions': [],
            'html_url': None,
        }

        content = '\n'.join(lines)

        # 提取标题
        title_match = re.search(r'# (.+?)(?:\n|$)', content)
        if title_match:
            result['title'] = title_match.group(1).strip()

        # 提取关键指标（寻找数字 + 描述的 pattern）
        metric_patterns = [
            r'(\d+)\s*(?:个\s*)?测试.*?(\d+)\s*(?:个\s*)?通过',
            r'(\d+)\s*条.*?规则',
            r'(\d+)\s*个.*?项目',
            r'(\d+)\s*\+\s*(\d+)',  # 如 "176 +18"
        ]

        for pattern in metric_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                groups = match.groups()
                if len(groups) == 2:
                    if '测试' in match.group(0):
                        result['metrics'].append({
                            'label': '测试用例',
                            'value': f"{groups[0]} 个（{groups[1]} 通过）"
                        })
                    elif '+' in match.group(0):
                        result['metrics'].append({
                            'label': '代码变更',
                            'value': f"+{groups[0]} -{groups[1]}"
                        })
                elif len(groups) == 1:
                    if '规则' in match.group(0):
                        result['metrics'].append({
                            'label': '安全规则',
                            'value': f"{groups[0]} 条"
                        })

        # 提取核心发现（寻找"总结"、"发现"、"洞察"等关键词后的内容）
        finding_keywords = ['总结', '发现', '洞察', '结论']
        for keyword in finding_keywords:
            pattern = rf'##? .*?{keyword}.*?\n(.*?)(?=\n##? |\Z)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                finding_text = match.group(1).strip()
                # 拆分为单独的发现
                for line in finding_text.split('\n'):
                    line = line.strip().lstrip('•-1234567890. ')
                    if line and len(line) > 10:
                        result['findings'].append(line)

        # 提取竞品动态
        competitor_section = re.search(
            r'##? .?竞品.*?\n(.*?)(?=\n##? |\Z)',
            content, re.DOTALL
        )
        if competitor_section:
            comp_text = competitor_section.group(1)
            for line in comp_text.split('\n'):
                line = line.strip()
                if line and any(kw in line for kw in ['CodeRabbit', 'Qodo', 'Sonar', 'Copilot', 'Sweep']):
                    result['competitors'].append(line)

        # 提取行动建议
        action_keywords = ['行动', '建议', '待办', 'TODO', '下一步']
        for keyword in action_keywords:
            pattern = rf'##? .?{keyword}.*?\n(.*?)(?=\n##? |\Z)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                action_text = match.group(1).strip()
                for line in action_text.split('\n'):
                    line = line.strip().lstrip('•-1234567890. ')
                    if line and len(line) > 10:
                        result['actions'].append(line)

        return result


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
