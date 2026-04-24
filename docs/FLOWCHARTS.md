# GitHub Insight Agent - 流程图集合

**最后更新:** 2026-04-24

---

## 1. 系统启动流程

```mermaid
flowchart TD
    A[用户启动 gia CLI] --> B[加载 ConfigManager]
    B --> C{检查配置文件}
    C -->|存在 | D[加载 configs/model_configs.json]
    C -->|不存在 | E[创建默认配置]
    D --> F[加载环境变量 /home/lisa/.env]
    E --> F
    F --> G{验证 API Key}
    G -->|有效 | H[初始化 ResearcherAgent]
    G -->|无效 | I[输出错误提示]
    H --> J[初始化 AnalystAgent]
    J --> K[进入交互模式]
    I --> L[退出程序]
```

---

## 2. 用户请求处理流程

```mermaid
flowchart TD
    A[用户输入命令] --> B{解析命令类型}
    
    B -->|/analyze | C[调用 AnalystAgent.analyze_project]
    B -->|/search | D[调用 ResearcherAgent.search_and_analyze]
    B -->|/report | E[调用 ReportGenerator 工作流]
    B -->|/pr | F[调用 PRReviewer.review_pull_request]
    B -->|/scan | G[调用 OWASPRuleEngine.detect_issues]
    
    C --> H{执行成功？}
    D --> H
    E --> H
    F --> H
    G --> H
    
    H -->|是 | I[格式化输出结果]
    H -->|否 | J[错误处理]
    
    I --> K[返回给用户]
    J --> L[输出错误详情]
    L --> K
```

---

## 3. ResearcherAgent 搜索流程

```mermaid
flowchart TD
    A[接收搜索查询] --> B[解析自然语言]
    B --> C{检测时间范围？}
    
    C -->|是 | D[转换为 created:YYYY-MM-DD..YYYY-MM-DD]
    C -->|否 | E[使用原始查询]
    
    D --> F{检测数量限制？}
    E --> F
    
    F -->|是 | G[设置 per_page=N]
    F -->|否 | H[设置 per_page=10]
    
    G --> I{检测排序偏好？}
    H --> I
    
    I -->|star 最高 | J[sort=stars]
    I -->|fork 最多 | K[sort=forks]
    I -->|最新 | L[sort=updated]
    I -->|无 | M[sort=stars 默认]
    
    J --> N[调用 GitHub Search API]
    K --> N
    L --> N
    M --> N
    
    N --> O{API 成功？}
    O -->|是 | P[返回结构化结果]
    O -->|否 | Q[错误处理]
    
    P --> R[添加到记忆]
    Q --> S[返回错误信息]
```

---

## 4. AnalystAgent 分析流程

```mermaid
flowchart TD
    A[接收项目名 owner/repo] --> B[获取 README]
    B --> C[获取仓库信息]
    C --> D[获取语言统计]
    D --> E[获取 Commit 历史]
    
    E --> F[代码质量评分]
    F --> G{规则评分 > 3？}
    
    G -->|是 | H[LLM 深度分析]
    G -->|否 | I[仅规则评分]
    
    H --> J[生成技术栈分析]
    I --> J
    
    J --> K[生成推荐意见]
    K --> L[结构化输出]
    
    L --> M{分析成功？}
    M -->|是 | N[保存到数据库]
    M -->|否 | O[错误处理]
```

---

## 5. ReportGenerator 工作流

```mermaid
flowchart TD
    A[用户请求生成报告] --> B[调用 Researcher.search_and_analyze]
    B --> C[获取搜索结果列表]
    
    C --> D[遍历每个项目]
    D --> E{还有项目？}
    
    E -->|是 | F[调用 Analyst.analyze_project]
    F --> G[收集分析结果]
    G --> D
    
    E -->|否 | H[汇总所有分析]
    
    H --> I[生成执行摘要]
    I --> J[生成项目详情表格]
    J --> K[生成综合评估]
    
    K --> L[填充报告模板]
    L --> M[输出 Markdown 报告]
    
    M --> N[推送到微信/飞书]
```

---

## 6. PR 审查流程

```mermaid
flowchart TD
    A[用户粘贴 git diff] --> B[解析 diff 为 CodeChange 列表]
    
    B --> C[规则检测]
    C --> D[OWASP 安全规则 53 条]
    D --> E[代码质量规则 6 条]
    E --> F[收集规则问题]
    
    F --> G{使用 LLM？}
    G -->|是 | H[LLM 深度审查]
    G -->|否 | I[跳过 LLM]
    
    H --> J[收集 LLM 问题]
    I --> J
    
    J --> K[汇总问题列表]
    K --> L[按严重程度排序]
    
    L --> M[生成审查报告]
    M --> N[输出修复建议]
```

