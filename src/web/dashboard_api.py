# -*- coding: utf-8 -*-
"""
Web 可视化仪表盘 API

功能:
- 提供 REST API 端点，返回项目分析数据
- 支持雷达图、统计卡片、历史记录查询
- 轻量级 FastAPI 实现

API 端点:
- GET /api/projects - 获取项目列表
- GET /api/projects/{owner}/{repo} - 获取单个项目详情
- GET /api/projects/{owner}/{repo}/quality - 获取质量评分
- GET /api/dashboard/summary - 获取仪表盘摘要
- GET /api/radar - 获取竞品对比雷达图数据
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.config_manager import ConfigManager
from src.core.logger import get_logger
from src.core.agentscope_persistent_memory import PersistentMemory
from src.tools.github_tool import GitHubTool
from src.tools.code_quality_tool import CodeQualityScorer
from src.tools.pr_review_tool import review_pull_request, PRReviewer, CodeChange

logger = get_logger(__name__)

# ===========================================
# 输入验证
# ===========================================
# GitHub owner/repo 仅允许字母、数字、连字符、下划线和点
_OWNER_REPO_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,38}$')


def _validate_identifier(value: str, field_name: str) -> str:
    """验证 owner/repo 等标识符，防止注入攻击"""
    if not value:
        raise HTTPException(status_code=400, detail=f"{field_name} 不能为空")
    if len(value) > 39:
        raise HTTPException(status_code=400, detail=f"{field_name} 过长（最大 39 字符）")
    if not _OWNER_REPO_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"{field_name} 包含非法字符")
    return value

# ===========================================
# FastAPI 应用
# ===========================================

app = FastAPI(
    title="GitHub Insight Agent Dashboard",
    description="GitHub 项目分析可视化仪表盘 API",
    version="1.0.0",
)

# CORS 配置 - 限制为本地来源，避免通配符带来的安全风险
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ===========================================
# 数据模型
# ===========================================


class ProjectSummary(BaseModel):
    """项目摘要"""

    full_name: str
    stars: int
    forks: int
    language: str
    description: str
    topics: List[str]
    quality_score: Optional[float] = None
    security_score: Optional[float] = None
    analyzed_at: Optional[str] = None


class QualityReport(BaseModel):
    """质量评估报告"""

    quality_score: float
    security_score: float
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    assessment: str


class PRReviewRequest(BaseModel):
    """PR 审查请求"""

    pr_title: str
    pr_description: str = ""
    diff_content: str
    use_llm: bool = True


class PRReviewReport(BaseModel):
    """PR 审查报告"""

    pr_title: str
    stats: Dict[str, Any]
    summary: str
    issues_count: int
    approval_recommendation: str


class RadarChartData(BaseModel):
    """雷达图数据"""

    dimensions: List[str]
    gia_scores: List[float]
    competitor_scores: List[List[float]]
    competitor_names: List[str]


class DashboardSummary(BaseModel):
    """仪表盘摘要"""

    total_projects: int
    avg_quality_score: float
    avg_security_score: float
    recent_analyses: List[ProjectSummary]


# ===========================================
# 内存存储（演示用，后续可替换为数据库）
# ===========================================

_analyzed_projects: Dict[str, Dict[str, Any]] = {}
_quality_reports: Dict[str, Dict[str, Any]] = {}


# ===========================================
# API 端点
# ===========================================


@app.get("/")
async def root() -> HTMLResponse:
    """根页面 - 简单的 HTML 仪表盘"""
    return HTMLResponse(
        content=_get_dashboard_html(),
        media_type="text/html",
    )


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    """获取仪表盘摘要"""
    total = len(_analyzed_projects)

    # 计算平均评分
    quality_scores = [
        p.get("quality_score", 0)
        for p in _analyzed_projects.values()
        if p.get("quality_score")
    ]
    security_scores = [
        p.get("security_score", 0)
        for p in _analyzed_projects.values()
        if p.get("security_score")
    ]

    recent = list(_analyzed_projects.values())[-5:]

    return DashboardSummary(
        total_projects=total,
        avg_quality_score=sum(quality_scores) / max(len(quality_scores), 1),
        avg_security_score=sum(security_scores) / max(len(security_scores), 1),
        recent_analyses=[
            ProjectSummary(
                full_name=p.get("full_name", ""),
                stars=p.get("stars", 0),
                forks=p.get("forks", 0),
                language=p.get("language", ""),
                description=p.get("description", "")[:100],
                topics=p.get("topics", []),
                quality_score=p.get("quality_score"),
                security_score=p.get("security_score"),
                analyzed_at=p.get("analyzed_at"),
            )
            for p in recent
        ],
    )


@app.get("/api/projects", response_model=List[ProjectSummary])
async def list_projects(
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
):
    """获取已分析的项目列表"""
    projects = list(_analyzed_projects.values())[-limit:]
    return [
        ProjectSummary(
            full_name=p.get("full_name", ""),
            stars=p.get("stars", 0),
            forks=p.get("forks", 0),
            language=p.get("language", ""),
            description=p.get("description", "")[:100],
            topics=p.get("topics", []),
            quality_score=p.get("quality_score"),
            security_score=p.get("security_score"),
            analyzed_at=p.get("analyzed_at"),
        )
        for p in projects
    ]


@app.post("/api/projects/analyze")
async def analyze_project(owner: str, repo: str, use_llm: bool = True):
    """
    分析指定 GitHub 项目

    Args:
        owner: 仓库所有者
        repo: 仓库名称
        use_llm: 是否使用 LLM 增强评估
    """
    try:
        # 输入验证 - 防止注入
        owner = _validate_identifier(owner, "owner")
        repo = _validate_identifier(repo, "repo")

        config = ConfigManager()
        github_tool = GitHubTool(config=config)

        # 获取项目摘要
        summary = github_tool.get_project_summary(owner, repo)

        # 评估代码质量
        scorer = CodeQualityScorer(config=config)
        quality_result = await scorer.evaluate(
            readme_content=summary.get("cleaned_readme_text", ""),
            repo_info={
                "full_name": summary["full_name"],
                "stars": summary["stars"],
                "forks": summary["forks"],
                "language": summary["language"],
                "topics": summary["topics"],
                "license": summary.get("license", "Unknown"),
            },
            use_llm=use_llm,
        )

        # 存储结果
        key = f"{owner}/{repo}"
        _analyzed_projects[key] = {
            **summary,
            "quality_score": quality_result["quality_score"],
            "security_score": quality_result["security_score"],
            "analyzed_at": datetime.now().isoformat(),
        }
        _quality_reports[key] = quality_result

        return {
            "success": True,
            "project": _analyzed_projects[key],
            "quality": quality_result,
        }

    except Exception as e:
        logger.error(f"分析失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{owner}/{repo}", response_model=ProjectSummary)
async def get_project(owner: str, repo: str):
    """获取指定项目的分析结果"""
    key = f"{owner}/{repo}"
    if key not in _analyzed_projects:
        raise HTTPException(status_code=404, detail="项目未分析")

    project = _analyzed_projects[key]
    return ProjectSummary(
        full_name=project.get("full_name", ""),
        stars=project.get("stars", 0),
        forks=project.get("forks", 0),
        language=project.get("language", ""),
        description=project.get("description", "")[:100],
        topics=project.get("topics", []),
        quality_score=project.get("quality_score"),
        security_score=project.get("security_score"),
        analyzed_at=project.get("analyzed_at"),
    )


@app.get("/api/projects/{owner}/{repo}/quality", response_model=QualityReport)
async def get_quality_report(owner: str, repo: str):
    """获取项目的质量评估报告"""
    key = f"{owner}/{repo}"
    if key not in _quality_reports:
        raise HTTPException(status_code=404, detail="质量报告不存在")

    report = _quality_reports[key]
    return QualityReport(
        quality_score=report["quality_score"],
        security_score=report["security_score"],
        overall_score=report["overall_score"],
        strengths=report.get("strengths", []),
        weaknesses=report.get("weaknesses", []),
        recommendations=report.get("recommendations", []),
        assessment=report.get("assessment", ""),
    )


@app.get("/api/radar", response_model=RadarChartData)
async def get_radar_data():
    """
    获取竞品对比雷达图数据

    维度:
    - AI 深度分析
    - 代码质量
    - 测试能力
    - 可视化
    - PR 工作流
    - 部署灵活性
    - 成本效益
    - 中文支持
    """
    # GIA 评分（基于实际能力）
    gia_scores = [5, 3, 1, 2, 1, 5, 5, 5]  # 当前 GIA 能力

    # 竞品评分
    competitors = {
        "CodeRabbit": [4, 3, 1, 2, 5, 1, 3, 1],
        "Qodo": [4, 4, 5, 2, 3, 1, 3, 1],
        "SonarCloud": [2, 5, 1, 4, 2, 2, 3, 1],
        "LinearB": [1, 1, 1, 5, 1, 2, 2, 1],
    }

    return RadarChartData(
        dimensions=[
            "AI 深度分析",
            "代码质量",
            "测试能力",
            "可视化",
            "PR 工作流",
            "部署灵活性",
            "成本效益",
            "中文支持",
        ],
        gia_scores=gia_scores,
        competitor_scores=list(competitors.values()),
        competitor_names=list(competitors.keys()),
    )


@app.post("/api/pr/review", response_model=PRReviewReport)
async def review_pr(request: PRReviewRequest):
    """
    审查 Pull Request 代码变更

    Args:
        pr_title: PR 标题
        pr_description: PR 描述
        diff_content: git diff 内容
        use_llm: 是否使用 LLM 增强

    Returns:
        PR 审查报告
    """
    try:
        config = ConfigManager()
        reviewer = PRReviewer(config=config)

        # 解析 diff
        from src.tools.pr_review_tool import _parse_diff
        changes = _parse_diff(request.diff_content)

        # 执行审查
        report = await reviewer.review(
            pr_title=request.pr_title,
            pr_description=request.pr_description,
            changes=changes,
            use_llm=request.use_llm,
        )

        # 获取 LLM 建议
        approval = report.get("llm_review", {}).get("approval_recommendation", "comment")

        return PRReviewReport(
            pr_title=report["pr_title"],
            stats=report["stats"],
            summary=report["summary"],
            issues_count=report["stats"]["issues_found"],
            approval_recommendation=approval,
        )

    except Exception as e:
        logger.error(f"PR 审查失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================
# HTML 仪表盘页面
# ===========================================


def _get_dashboard_html() -> str:
    """生成简单的 HTML 仪表盘页面"""
    return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Insight Agent - Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5rem;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 2.5rem;
            font-weight: bold;
            color: #333;
        }
        .chart-container {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .projects-table {
            background: white;
            border-radius: 12px;
            padding: 24px;
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
        }
        .score-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .score-high { background: #d4edda; color: #155724; }
        .score-medium { background: #fff3cd; color: #856404; }
        .score-low { background: #f8d7da; color: #721c24; }
        .analyze-form {
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .analyze-form input {
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 1rem;
            width: 200px;
        }
        .analyze-form button {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
            margin-left: 10px;
        }
        .analyze-form button:hover {
            background: #5a6fd6;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
            color: white;
        }
        .loading.active { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 GitHub Insight Agent Dashboard</h1>

        <!-- 分析表单 -->
        <div class="analyze-form">
            <h3 style="margin-bottom: 15px;">分析新项目</h3>
            <input type="text" id="owner" placeholder="所有者 (如：facebook)">
            <input type="text" id="repo" placeholder="仓库名 (如：react)">
            <button onclick="analyzeProject()">开始分析</button>
            <label style="margin-left: 20px;">
                <input type="checkbox" id="useLlm" checked> 使用 LLM 增强评估
            </label>
        </div>

        <!-- 加载指示器 -->
        <div class="loading" id="loading">
            ⏳ 正在分析项目，请稍候...
        </div>

        <!-- 统计卡片 -->
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 已分析项目</h3>
                <div class="value" id="totalProjects">-</div>
            </div>
            <div class="stat-card">
                <h3>📈 平均质量评分</h3>
                <div class="value" id="avgQuality">-</div>
            </div>
            <div class="stat-card">
                <h3>🔒 平均安全评分</h3>
                <div class="value" id="avgSecurity">-</div>
            </div>
        </div>

        <!-- 雷达图 -->
        <div class="chart-container">
            <h3 style="margin-bottom: 15px;">🎯 竞品对比雷达图</h3>
            <canvas id="radarChart"></canvas>
        </div>

        <!-- 项目列表 -->
        <div class="projects-table">
            <h3 style="margin-bottom: 15px;">📋 最近分析的项目</h3>
            <table>
                <thead>
                    <tr>
                        <th>项目</th>
                        <th>Stars</th>
                        <th>语言</th>
                        <th>质量评分</th>
                        <th>安全评分</th>
                        <th>分析时间</th>
                    </tr>
                </thead>
                <tbody id="projectsTable">
                    <tr><td colspan="6" style="text-align: center;">暂无数据</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        // 加载仪表盘数据
        async function loadDashboard() {
            try {
                const response = await fetch('/api/dashboard/summary');
                const data = await response.json();

                document.getElementById('totalProjects').textContent = data.total_projects;
                document.getElementById('avgQuality').textContent = data.avg_quality_score.toFixed(2) + '/5.0';
                document.getElementById('avgSecurity').textContent = data.avg_security_score.toFixed(2) + '/5.0';

                // 更新项目列表
                const tbody = document.getElementById('projectsTable');
                if (data.recent_analyses.length > 0) {
                    tbody.innerHTML = data.recent_analyses.map(p => `
                        <tr>
                            <td><strong>${p.full_name}</strong><br><small>${p.description}</small></td>
                            <td>⭐ ${p.stars.toLocaleString()}</td>
                            <td>${p.language || 'N/A'}</td>
                            <td>${renderScore(p.quality_score)}</td>
                            <td>${renderScore(p.security_score)}</td>
                            <td>${p.analyzed_at ? new Date(p.analyzed_at).toLocaleString('zh-CN') : '-'}</td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('加载数据失败:', error);
            }
        }

        function renderScore(score) {
            if (score === null || score === undefined) return '-';
            const className = score >= 4 ? 'score-high' : score >= 3 ? 'score-medium' : 'score-low';
            return `<span class="score-badge ${className}">${score.toFixed(1)}</span>`;
        }

        // 分析项目
        async function analyzeProject() {
            const owner = document.getElementById('owner').value.trim();
            const repo = document.getElementById('repo').value.trim();
            const useLlm = document.getElementById('useLlm').checked;

            if (!owner || !repo) {
                alert('请输入所有者和仓库名');
                return;
            }

            document.getElementById('loading').classList.add('active');

            try {
                const response = await fetch(`/api/projects/analyze?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}&use_llm=${useLlm}`, {
                    method: 'POST',
                });

                const result = await response.json();

                if (response.ok) {
                    alert(`分析完成！\\n质量评分：${result.quality.quality_score}/5.0\\n安全评分：${result.quality.security_score}/5.0`);
                    loadDashboard();  // 刷新数据
                } else {
                    alert(`分析失败：${result.detail}`);
                }
            } catch (error) {
                alert('请求失败：' + error.message);
            } finally {
                document.getElementById('loading').classList.remove('active');
            }
        }

        // 加载雷达图
        async function loadRadarChart() {
            try {
                const response = await fetch('/api/radar');
                const data = await response.json();

                const ctx = document.getElementById('radarChart').getContext('2d');
                new Chart(ctx, {
                    type: 'radar',
                    data: {
                        labels: data.dimensions,
                        datasets: [
                            {
                                label: 'GIA (本产品)',
                                data: data.gia_scores,
                                borderColor: '#667eea',
                                backgroundColor: 'rgba(102, 126, 234, 0.2)',
                                borderWidth: 3,
                            },
                            ...data.competitor_names.map((name, i) => ({
                                label: name,
                                data: data.competitor_scores[i],
                                borderColor: ['#ff6384', '#36a2eb', '#ffce56', '#4bc0c0'][i % 4],
                                backgroundColor: 'transparent',
                                borderWidth: 2,
                                borderDash: [5, 5],
                            })),
                        ]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            r: {
                                min: 0,
                                max: 5,
                                ticks: { stepSize: 1 },
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('加载雷达图失败:', error);
            }
        }

        // 页面加载时初始化
        loadDashboard();
        loadRadarChart();
    </script>
</body>
</html>
"""


# ===========================================
# 启动服务器
# ===========================================


def run_dashboard(host: str = "0.0.0.0", port: int = 8000):
    """
    启动仪表盘服务器

    Args:
        host: 监听地址
        port: 端口号
    """
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_dashboard()
