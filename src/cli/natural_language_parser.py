# -*- coding: utf-8 -*-
"""
Natural Language Intent Recognition Module

Features:
- Parse user natural language input
- Recognize intent and map to corresponding commands
- Extract command parameters
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class IntentType(Enum):
    """Intent type"""
    SEARCH = "search"           # Search projects
    ANALYZE = "analyze"         # Analyze a single project
    REPORT = "report"           # Generate report
    FOLLOWUP = "followup"       # Follow-up (existing context)
    UNKNOWN = "unknown"         # Unknown intent


@dataclass
class ParsedIntent:
    """Parsed intent result"""
    intent: IntentType
    query: str                  # Search keyword or project name
    num_results: int = 5        # Expected number of results
    sort_by: str = "stars"      # Sort method
    time_range: Optional[str] = None  # Time range


class NaturalLanguageParser:
    """Natural language parser"""

    # Time range keywords (pattern -> default days)
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

    # Number keywords
    NUMBER_PATTERNS = [
        r"前\s*(\d+)\s*个",
        r"前\s*(\d+)\s*名",
        r"排名\s*[前]?(\d+)",
        r"(\d+)\s*个项目",
        r"(\d+)\s*个仓库",
        r"最多的\s*[前]?(\d+)\s*个",
        r"top[ -]?(\d+)",
    ]

    # Sort keywords
    SORT_KEYWORDS = {
        "stars": ["star", "星", "收藏", "热门", "最受欢迎"],
        "forks": ["fork", "分支", "派生"],
        "updated": ["最新", "最近更新", "活跃", "最近创建"],
        "relevance": ["相关", "匹配"],
    }

    # Command trigger words
    INTENT_KEYWORDS = {
        IntentType.SEARCH: ["搜索", "找", "查找", "推荐", "有哪些", "介绍", "对比"],
        IntentType.ANALYZE: ["分析", "看看", "查看", "审查", "评估"],
        IntentType.REPORT: ["报告", "生成报告", "详细分析", "深度分析", "总结"],
    }

    def parse(self, user_input: str, has_context: bool = False) -> ParsedIntent:
        """
        Parse user input

        Args:
            user_input: User input text
            has_context: Whether there is previous conversation context

        Returns:
            ParsedIntent: Parsed intent result
        """
        text = user_input.lower().strip()

        # Check if this is a follow-up (short input without explicit intent keywords)
        if has_context and len(text.split()) < 5:
            if not any(kw for keywords in self.INTENT_KEYWORDS.values() for kw in keywords if kw in text):
                return ParsedIntent(intent=IntentType.FOLLOWUP, query=user_input)

        # Extract number
        num_results = self._extract_number(text)

        # Extract sort method
        sort_by = self._extract_sort(text)

        # Extract time range
        time_range = self._extract_time_range(text)

        # Recognize intent
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
        Identify intent type

        Returns:
            (Intent type, query term)
        """
        text_lower = text.lower()

        # Check if it's in owner/repo format (analyze a single project)
        owner_repo_match = re.match(r"^(\w+)/(\w+)$", text.strip())
        if owner_repo_match and "/" in text and " " not in text:
            return IntentType.ANALYZE, text.strip()

        # Check if there's an explicit project name (contains owner/repo)
        if re.search(r"\w+/\w+", text):
            match = re.search(r"(\w+/\w+)", text)
            if match:
                return IntentType.ANALYZE, match.group(1)

        # Detect combined intent: search + analyze -> report
        has_search = any(kw in text_lower for kw in self.INTENT_KEYWORDS[IntentType.SEARCH])
        has_analyze = any(kw in text_lower for kw in self.INTENT_KEYWORDS[IntentType.ANALYZE])
        if has_search and has_analyze:
            # Use _extract_query to clean up intent keywords and connectors
            query = self._extract_query(
                text,
                self.INTENT_KEYWORDS[IntentType.SEARCH] + self.INTENT_KEYWORDS[IntentType.ANALYZE],
            )
            return IntentType.REPORT, query

        # Check intent keywords
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    # Extract query term (remove intent keywords)
                    query = self._extract_query(text, keywords)
                    return intent_type, query

        # Default: judge based on input length and features
        # Short input + project pattern -> likely analyze
        if len(text.split()) <= 3 and "/" in text:
            return IntentType.ANALYZE, text.strip()

        # Contains tech stack/domain keywords -> search
        tech_keywords = [
            "python", "rust", "go", "java", "javascript", "typescript",
            "web", "ai", "ml", "framework", "库", "工具",
        ]
        if any(kw in text_lower for kw in tech_keywords):
            return IntentType.SEARCH, text.strip()

        # Default to treating as search
        return IntentType.SEARCH, text.strip()

    def _extract_number(self, text: str) -> int:
        """Extract desired number of results from user input"""
        text_lower = text.lower()

        for pattern in self.NUMBER_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                num = int(match.group(1))
                return min(num, 10)  # Maximum 10

        # Check Chinese numerals
        chinese_nums = {"几个": 3, "一些": 5, "多个": 5, "前十": 10, "前百": 100}
        for cn, num in chinese_nums.items():
            if cn in text:
                return num

        return 5  # Default 5

    def _extract_sort(self, text: str) -> str:
        """Extract sort method"""
        text_lower = text.lower()

        for sort_type, keywords in self.SORT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return sort_type

        return "stars"  # Default sort by star

    def _extract_time_range(self, text: str) -> Optional[str]:
        """Extract time range"""
        text_lower = text.lower()

        # Check specific number of days
        for pattern, default_days in self.TIME_PATTERNS["recent"]:
            match = re.search(pattern, text_lower)
            if match:
                days = int(match.group(1)) if (match.lastindex and match.group(1)) else default_days
                return f"pushed:>={(self._days_ago(days))}"

        # Check keywords
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
        """Calculate date string N days ago"""
        from datetime import datetime, timedelta
        date = datetime.now() - timedelta(days=days)
        return date.strftime("%Y-%m-%d")

    def _extract_query(self, text: str, intent_keywords: list) -> str:
        """Extract query term from text (remove intent keywords)"""
        query = text

        # Remove intent keywords
        for keyword in intent_keywords:
            query = query.replace(keyword, "")

        # Clean up connector residue
        query = query.replace("并", "")

        # Remove number terms
        for pattern in self.NUMBER_PATTERNS:
            query = re.sub(pattern, "", query)

        # Remove sort terms
        for keywords in self.SORT_KEYWORDS.values():
            for kw in keywords:
                query = query.replace(kw, "")

        # Clean up whitespace
        query = " ".join(query.split())

        return query if query.strip() else text.strip()


# Global parser instance
parser = NaturalLanguageParser()
