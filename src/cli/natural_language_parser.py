# -*- coding: utf-8 -*-
"""
自然语言意图识别模块

功能:
- 解析用户自然语言输入
- 识别意图并映射到对应命令
- 提取命令参数
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class IntentType(Enum):
    """意图类型"""
    SEARCH = "search"           # 搜索项目
    ANALYZE = "analyze"         # 分析单个项目
    REPORT = "report"           # 生成报告
    FOLLOWUP = "followup"       # 追问（已有上下文）
    UNKNOWN = "unknown"         # 未知意图


@dataclass
class ParsedIntent:
    """解析后的意图"""
    intent: IntentType
    query: str                  # 搜索关键词或项目名
    num_results: int = 5        # 期望结果数量
    sort_by: str = "stars"      # 排序方式
    time_range: Optional[str] = None  # 时间范围


class NaturalLanguageParser:
    """自然语言解析器"""

    # 时间范围关键词 (pattern -> 默认天数)
    TIME_PATTERNS = {
        "recent": [
            (r"最近 (\d+) 天", None),
            (r"过去 (\d+) 天", None),
            (r"近 (\d+) 天", None),
            (r"最近 (\d+) 周", None),
            (r"过去 (\d+) 周", None),
            (r"本周", 7),
            (r"最近一周", 7),
            (r"过去一周", 7),
            (r"本月", 30),
            (r"最近一月", 30),
            (r"过去一月", 30),
        ],
        "keywords": {
            "今天": "today",
            "昨天": "yesterday",
            "本周": "this_week",
            "上周": "last_week",
            "本月": "this_month",
            "最近": "recent",
        }
    }

    # 数量关键词
    NUMBER_PATTERNS = [
        r"前\s*(\d+)\s*个",
        r"前\s*(\d+)\s*名",
        r"排名\s*[前]?(\d+)",
        r"(\d+)\s*个项目",
        r"(\d+)\s*个仓库",
        r"最多的\s*[前]?(\d+)\s*个",
        r"top[ -]?(\d+)",
    ]

    # 排序关键词
    SORT_KEYWORDS = {
        "stars": ["star", "星", "收藏", "热门", "最受欢迎"],
        "forks": ["fork", "分支", "派生"],
        "updated": ["最新", "最近更新", "活跃", "最近创建"],
        "relevance": ["相关", "匹配"],
    }

    # 命令触发词
    INTENT_KEYWORDS = {
        IntentType.SEARCH: ["搜索", "找", "查找", "推荐", "有哪些", "介绍", "对比"],
        IntentType.ANALYZE: ["分析", "看看", "查看", "审查", "评估"],
        IntentType.REPORT: ["报告", "生成报告", "详细分析", "深度分析", "总结"],
    }

    def parse(self, user_input: str, has_context: bool = False) -> ParsedIntent:
        """
        解析用户输入

        Args:
            user_input: 用户输入文本
            has_context: 是否有之前的对话上下文

        Returns:
            ParsedIntent: 解析后的意图
        """
        text = user_input.lower().strip()

        # 检查是否是追问（简短输入且没有明确意图词）
        if has_context and len(text.split()) < 5:
            if not any(kw for keywords in self.INTENT_KEYWORDS.values() for kw in keywords if kw in text):
                return ParsedIntent(intent=IntentType.FOLLOWUP, query=user_input)

        # 提取数量
        num_results = self._extract_number(text)

        # 提取排序方式
        sort_by = self._extract_sort(text)

        # 提取时间范围
        time_range = self._extract_time_range(text)

        # 识别意图
        intent, query = self._identify_intent(user_input)

        return ParsedIntent(
            intent=intent,
            query=query,
            num_results=num_results,
            sort_by=sort_by,
            time_range=time_range,
        )

    def _identify_intent(self, text: str) -> Tuple[IntentType, str]:
        """
        识别意图类型

        Returns:
            (意图类型，查询词)
        """
        text_lower = text.lower()

        # 检查是否是 owner/repo 格式（分析单个项目）
        owner_repo_match = re.match(r"^(\w+)/(\w+)$", text.strip())
        if owner_repo_match and "/" in text and " " not in text:
            return IntentType.ANALYZE, text.strip()

        # 检查是否明确的项目名（包含 owner/repo）
        if re.search(r"\w+/\w+", text):
            match = re.search(r"(\w+/\w+)", text)
            if match:
                return IntentType.ANALYZE, match.group(1)

        # 检测组合意图：搜索 + 分析 → 报告
        has_search = any(kw in text_lower for kw in self.INTENT_KEYWORDS[IntentType.SEARCH])
        has_analyze = any(kw in text_lower for kw in self.INTENT_KEYWORDS[IntentType.ANALYZE])
        if has_search and has_analyze:
            # 使用 _extract_query 清理意图关键词和 connector
            query = self._extract_query(
                text,
                self.INTENT_KEYWORDS[IntentType.SEARCH] + self.INTENT_KEYWORDS[IntentType.ANALYZE],
            )
            return IntentType.REPORT, query

        # 检查意图关键词
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # 提取查询词（去除意图词）
                    query = self._extract_query(text, keywords)
                    return intent_type, query

        # 默认：根据输入长度和特征判断
        # 短输入 + 项目特征 → 可能是分析
        if len(text.split()) <= 3 and "/" in text:
            return IntentType.ANALYZE, text.strip()

        # 包含技术栈/领域关键词 → 搜索
        tech_keywords = [
            "python", "rust", "go", "java", "javascript", "typescript",
            "web", "ai", "ml", "framework", "库", "工具",
        ]
        if any(kw in text_lower for kw in tech_keywords):
            return IntentType.SEARCH, text.strip()

        # 默认当作搜索处理
        return IntentType.SEARCH, text.strip()

    def _extract_number(self, text: str) -> int:
        """提取用户想要的结果数量"""
        text_lower = text.lower()

        for pattern in self.NUMBER_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                num = int(match.group(1))
                return min(num, 10)  # 最多 10 个

        # 检查中文数字
        chinese_nums = {"几个": 3, "一些": 5, "多个": 5, "前十": 10, "前百": 100}
        for cn, num in chinese_nums.items():
            if cn in text:
                return num

        return 5  # 默认 5 个

    def _extract_sort(self, text: str) -> str:
        """提取排序方式"""
        text_lower = text.lower()

        for sort_type, keywords in self.SORT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return sort_type

        return "stars"  # 默认按 star 排序

    def _extract_time_range(self, text: str) -> Optional[str]:
        """提取时间范围"""
        text_lower = text.lower()

        # 检查具体天数
        for pattern, default_days in self.TIME_PATTERNS["recent"]:
            match = re.search(pattern, text_lower)
            if match:
                days = int(match.group(1)) if (match.lastindex and match.group(1)) else default_days
                return f"pushed:>={(self._days_ago(days))}"

        # 检查关键词
        for keyword, time_val in self.TIME_PATTERNS["keywords"].items():
            if keyword in text_lower:
                if keyword == "今天":
                    return f"pushed:>={self._days_ago(0)}"
                elif keyword == "昨天":
                    return f"pushed:{self._days_ago(1)}..{self._days_ago(0)}"
                elif keyword in ["本周", "最近一周"]:
                    return f"pushed:>={self._days_ago(7)}"
                elif keyword == "上周":
                    return f"pushed:{self._days_ago(14)}..{self._days_ago(7)}"
                elif keyword in ["本月", "最近一月"]:
                    return f"pushed:>={self._days_ago(30)}"

        return None

    def _days_ago(self, days: int) -> str:
        """计算 N 天前的日期字符串"""
        from datetime import datetime, timedelta
        date = datetime.now() - timedelta(days=days)
        return date.strftime("%Y-%m-%d")

    def _extract_query(self, text: str, intent_keywords: list) -> str:
        """从文本中提取查询词（去除意图词）"""
        query = text

        # 移除意图关键词
        for keyword in intent_keywords:
            query = query.replace(keyword, "")

        # 清理连接词残留
        query = query.replace("并", "")

        # 移除数量词
        for pattern in self.NUMBER_PATTERNS:
            query = re.sub(pattern, "", query)

        # 移除排序词
        for keywords in self.SORT_KEYWORDS.values():
            for kw in keywords:
                query = query.replace(kw, "")

        # 清理空白字符
        query = " ".join(query.split())

        return query if query.strip() else text.strip()


# 全局解析器实例
parser = NaturalLanguageParser()
