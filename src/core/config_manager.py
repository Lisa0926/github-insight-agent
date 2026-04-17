# -*- coding: utf-8 -*-
"""
配置加载器 - ConfigManager 单例类

功能:
- 读取 configs/model_configs.json 配置文件
- 支持环境变量覆盖敏感配置 (如 API Key)
- 提供统一的配置访问接口

使用类型驱动设计，确保配置数据的类型安全。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv


class ConfigManager:
    """
    配置管理器单例类

    负责加载和管理项目的全局配置，支持:
    1. 从 JSON 文件加载配置
    2. 环境变量覆盖 (优先于文件配置)
    3. 配置热刷新
    """

    _instance: Optional["ConfigManager"] = None
    _initialized: bool = False

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ConfigManager._initialized:
            return

        self._config_path: Path = Path(__file__).parent.parent.parent / "configs"
        self._model_configs: Dict[str, Any] = {}
        self._env_loaded: bool = False
        self._load_env()
        self._load_model_configs()
        ConfigManager._initialized = True

    def _load_env(self) -> None:
        """加载 .env 文件中的环境变量

        加载顺序:
        1. 全局 .env (包含共享的 API Keys) - 路径由 GLOBAL_ENV 环境变量指定，默认为 ~/.env
        2. 项目 .env (项目特定配置，可覆盖全局配置)
        """
        # 1. 先加载全局 .env (如果存在)
        global_env_path = Path(os.environ.get("GLOBAL_ENV", Path.home() / ".env"))
        if global_env_path.exists():
            load_dotenv(global_env_path)
            self._env_loaded = True

        # 2. 再加载项目 .env (可覆盖全局配置)
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)
            self._env_loaded = True
        else:
            # 尝试加载 .env.example 作为备选
            env_example_path = Path(__file__).parent.parent.parent / ".env.example"
            if env_example_path.exists():
                load_dotenv(env_example_path, override=True)

    def _load_model_configs(self) -> None:
        """从 JSON 文件加载模型配置"""
        config_file = self._config_path / "model_configs.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._model_configs = json.load(f)
        else:
            self._model_configs = {}

    def refresh(self) -> None:
        """刷新配置 (重新加载文件和环境变量)"""
        self._load_env()
        self._load_model_configs()

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键名，支持点分隔符 (如 "qwen-max.api_key")
            default: 默认值

        Returns:
            配置值或默认值
        """
        keys = key.split(".")
        value: Any = self._model_configs

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """
        获取指定模型的完整配置

        Args:
            model_name: 模型名称 (如 "qwen-max")

        Returns:
            模型配置字典
        """
        return self._model_configs.get(model_name, {})

    def get_api_key(self, model_name: str) -> Optional[str]:
        """
        获取模型 API Key (优先从环境变量读取)

        Args:
            model_name: 模型名称

        Returns:
            API Key 或 None
        """
        # 优先从环境变量读取
        env_key_map = {
            "qwen-max": "DASHSCOPE_API_KEY",
            "qwen-plus": "DASHSCOPE_API_KEY",
            "qwen-turbo": "DASHSCOPE_API_KEY",
        }
        env_var = env_key_map.get(model_name, "DASHSCOPE_API_KEY")
        api_key = os.getenv(env_var)

        if api_key:
            return api_key

        # 从配置文件读取
        return self.get(f"{model_name}.api_key")

    @property
    def model_configs(self) -> Dict[str, Any]:
        """获取所有模型配置"""
        return self._model_configs.copy()

    @property
    def env_loaded(self) -> bool:
        """检查环境变量是否已加载"""
        return self._env_loaded

    # ===========================================
    # 阿里云百炼配置
    # ===========================================
    @property
    def dashscope_api_key(self) -> str:
        """获取阿里云百炼 API Key"""
        return os.getenv("DASHSCOPE_API_KEY", "")

    @property
    def dashscope_organization_id(self) -> str:
        """获取阿里云百炼组织 ID"""
        return os.getenv("DASHSCOPE_ORGANIZATION_ID", "")

    @property
    def dashscope_model_name(self) -> str:
        """获取默认模型名称"""
        return os.getenv("DASHSCOPE_MODEL_NAME", "qwen-max")

    @property
    def dashscope_base_url(self) -> str:
        """获取阿里云百炼 API 端点 URL"""
        return os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com")

    # ===========================================
    # GitHub API 配置
    # ===========================================
    @property
    def github_token(self) -> str:
        """获取 GitHub Token"""
        return os.getenv("GITHUB_TOKEN", "")

    @property
    def github_api_url(self) -> str:
        """获取 GitHub API URL"""
        return os.getenv("GITHUB_API_URL", "https://api.github.com")

    @property
    def github_timeout(self) -> int:
        """获取 GitHub API 请求超时时间"""
        return int(os.getenv("GITHUB_TIMEOUT", "30"))

    @property
    def github_rate_limit(self) -> int:
        """获取 GitHub API 请求速率限制"""
        return int(os.getenv("GITHUB_RATE_LIMIT", "10"))

    # ===========================================
    # 模型参数配置
    # ===========================================
    @property
    def model_temperature(self) -> float:
        """获取模型温度参数"""
        return float(os.getenv("MODEL_TEMPERATURE", "0.7"))

    @property
    def model_max_tokens(self) -> int:
        """获取模型最大 token 数"""
        return int(os.getenv("MODEL_MAX_TOKENS", "2048"))

    @property
    def model_top_p(self) -> float:
        """获取模型 Top-P 参数"""
        return float(os.getenv("MODEL_TOP_P", "0.9"))

    @property
    def model_repetition_penalty(self) -> float:
        """获取模型重复惩罚系数"""
        return float(os.getenv("MODEL_REPETITION_PENALTY", "1.1"))

    # ===========================================
    # 日志配置
    # ===========================================
    @property
    def log_level(self) -> str:
        """获取日志级别"""
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def log_max_size_mb(self) -> int:
        """获取日志文件最大大小 (MB)"""
        return int(os.getenv("LOG_MAX_SIZE_MB", "10"))

    @property
    def log_retention_days(self) -> int:
        """获取日志保留天数"""
        return int(os.getenv("LOG_RETENTION_DAYS", "7"))

    @property
    def log_dir(self) -> str:
        """获取日志目录"""
        return os.getenv("LOG_DIR", "logs")

    # ===========================================
    # AgentScope 配置
    # ===========================================
    @property
    def agentscope_project(self) -> str:
        """获取 AgentScope 项目名称"""
        return os.getenv("AGENTSCOPE_PROJECT", "GitHub Insight Agent")

    @property
    def agentscope_run_name(self) -> str:
        """获取 AgentScope 运行名称"""
        return os.getenv("AGENTSCOPE_RUN_NAME", "main")

    @property
    def agentscope_enable_studio(self) -> bool:
        """是否启用 AgentScope Studio"""
        return os.getenv("AGENTSCOPE_ENABLE_STUDIO", "false").lower() == "true"

    @property
    def agentscope_studio_url(self) -> str:
        """获取 AgentScope Studio URL"""
        return os.getenv("AGENTSCOPE_STUDIO_URL", "http://localhost:3000")

    @property
    def agentscope_enable_tracing(self) -> bool:
        """是否启用追踪"""
        return os.getenv("AGENTSCOPE_ENABLE_TRACING", "false").lower() == "true"

    @property
    def agentscope_tracing_url(self) -> str:
        """获取追踪服务 URL"""
        return os.getenv("AGENTSCOPE_TRACING_URL", "")

    # ===========================================
    # 应用配置
    # ===========================================
    @property
    def project_root(self) -> str:
        """获取项目根目录"""
        return os.getenv("PROJECT_ROOT", str(Path(__file__).parent.parent.parent))

    @property
    def config_dir(self) -> str:
        """获取配置目录"""
        return os.getenv("CONFIG_DIR", "configs")

    @property
    def model_config_file(self) -> str:
        """获取模型配置文件名"""
        return os.getenv("MODEL_CONFIG_FILE", "model_configs.json")

    @property
    def prompt_templates_dir(self) -> str:
        """获取提示词模板目录"""
        return os.getenv("PROMPT_TEMPLATES_DIR", "prompt_templates")

    @property
    def output_dir(self) -> str:
        """获取输出目录"""
        return os.getenv("OUTPUT_DIR", "output")

    @property
    def temp_dir(self) -> str:
        """获取临时目录"""
        return os.getenv("TEMP_DIR", "tmp")

    # ===========================================
    # 高级配置
    # ===========================================
    @property
    def max_retries(self) -> int:
        """获取最大重试次数"""
        return int(os.getenv("MAX_RETRIES", "3"))

    @property
    def retry_delay_seconds(self) -> float:
        """获取重试延迟时间 (秒)"""
        return float(os.getenv("RETRY_DELAY_SECONDS", "1"))

    @property
    def retry_backoff_multiplier(self) -> float:
        """获取重试退避乘数"""
        return float(os.getenv("RETRY_BACKOFF_MULTIPLIER", "2.0"))

    @property
    def request_timeout(self) -> int:
        """获取请求超时时间 (秒)"""
        return int(os.getenv("REQUEST_TIMEOUT", "60"))

    @property
    def debug_mode(self) -> bool:
        """是否启用调试模式"""
        return os.getenv("DEBUG_MODE", "false").lower() == "true"
