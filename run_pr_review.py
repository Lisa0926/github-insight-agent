#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR 审查工具 - 独立页面

用法:
    python run_pr_review.py [--port 8001]
"""

import argparse
import asyncio
from src.tools.pr_review_tool import review_pull_request, _parse_diff, PRReviewer
from src.core.config_manager import ConfigManager


def get_pr_review_html() -> str:
    """生成 PR 审查页面 HTML"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PR 自动审查 - GitHub Insight Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 10px;
            font-size: 2rem;
        }
        .subtitle {
            color: rgba(255,255,255,0.8);
            text-align: center;
            margin-bottom: 30px;
        }
        .back-link {
            display: inline-block;
            color: white;
            text-decoration: none;
            margin-bottom: 20px;
            padding: 8px 16px;
            background: rgba(255,255,255,0.2);
            border-radius: 6px;
        }
        .back-link:hover { background: rgba(255,255,255,0.3); }
        .form-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            font-weight: 600;
            margin-bottom: 6px;
            color: #333;
        }
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
        }
        .form-group textarea {
            min-height: 80px;
            resize: vertical;
        }
        .form-group input[type="checkbox"] {
            width: auto;
            margin-right: 8px;
        }
        .checkbox-label {
            display: flex;
            align-items: center;
            cursor: pointer;
        }
        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
        }
        .btn:hover { background: #5a6fd6; }
        .btn:disabled { background: #ccc; cursor: not-allowed; }
        .result-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-top: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            display: none;
        }
        .result-card.show { display: block; }
        .result-header {
            border-bottom: 1px solid #eee;
            padding-bottom: 16px;
            margin-bottom: 16px;
        }
        .result-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
            margin: 16px 0;
        }
        .stat-item {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #667eea;
        }
        .stat-label {
            font-size: 0.85rem;
            color: #666;
            margin-top: 4px;
        }
        .summary-box {
            background: #f0f4ff;
            border-left: 4px solid #667eea;
            padding: 16px;
            margin: 16px 0;
            border-radius: 0 6px 6px 0;
        }
        .issue-list {
            margin: 16px 0;
        }
        .issue-item {
            border: 1px solid #eee;
            border-radius: 6px;
            padding: 12px;
            margin-bottom: 12px;
        }
        .issue-header {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }
        .severity {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .severity-critical { background: #fee; color: #c00; }
        .severity-high { background: #fed; color: #f60; }
        .severity-medium { background: #fef9e7; color: #b78900; }
        .severity-low { background: #e8f5e9; color: #2e7d32; }
        .issue-message {
            color: #333;
            font-size: 0.95rem;
        }
        .issue-suggestion {
            color: #666;
            font-size: 0.9rem;
            margin-top: 8px;
            padding-left: 12px;
            border-left: 2px solid #667eea;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.2rem;
            display: none;
        }
        .loading.show { display: block; }
        .recommendation {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            margin-top: 16px;
        }
        .rec-approve { background: #d4edda; color: #155724; }
        .rec-comment { background: #fff3cd; color: #856404; }
        .rec-changes { background: #f8d7da; color: #721c24; }
        pre {
            background: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-break: break-word;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-link">← 返回仪表盘</a>
        <h1>🔍 PR 自动审查</h1>
        <p class="subtitle">基于 AI 的代码变更分析和问题检测</p>

        <div class="form-card">
            <div class="form-group">
                <label for="prTitle">PR 标题</label>
                <input type="text" id="prTitle" placeholder="例如：feat: Add user authentication">
            </div>
            <div class="form-group">
                <label for="prDescription">PR 描述（可选）</label>
                <textarea id="prDescription" placeholder="描述本次 PR 的主要变更..."></textarea>
            </div>
            <div class="form-group">
                <label for="diffContent">Git Diff 内容</label>
                <textarea id="diffContent" style="min-height: 200px; font-family: monospace;" placeholder="粘贴 git diff 输出...

示例:
diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,5 +1,6 @@
 def hello():
-    return \"Hello\"
+    password = \"secret\"
+    return \"Hello World\"
"></textarea>
            </div>
            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="useLlm" checked>
                    使用 LLM 增强审查（更深入的代码分析）
                </label>
            </div>
            <button class="btn" onclick="reviewPR()">开始审查</button>
        </div>

        <div class="loading" id="loading">
            ⏳ 正在分析代码变更，请稍候...
        </div>

        <div class="result-card" id="resultCard">
            <div class="result-header">
                <div class="result-title" id="resultTitle">审查报告</div>
                <div id="recommendationBadge"></div>
            </div>

            <div class="stats-grid" id="statsGrid">
                <!-- 动态填充 -->
            </div>

            <div class="summary-box">
                <strong>📝 审查摘要：</strong>
                <p id="summaryText" style="margin-top: 8px;"></p>
            </div>

            <div id="issuesSection">
                <h3 style="margin-bottom: 12px;">🔍 检测到的问题</h3>
                <div class="issue-list" id="issueList">
                    <!-- 动态填充 -->
                </div>
            </div>

            <div id="llmSection" style="display: none;">
                <h3 style="margin-bottom: 12px;">🤖 AI 审查意见</h3>
                <div id="llmContent"></div>
            </div>
        </div>
    </div>

    <script>
        async function reviewPR() {
            const prTitle = document.getElementById('prTitle').value.trim();
            const prDescription = document.getElementById('prDescription').value.trim();
            const diffContent = document.getElementById('diffContent').value.trim();
            const useLlm = document.getElementById('useLlm').checked;

            if (!prTitle) {
                alert('请输入 PR 标题');
                return;
            }
            if (!diffContent) {
                alert('请输入 Git Diff 内容');
                return;
            }

            // 显示加载状态
            document.getElementById('loading').classList.add('show');
            document.getElementById('resultCard').classList.remove('show');
            document.querySelector('.btn').disabled = true;

            try {
                const params = new URLSearchParams({
                    pr_title: prTitle,
                    pr_description: prDescription || '',
                    diff_content: diffContent,
                    use_llm: useLlm,
                });

                const response = await fetch('/api/pr/review?' + params.toString(), {
                    method: 'POST',
                });

                const result = await response.json();

                if (response.ok) {
                    displayResult(result);
                } else {
                    alert('审查失败：' + result.detail);
                }
            } catch (error) {
                alert('请求失败：' + error.message);
            } finally {
                document.getElementById('loading').classList.remove('show');
                document.querySelector('.btn').disabled = false;
            }
        }

        function displayResult(result) {
            // 标题
            document.getElementById('resultTitle').textContent = '审查报告：' + result.pr_title;

            // 推荐徽章
            const recMap = {
                'approve': { class: 'rec-approve', text: '✅ 建议合并' },
                'comment': { class: 'rec-comment', text: '📝 有建议但不阻碍' },
                'request_changes': { class: 'rec-changes', text: '🔧 需要修改' },
            };
            const rec = recMap[result.approval_recommendation] || recMap['comment'];
            const badge = document.getElementById('recommendationBadge');
            badge.className = 'recommendation ' + rec.class;
            badge.textContent = rec.text;

            // 统计
            const stats = result.stats;
            const statsHtml = `
                <div class="stat-item">
                    <div class="stat-value">${stats.total_files}</div>
                    <div class="stat-label">变更文件</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">+${stats.total_additions}</div>
                    <div class="stat-label">新增行数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">-${stats.total_deletions}</div>
                    <div class="stat-label">删除行数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${stats.issues_found}</div>
                    <div class="stat-label">发现问题</div>
                </div>
            `;
            document.getElementById('statsGrid').innerHTML = statsHtml;

            // 摘要
            document.getElementById('summaryText').textContent = result.summary;

            // 问题列表 - 需要从完整报告获取
            // 注意：当前 API 返回的是简化报告，如需显示详细问题列表需要修改 API
            document.getElementById('issueList').innerHTML = `
                <div class="issue-item">
                    <div class="issue-message">
                        ℹ️ 详细问题列表需要在完整审查报告中查看。
                        当前显示的是摘要信息。
                    </div>
                </div>
            `;

            // 显示结果
            document.getElementById('resultCard').classList.add('show');
        }
    </script>
</body>
</html>
"""


def run_pr_review_server(host: str = "0.0.0.0", port: int = 8001):
    """
    启动 PR 审查独立服务器

    Args:
        host: 监听地址
        port: 端口号
    """
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse
    from fastapi import Query
    import asyncio

    app = FastAPI(title="PR Review Tool")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=get_pr_review_html())

    @app.post("/api/pr/review")
    async def review_pr(
        pr_title: str = Query(...),
        pr_description: str = Query(default=""),
        diff_content: str = Query(...),
        use_llm: bool = Query(default=True),
    ):
        """审查 PR"""
        try:
            config = ConfigManager()
            reviewer = PRReviewer(config=config)
            changes = _parse_diff(diff_content)

            report = await reviewer.review(
                pr_title=pr_title,
                pr_description=pr_description,
                changes=changes,
                use_llm=use_llm,
            )

            approval = report.get("llm_review", {}).get("approval_recommendation", "comment")

            return {
                "pr_title": report["pr_title"],
                "stats": report["stats"],
                "summary": report["summary"],
                "issues_count": report["stats"]["issues_found"],
                "approval_recommendation": approval,
                "full_report": report,
            }

        except Exception as e:
            from src.core.logger import get_logger
            get_logger(__name__).error(f"PR 审查失败：{e}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=str(e))

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PR 自动审查工具")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8001, help="端口号")
    args = parser.parse_args()

    print("=" * 60)
    print("🔍 PR 自动审查工具")
    print("=" * 60)
    print(f"访问地址：http://localhost:{args.port}")
    print("=" * 60)

    run_pr_review_server(host=args.host, port=args.port)
