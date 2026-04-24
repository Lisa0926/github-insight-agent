# -*- coding: utf-8 -*-
"""
OWASP Top 10 安全规则检测

功能:
- 检测 OWASP Top 10 安全漏洞
- 覆盖 2021 年最新版 OWASP Top 10 类别
- 提供修复建议和代码示例

OWASP Top 10 2021 类别:
A01: Broken Access Control
A02: Cryptographic Failures
A03: Injection
A04: Insecure Design
A05: Security Misconfiguration
A06: Vulnerable and Outdated Components
A07: Identification and Authentication Failures
A08: Software and Data Integrity Failures
A09: Security Logging and Monitoring Failures
A10: Server-Side Request Forgery (SSRF)
"""

import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from src.core.logger import get_logger
from src.core.config_manager import ConfigManager
from src.types.schemas import ToolResponse

logger = get_logger(__name__)


class IssueSeverity(Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(Enum):
    """问题类别 (OWASP Top 10 2021)"""
    A01_ACCESS_CONTROL = "A01: Broken Access Control"
    A02_CRYPTOGRAPHIC = "A02: Cryptographic Failures"
    A03_INJECTION = "A03: Injection"
    A04_INSECURE_DESIGN = "A04: Insecure Design"
    A05_MISCONFIGURATION = "A05: Security Misconfiguration"
    A06_VULNERABLE_COMPONENTS = "A06: Vulnerable and Outdated Components"
    A07_AUTH_FAILURE = "A07: Identification and Authentication Failures"
    A08_INTEGRITY_FAILURE = "A08: Software and Data Integrity Failures"
    A09_LOGGING_FAILURE = "A09: Security Logging and Monitoring Failures"
    A10_SSRF = "A10: Server-Side Request Forgery"
    GENERAL_SECURITY = "General Security"


@dataclass
class SecurityComment:
    """安全审查评论"""
    file_path: str
    line_number: int
    category: IssueCategory
    severity: IssueSeverity
    owasp_id: str
    message: str
    suggestion: Optional[str] = None
    code_example: Optional[str] = None
    cwe_id: Optional[str] = None


class OWASPRuleEngine:
    """
    OWASP Top 10 安全规则检测引擎

    基于正则表达式检测常见安全漏洞模式。
    """

    # OWASP Top 10 安全规则库 (50+ 条规则)
    SECURITY_RULES = {
        # ===========================================
        # A01: Broken Access Control (访问控制破坏)
        # ===========================================
        "a01_hardcoded_admin": {
            "pattern": r"(admin|root|superuser)\s*=\s*(True|1|'true'|\"true\")",
            "category": IssueCategory.A01_ACCESS_CONTROL,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A01:2021",
            "message": "发现硬编码的管理员权限设置",
            "suggestion": "使用基于角色的访问控制 (RBAC)，从配置或数据库读取权限",
            "cwe_id": "CWE-284"
        },
        "a01_missing_auth_check": {
            "pattern": r"@(app\.route|router\.(get|post|put|delete))\s*\([^)]*admin[^)]*\)",
            "category": IssueCategory.A01_ACCESS_CONTROL,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A01:2021",
            "message": "管理路由可能缺少权限检查",
            "suggestion": "添加 @login_required 和 @admin_required 装饰器",
            "cwe_id": "CWE-285"
        },
        "a01_path_traversal": {
            "pattern": r"(open|read|write)\s*\(\s*['\"].*?\s*\+\s*\w+.*?\)",
            "category": IssueCategory.A01_ACCESS_CONTROL,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A01:2021",
            "message": "可能存在路径遍历漏洞",
            "suggestion": "验证并净化文件路径输入，使用 os.path.basename() 限制访问范围",
            "cwe_id": "CWE-22"
        },
        "a01_insecure_direct_reference": {
            "pattern": r"/(user|account|profile)/(\{\w+\}|\$\w+)",
            "category": IssueCategory.A01_ACCESS_CONTROL,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A01:2021",
            "message": "可能存在不安全直接对象引用 (IDOR)",
            "suggestion": "验证用户是否有权访问请求的资源",
            "cwe_id": "CWE-639"
        },

        # ===========================================
        # A02: Cryptographic Failures (加密失败)
        # ===========================================
        "a02_md5_password": {
            "pattern": r"(md5|MD5)\s*\(.*?(password|passwd|pwd)",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A02:2021",
            "message": "使用 MD5 加密密码 (已被破解)",
            "suggestion": "使用 bcrypt 或 Argon2 进行密码哈希",
            "cwe_id": "CWE-328"
        },
        "a02_sha1_password": {
            "pattern": r"(sha1|SHA1|sha1sum)\s*\(.*?(password|passwd|pwd)",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A02:2021",
            "message": "使用 SHA1 加密密码 (不够安全)",
            "suggestion": "使用 bcrypt 或 Argon2 进行密码哈希",
            "cwe_id": "CWE-328"
        },
        "a02_plaintext_password": {
            "pattern": r"password\s*=\s*(user_?\w*\.password|input\.password|request\.\w*password)",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A02:2021",
            "message": "密码以明文形式存储或传输",
            "suggestion": "在存储前使用 bcrypt.hashpw() 进行哈希处理",
            "cwe_id": "CWE-319"
        },
        "a02_weak_crypto": {
            "pattern": r"(DES|RC4|Blowfish)\s*\(",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A02:2021",
            "message": "使用弱加密算法",
            "suggestion": "使用 AES-256 或 ChaCha20 等现代加密算法",
            "cwe_id": "CWE-327"
        },
        "a02_http_cookie": {
            "pattern": r"setCookie\s*\([^)]*secure\s*=\s*False",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A02:2021",
            "message": "Cookie 未设置 secure 标志",
            "suggestion": "设置 secure=True 和 httponly=True",
            "cwe_id": "CWE-614"
        },
        "a02_unencrypted_transport": {
            "pattern": r"http://(?!localhost|127\.0\.0\.1)",
            "category": IssueCategory.A02_CRYPTOGRAPHIC,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A02:2021",
            "message": "使用 HTTP 而非 HTTPS 进行通信",
            "suggestion": "使用 HTTPS 加密所有网络通信",
            "cwe_id": "CWE-319"
        },

        # ===========================================
        # A03: Injection (注入漏洞)
        # ===========================================
        "a03_sql_injection_fstring": {
            "pattern": r"(execute|cursor\.execute|query)\s*\(\s*f['\"]SELECT",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A03:2021",
            "message": "SQL 注入风险：使用 f-string 拼接 SQL",
            "suggestion": "使用参数化查询：cursor.execute('SELECT * FROM t WHERE id = ?', (user_id,))",
            "cwe_id": "CWE-89"
        },
        "a03_sql_injection_format": {
            "pattern": r"(execute|query)\s*\(\s*['\"].*?%\s*.*?['\"]",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A03:2021",
            "message": "SQL 注入风险：使用 % 格式化拼接 SQL",
            "suggestion": "使用参数化查询，避免字符串格式化",
            "cwe_id": "CWE-89"
        },
        "a03_sql_injection_concat": {
            "pattern": r"(execute|query)\s*\(\s*['\"].*?\s*\+\s*\w+",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A03:2021",
            "message": "SQL 注入风险：使用 + 拼接 SQL",
            "suggestion": "使用参数化查询",
            "cwe_id": "CWE-89"
        },
        "a03_command_injection": {
            "pattern": r"os\.(system|popen|exec)\s*\(\s*f?['\"]",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A03:2021",
            "message": "命令注入风险：用户输入直接传递给系统命令",
            "suggestion": "使用 subprocess.run() 并传入列表参数，避免 shell=True",
            "cwe_id": "CWE-78"
        },
        "a03_xss_output": {
            "pattern": r"(write|html|innerHTML)\s*\(\s*\w+\s*[,+)]",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A03:2021",
            "message": "XSS 风险：未转义的用户输出",
            "suggestion": "使用 html.escape() 或模板引擎的自动转义功能",
            "cwe_id": "CWE-79"
        },
        "a03_xss_request": {
            "pattern": r"request\.(args|form|data)\['?\w+'?\]",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A03:2021",
            "message": "可能的 XSS 风险：未净化的用户输入",
            "suggestion": "验证并转义所有用户输入",
            "cwe_id": "CWE-79"
        },
        "a03_ldap_injection": {
            "pattern": r"(ldap|LDAPS?)\s*\(\s*['\"].*?\+",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A03:2021",
            "message": "LDAP 注入风险",
            "suggestion": "净化 LDAP 查询中的特殊字符",
            "cwe_id": "CWE-90"
        },
        "a03_xpath_injection": {
            "pattern": r"xpath\s*\(\s*['\"].*?\+",
            "category": IssueCategory.A03_INJECTION,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A03:2021",
            "message": "XPath 注入风险",
            "suggestion": "使用参数化 XPath 查询",
            "cwe_id": "CWE-643"
        },

        # ===========================================
        # A04: Insecure Design (不安全设计)
        # ===========================================
        "a04_weak_rate_limit": {
            "pattern": r"rate[_-]?limit\s*=\s*(0|99999|Infinity)",
            "category": IssueCategory.A04_INSECURE_DESIGN,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A04:2021",
            "message": "速率限制设置过弱或禁用",
            "suggestion": "实施合理的速率限制 (如 100 次/小时)",
            "cwe_id": "CWE-1190"
        },
        "a04_missing_csrf": {
            "pattern": r"@app\.(route|post)\s*\([^)]*(form|submit|update)[^)]*\)",
            "category": IssueCategory.A04_INSECURE_DESIGN,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A04:2021",
            "message": "表单提交可能缺少 CSRF 保护",
            "suggestion": "添加 CSRF token 验证",
            "cwe_id": "CWE-352"
        },
        "a04_weak_captcha": {
            "pattern": r"captcha\s*=\s*(None|False|'skip')",
            "category": IssueCategory.A04_INSECURE_DESIGN,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A04:2021",
            "message": "验证码被禁用或跳过",
            "suggestion": "在关键操作 (登录、注册、重置密码) 启用验证码",
            "cwe_id": "CWE-300"
        },
        "a04_business_logic": {
            "pattern": r"if\s+\w+\.price\s*<=?\s*0",
            "category": IssueCategory.A04_INSECURE_DESIGN,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A04:2021",
            "message": "可能存在业务逻辑漏洞 (价格篡改)",
            "suggestion": "在服务器端验证价格，不信任客户端输入",
            "cwe_id": "CWE-840"
        },

        # ===========================================
        # A05: Security Misconfiguration (安全配置错误)
        # ===========================================
        "a05_debug_true": {
            "pattern": r"DEBUG\s*=\s*True",
            "category": IssueCategory.A05_MISCONFIGURATION,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A05:2021",
            "message": "生产环境开启 DEBUG 模式",
            "suggestion": "设置 DEBUG=False，并配置适当的日志级别",
            "cwe_id": "CWE-215"
        },
        "a05_cors_wildcard": {
            "pattern": r"allow_origins\s*=\s*\['\*'\]| CORS\(.*\*\)",
            "category": IssueCategory.A05_MISCONFIGURATION,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A05:2021",
            "message": "CORS 配置为允许所有来源",
            "suggestion": "指定允许的来源列表",
            "cwe_id": "CWE-942"
        },
        "a05_exposed_env": {
            "pattern": r"\.env|\.git|\.DS_Store",
            "category": IssueCategory.A05_MISCONFIGURATION,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A05:2021",
            "message": "敏感文件可能被公开访问",
            "suggestion": "在 web 服务器配置中禁止访问敏感文件",
            "cwe_id": "CWE-538"
        },
        "a05_verbose_errors": {
            "pattern": r"(return|raise|print)\s+.*?(traceback|stacktrace|exception)",
            "category": IssueCategory.A05_MISCONFIGURATION,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A05:2021",
            "message": "可能泄露详细错误信息",
            "suggestion": "返回通用错误消息，记录详细错误到日志",
            "cwe_id": "CWE-209"
        },
        "a05_default_credentials": {
            "pattern": r"(password|passwd)\s*=\s*['\"](admin|password|123456|default)['\"]",
            "category": IssueCategory.A05_MISCONFIGURATION,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A05:2021",
            "message": "使用默认凭证",
            "suggestion": "修改默认密码，使用强密码策略",
            "cwe_id": "CWE-798"
        },

        # ===========================================
        # A06: Vulnerable Components (易受攻击的组件)
        # ===========================================
        "a06_outdated_python": {
            "pattern": r"python_requires\s*=\s*['\"]>=?\s*(2\.|3\.[0-5])",
            "category": IssueCategory.A06_VULNERABLE_COMPONENTS,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A06:2021",
            "message": "使用过时或不安全的 Python 版本",
            "suggestion": "升级到 Python 3.8+ (已停止支持的版本有安全风险)",
            "cwe_id": "CWE-1104"
        },
        "a06_pinned_version": {
            "pattern": r"(requests|flask|django|pillow|urllib3)\s*==\s*(1\.|2\.0|2\.1|2\.2)\d*",
            "category": IssueCategory.A06_VULNERABLE_COMPONENTS,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A06:2021",
            "message": "依赖版本可能有过时安全漏洞",
            "suggestion": "运行 pip-audit 或 safety check 检查已知漏洞",
            "cwe_id": "CWE-1104"
        },
        "a06_insecure_package": {
            "pattern": r"(git|https?)://github\.com/[^/]+/[^/]+\.git",
            "category": IssueCategory.A06_VULNERABLE_COMPONENTS,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A06:2021",
            "message": "直接从 GitHub 安装依赖 (绕过 PyPI 安全机制)",
            "suggestion": "优先使用 PyPI 官方包，验证包完整性",
            "cwe_id": "CWE-1104"
        },

        # ===========================================
        # A07: Auth Failure (认证失败)
        # ===========================================
        "a07_weak_password": {
            "pattern": r"min_length\s*=\s*[1-5]\b",
            "category": IssueCategory.A07_AUTH_FAILURE,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A07:2021",
            "message": "密码最小长度要求过弱",
            "suggestion": "设置最小密码长度为 12 位，并要求复杂度",
            "cwe_id": "CWE-521"
        },
        "a07_session_fixation": {
            "pattern": r"(session|cookie).*(regenerate|rotate)",
            "category": IssueCategory.A07_AUTH_FAILURE,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A07:2021",
            "message": "可能存在会话固定攻击风险",
            "suggestion": "登录后重新生成 session ID",
            "cwe_id": "CWE-384"
        },
        "a07_brute_force": {
            "pattern": r"for\s+\w+\s+in\s+range\s*\([^)]*\):\s*\n\s+if\s+password",
            "category": IssueCategory.A07_AUTH_FAILURE,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A07:2021",
            "message": "可能存在暴力破解风险",
            "suggestion": "添加账户锁定机制和验证码",
            "cwe_id": "CWE-307"
        },
        "a07_jwt_none": {
            "pattern": r"JWT.*?(algorithm|verify)\s*=\s*(none|'none'|\"none\")",
            "category": IssueCategory.A07_AUTH_FAILURE,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "A07:2021",
            "message": "JWT 算法设置为 'none' (严重安全风险)",
            "suggestion": "使用 RS256 或 HS256 算法，并验证签名",
            "cwe_id": "CWE-347"
        },
        "a07_jwt_weak_secret": {
            "pattern": r"JWT_SECRET\s*=\s*['\"](secret|123456|password)['\"]",
            "category": IssueCategory.A07_AUTH_FAILURE,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A07:2021",
            "message": "JWT 密钥过弱",
            "suggestion": "使用至少 32 字节的随机密钥",
            "cwe_id": "CWE-347"
        },

        # ===========================================
        # A08: Integrity Failure (完整性失败)
        # ===========================================
        "a08_unserialize": {
            "pattern": r"(pickle|marshal|unserialize)\.loads?\s*\(",
            "category": IssueCategory.A08_INTEGRITY_FAILURE,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A08:2021",
            "message": "使用不安全的反序列化 (可能导致 RCE)",
            "suggestion": "使用 JSON 或其他安全序列化格式",
            "cwe_id": "CWE-502"
        },
        "a08_insecure_deserialize": {
            "pattern": r"yaml\.load\s*\([^)]*\)\s*$|yaml\.unsafe_load",
            "category": IssueCategory.A08_INTEGRITY_FAILURE,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A08:2021",
            "message": "使用不安全的 YAML 加载",
            "suggestion": "使用 yaml.safe_load() 替代",
            "cwe_id": "CWE-502"
        },
        "a08_code_execution": {
            "pattern": r"__reduce__|__setstate__|__getstate__",
            "category": IssueCategory.A08_INTEGRITY_FAILURE,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A08:2021",
            "message": "自定义序列化方法可能被滥用",
            "suggestion": "谨慎实现魔术方法，避免反序列化不可信数据",
            "cwe_id": "CWE-502"
        },
        "a08_tampering": {
            "pattern": r"integrity\s*=\s*['\"]sha(256|384|512)-[^'\"]{1,20}['\"]",
            "category": IssueCategory.A08_INTEGRITY_FAILURE,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A08:2021",
            "message": "SRI 哈希值过短可能不安全",
            "suggestion": "使用完整的 SHA-384 或 SHA-512 哈希",
            "cwe_id": "CWE-353"
        },

        # ===========================================
        # A09: Logging Failure (日志记录失败)
        # ===========================================
        "a09_missing_audit_log": {
            "pattern": r"def\s+(login|logout|register|delete|admin)",
            "category": IssueCategory.A09_LOGGING_FAILURE,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A09:2021",
            "message": "关键操作可能缺少审计日志",
            "suggestion": "记录所有安全相关操作 (登录、权限变更、数据删除)",
            "cwe_id": "CWE-778"
        },
        "a09_sensitive_log": {
            "pattern": r"log(ger)?\.(info|debug|warning)\s*\(.*?(password|secret|token|api_key)",
            "category": IssueCategory.A09_LOGGING_FAILURE,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A09:2021",
            "message": "日志中记录敏感信息",
            "suggestion": "对敏感信息进行脱敏或过滤后再记录",
            "cwe_id": "CWE-532"
        },
        "a09_no_log_rotation": {
            "pattern": r"(log|logs)/[\w.]+(?!\.conf)",
            "category": IssueCategory.A09_LOGGING_FAILURE,
            "severity": IssueSeverity.LOW,
            "owasp_id": "A09:2021",
            "message": "可能缺少日志轮转配置",
            "suggestion": "配置日志轮转防止磁盘填满",
            "cwe_id": "CWE-778"
        },

        # ===========================================
        # A10: SSRF (服务器端请求伪造)
        # ===========================================
        "a10_ssrf_url": {
            "pattern": r"(requests|urllib|httpx)\.(get|post|put|fetch)\s*\([^)]*url\s*=\s*\w+",
            "category": IssueCategory.A10_SSRF,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "A10:2021",
            "message": "SSRF 风险：用户控制的 URL 发起请求",
            "suggestion": "验证 URL 白名单，阻止内网地址",
            "cwe_id": "CWE-918"
        },
        "a10_ssrf_redirect": {
            "pattern": r"(follow_redirects?|allow_redirects)\s*=\s*True",
            "category": IssueCategory.A10_SSRF,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A10:2021",
            "message": "自动跟随重定向可能导致 SSRF",
            "suggestion": "限制重定向次数并验证目标地址",
            "cwe_id": "CWE-918"
        },
        "a10_internal_service": {
            "pattern": r"(http|https)://(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])|localhost)",
            "category": IssueCategory.A10_SSRF,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "A10:2021",
            "message": "硬编码访问内部服务地址",
            "suggestion": "使用服务发现，避免硬编码内网地址",
            "cwe_id": "CWE-918"
        },

        # ===========================================
        # General Security (通用安全)
        # ===========================================
        "gen_hardcoded_secret": {
            "pattern": r"(password|secret|api_key|token|apikey|private_key)\s*=\s*['\"][^'\"]{8,}['\"]",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.HIGH,
            "owasp_id": "General",
            "message": "发现硬编码的敏感信息（密码/密钥/Token）",
            "suggestion": "使用环境变量或配置文件管理敏感信息",
            "cwe_id": "CWE-798"
        },
        "gen_eval": {
            "pattern": r"\beval\s*\([^)]*\)",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "General",
            "message": "使用 eval() 存在代码执行风险",
            "suggestion": "避免使用 eval()，考虑使用 ast.literal_eval() 或其他安全替代方案",
            "cwe_id": "CWE-95"
        },
        "gen_exec": {
            "pattern": r"\bexec\s*\([^)]*\)",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.CRITICAL,
            "owasp_id": "General",
            "message": "使用 exec() 存在代码执行风险",
            "suggestion": "避免使用 exec()，重构为更安全的代码结构",
            "cwe_id": "CWE-95"
        },
        "gen_temp_file": {
            "pattern": r"open\s*\(\s*['\"]/tmp/",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "General",
            "message": "使用可预测的临时文件路径",
            "suggestion": "使用 tempfile.NamedTemporaryFile() 创建安全临时文件",
            "cwe_id": "CWE-377"
        },
        "gen_race_condition": {
            "pattern": r"if\s+os\.path\.exists\s*\(.*\):\s*\n\s+open\s*\(",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "General",
            "message": "TOCTOU 竞态条件风险",
            "suggestion": "使用原子操作或加锁机制",
            "cwe_id": "CWE-367"
        },
        "gen_assertion": {
            "pattern": r"assert\s+\w+",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.LOW,
            "owasp_id": "General",
            "message": "使用 assert 进行安全验证 (生产环境可能被禁用)",
            "suggestion": "使用显式的条件检查和异常处理",
            "cwe_id": "CWE-703"
        },
        "gen_random": {
            "pattern": r"\brandom\.(random|randint|choice|shuffle)",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "General",
            "message": "使用伪随机数生成器 (不适合安全场景)",
            "suggestion": "使用 secrets 模块生成密码学安全的随机数",
            "cwe_id": "CWE-330"
        },
        "gen_input": {
            "pattern": r"\binput\s*\(\s*['\"]Password",
            "category": IssueCategory.GENERAL_SECURITY,
            "severity": IssueSeverity.MEDIUM,
            "owasp_id": "General",
            "message": "明文输入密码",
            "suggestion": "使用 getpass.getpass() 隐藏密码输入",
            "cwe_id": "CWE-319"
        },
    }

    def __init__(self, config: Optional[ConfigManager] = None):
        """
        初始化 OWASP 规则引擎

        Args:
            config: 配置管理器实例
        """
        self._config = config or ConfigManager()
        logger.info("OWASPRuleEngine initialized with %d rules", len(self.SECURITY_RULES))

    def detect_issues(self, file_path: str, code_content: str, start_line: int = 1) -> List[SecurityComment]:
        """
        检测代码中的安全问题

        Args:
            file_path: 文件路径
            code_content: 代码内容
            start_line: 起始行号

        Returns:
            SecurityComment 列表
        """
        issues: List[SecurityComment] = []

        for rule_name, rule_config in self.SECURITY_RULES.items():
            matches = re.finditer(rule_config["pattern"], code_content, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                # 计算行号
                line_number = start_line + code_content[:match.start()].count('\n')

                # 创建安全审查评论
                comment = SecurityComment(
                    file_path=file_path,
                    line_number=line_number,
                    category=rule_config["category"],
                    severity=rule_config["severity"],
                    owasp_id=rule_config["owasp_id"],
                    message=rule_config["message"],
                    suggestion=rule_config.get("suggestion"),
                    cwe_id=rule_config.get("cwe_id"),
                )
                issues.append(comment)

        return issues

    def get_stats(self) -> Dict[str, Any]:
        """获取规则统计信息"""
        stats = {
            "total_rules": len(self.SECURITY_RULES),
            "by_category": {},
            "by_severity": {},
            "owasp_coverage": set(),
        }

        for rule_name, rule_config in self.SECURITY_RULES.items():
            # 按类别统计
            cat = rule_config["category"].value
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            # 按严重程度统计
            sev = rule_config["severity"].value
            stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1

            # OWASP 覆盖
            stats["owasp_coverage"].add(rule_config["owasp_id"])

        stats["owasp_coverage"] = list(stats["owasp_coverage"])
        return stats


async def scan_security(
    file_path: str,
    code_content: str,
    config: Optional[ConfigManager] = None,
) -> ToolResponse:
    """
    安全扫描工具函数

    Args:
        file_path: 文件路径
        code_content: 代码内容
        config: 配置管理器

    Returns:
        ToolResponse 包装的扫描结果
    """
    try:
        engine = OWASPRuleEngine(config=config)
        issues = engine.detect_issues(file_path, code_content)
        stats = engine.get_stats()

        # 按严重程度分组
        issues_by_severity = {
            "critical": [i for i in issues if i.severity == IssueSeverity.CRITICAL],
            "high": [i for i in issues if i.severity == IssueSeverity.HIGH],
            "medium": [i for i in issues if i.severity == IssueSeverity.MEDIUM],
            "low": [i for i in issues if i.severity == IssueSeverity.LOW],
        }

        # 格式化报告
        report_text = _format_report(file_path, issues, stats)

        report = {
            "file_path": file_path,
            "total_issues": len(issues),
            "issues_by_severity": {k: len(v) for k, v in issues_by_severity.items()},
            "issues": [
                {
                    "file": i.file_path,
                    "line": i.line_number,
                    "category": i.category.value,
                    "severity": i.severity.value,
                    "owasp_id": i.owasp_id,
                    "cwe_id": i.cwe_id,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in issues
            ],
            "rule_stats": stats,
        }

        return ToolResponse.ok(
            data=report,
            message=report_text,
        )

    except Exception as e:
        logger.error(f"安全扫描失败：{e}")
        return ToolResponse.fail(error_message=str(e))


def _format_report(file_path: str, issues: List[SecurityComment], stats: Dict[str, Any]) -> str:
    """格式化扫描报告"""
    lines = [
        "=" * 60,
        "OWASP Top 10 安全扫描报告",
        "=" * 60,
        f"\n文件：{file_path}",
        f"使用规则：{stats['total_rules']} 条",
        f"OWASP 覆盖：{', '.join(stats['owasp_coverage'])}",
        "",
        f"发现问题：{len(issues)} 个",
        "",
    ]

    # 按严重程度分组
    by_severity = {}
    for issue in issues:
        sev = issue.severity.value
        if sev not in by_severity:
            by_severity[sev] = []
        by_severity[sev].append(issue)

    for sev in ["critical", "high", "medium", "low"]:
        if sev in by_severity:
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[sev]
            lines.append(f"{icon} {sev.upper()} ({len(by_severity[sev])} 个)")
            for issue in by_severity[sev][:5]:  # 每级最多显示 5 个
                lines.append(f"   - [{issue.owasp_id}] {issue.file_path}:{issue.line_number}")
                lines.append(f"     {issue.message}")
                if issue.suggestion:
                    lines.append(f"     💡 {issue.suggestion}")
            if len(by_severity[sev]) > 5:
                lines.append(f"   ... 还有 {len(by_severity[sev]) - 5} 个问题")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
