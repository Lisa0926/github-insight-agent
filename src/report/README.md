# 报告导出与推送模块

## 概述

本模块提供 GitHub Insight Agent 报告的导出和推送功能：

1. **HTML 报告导出** - 将 Markdown 格式的分析报告转换为美观的 HTML 页面
2. **推送格式优化** - 针对微信/飞书等即时通讯工具优化报告格式

## 功能

### HTML 报告导出

- 响应式设计，支持手机/PC 浏览器
- 深色主题（GitHub Dark 风格）
- 自动提取关键指标卡片
- 状态标签美化（✅ ⚠️ 🔴 等）
- 表格自动适配屏幕宽度

### 推送优化

#### 微信推送
- 文本长度控制在 1800 字符以内
- 关键信息优先（指标 → 发现 → 建议）
- 适合微信消息直接阅读

#### 飞书推送
- 支持 Markdown 子集（表格、列表、粗体）
- 长度控制在 3000 字符以内
- 可嵌入飞书文档或消息卡片

## 使用示例

### 导出 HTML 报告

```python
from src.report.html_exporter import export_markdown_to_html

# 读取 Markdown 报告
with open('report.md') as f:
    md_content = f.read()

# 导出为 HTML
output_path = export_markdown_to_html(md_content)
print(f"HTML 报告已导出: {output_path}")
```

### 优化推送格式

```python
from src.report.push_optimizer import optimize_for_wechat, optimize_for_feishu

# 优化为微信格式
wechat_report = optimize_for_wechat(md_content)
print(wechat_report)

# 优化为飞书格式
feishu_report = optimize_for_feishu(md_content)
print(feishu_report)
```

### 集成到 Cron Job

在 cron job 的任务完成后，自动导出 HTML 报告并推送：

```python
# 在 mission 执行完成后
report_content = generate_report()  # 生成 Markdown 报告

# 1. 导出 HTML 报告
html_path = export_markdown_to_html(report_content)

# 2. 优化推送格式
wechat_content = optimize_for_wechat(report_content)
feishu_content = optimize_for_feishu(report_content)

# 3. 推送到微信/飞书（通过 cron scheduler 自动完成）
# 推送内容会自动包含精简版报告 + HTML 链接
```

## 文件结构

```
src/report/
├── __init__.py
├── html_exporter.py      # HTML 导出器
├── push_optimizer.py     # 推送格式优化器
└── README.md             # 本文档
```

## 技术细节

### HTML 导出
- 使用 `markdown` 库转换 Markdown 为 HTML
- 使用 `jinja2` 模板渲染完整页面
- CSS 采用 CSS Variables，方便主题切换
- 移动端优先的响应式设计

### 推送优化
- 正则表达式提取关键信息
- 智能截断，保持内容完整性
- 不同平台使用不同的格式优化策略

## 未来计划

- [ ] 支持 PDF 导出
- [ ] 支持图表生成（Star 趋势、代码质量趋势）
- [ ] 支持自定义模板
- [ ] 支持多语言报告