---

## 7. OWASP 安全检测流程

```mermaid
flowchart TD
    A[接收代码内容] --> B[遍历 53 条安全规则]
    
    B --> C{匹配规则？}
    C -->|是 | D[记录问题位置]
    C -->|否 | E[继续下一条]
    
    D --> F[确定严重程度]
    F --> G{CRITICAL/HIGH？}
    
    G -->|是 | H[标记为高危]
    G -->|否 | I[标记为中低危]
    
    H --> J[生成修复建议]
    I --> J
    
    J --> K[添加到问题列表]
    K --> L{还有规则？}
    
    L -->|是 | B
    L -->|否 | M[返回问题列表]
```

---

## 8. 配置加载流程

```mermaid
flowchart TD
    A[ConfigManager 初始化] --> B[加载全局 /home/lisa/.env]
    B --> C{文件存在？}
    
    C -->|是 | D[加载 DASHSCOPE_API_KEY]
    C -->|否 | E[记录警告]
    
    D --> F[加载项目 .env]
    E --> F
    
    F --> G[加载 configs/model_configs.json]
    G --> H{环境变量覆盖？}
    
    H -->|是 | I[使用环境变量值]
    H -->|否 | J[使用文件配置值]
    
    I --> K[配置完成]
    J --> K
```

---

## 9. 持久化内存流程

```mermaid
flowchart TD
    A[PersistentMemory 初始化] --> B[连接 SQLite data/app.db]
    B --> C{数据库存在？}
    
    C -->|否 | D[创建表结构]
    D --> E[conversation_history 表]
    E --> F[memory_index 表]
    
    C --> G[表已存在]
    F --> G
    
    G --> H[写入消息]
    H --> I{事务成功？}
    
    I -->|是 | J[提交事务]
    I -->|否 | K[重试机制]
    
    K --> L{重试 3 次？}
    L -->|否 | H
    L -->|是 | M[抛出异常]
    
    J --> N[索引更新]
```

---

## 10. 定时任务执行流程 (Hermes)

```mermaid
flowchart TD
    A[Hermes Cron 触发 21:00] --> B[加载任务配置]
    
    B --> C[执行 Part 1: 技术迭代]
    C --> D[架构审查]
    D --> E[安全漏洞修复]
    E --> F[测试用例补充]
    F --> G[执行测试]
    
    G --> H[输出 Part 1 结果]
    H --> I[执行 Part 2: 产品迭代]
    
    I --> J[竞品分析]
    J --> K[产品待办列表]
    K --> L[迭代计划]
    
    L --> M[输出 Part 2 结果]
    M --> N[保存到 .hermes/mission-results/]
    
    N --> O[推送到微信]
    O --> P[推送到飞书]
    
    P --> Q[更新 INDEX.md]
```

---

## 11. 错误处理流程

```mermaid
flowchart TD
    A[捕获异常] --> B{异常类型}
    
    B -->|APIError | C[检查 API Key]
    B -->|RateLimitError | D[等待重试]
    B -->|ConnectionError | E[检查网络]
    B -->|ValueError | F[检查输入参数]
    
    C --> G{Key 有效？}
    G -->|否 | H[输出配置指南]
    G -->|是 | I[重试请求]
    
    D --> J{超过重试次数？}
    J -->|否 | K[指数退避]
    J -->|是 | L[输出限流提示]
    
    E --> M[输出网络诊断]
    F --> N[输出参数格式]
    
    H --> O[记录日志]
    I --> O
    K --> O
    L --> O
    M --> O
    N --> O
    
    O --> P[返回用户友好错误]
```

---

## 12. CI/CD 流程

```mermaid
flowchart TD
    A[Git Push] --> B[GitHub Actions 触发]
    
    B --> C[Lint 检查]
    C --> D{flake8 通过？}
    D -->|否 | E[邮件通知失败]
    D -->|是 | F[运行测试]
    
    F --> G{测试通过？}
    G -->|否 | E
    G -->|是 | H[安全审计]
    
    H --> I{pip-audit 通过？}
    I -->|否 | E
    I -->|是 | J[构建成功]
    
    J --> K[更新 CHANGELOG]
    K --> L[邮件通知成功]
```

---

*图表使用 Mermaid 语法，可在支持 Mermaid 的 Markdown 查看器中渲染*
