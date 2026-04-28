# -*- coding: utf-8 -*-
"""
Configuration loader - ConfigManager singleton class

Features:
- Read configuration from configs/model_configs.json
- Support environment variable overrides for sensitive config (e.g. API Key)
- Provide a unified configuration access interface

Uses type-driven design to ensure type safety of configuration data.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv


class ConfigManager:
    """
    Configuration manager singleton class

    Responsible for loading and managing the project's global configuration, supports:
    1. Load configuration from JSON file
    2. Environment variable overrides (takes precedence over file config)
    3. Configuration hot refresh
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
        """Load environment variables from .env file

        Load order:
        1. Global .env (contains shared API Keys) - path specified by GLOBAL_ENV env var, defaults to ~/.env
        2. Project .env (project-specific config, overrides global config)
        """
        # 1. Load global .env first (if exists)
        global_env_path = Path(os.environ.get("GLOBAL_ENV", Path.home() / ".env"))
        if global_env_path.exists():
            load_dotenv(global_env_path)
            self._env_loaded = True

        # 2. Load project .env (overrides global config) - only when explicitly allowed
        project_env_path = Path(__file__).parent.parent.parent / ".env"
        if project_env_path.exists():
            # Security: Project .env files may contain secrets that could be committed
            # Only load if explicitly allowed via PROJECT_ENV_ALLOWED=true
            if os.getenv("PROJECT_ENV_ALLOWED", "").lower() == "true":
                load_dotenv(project_env_path, override=True)
                self._env_loaded = True
            else:
                # Log warning if project .env exists but is not explicitly allowed
                pass  # Silently skip - project .env should not be used
        else:
            # Do not load .env.example - it is only a config template reference, not a valid config file
            pass  # Silently skip - .env.example is a template, not a config file

    def _load_model_configs(self) -> None:
        """Load model configuration from JSON file"""
        config_file = self._config_path / "model_configs.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._model_configs = json.load(f)
        else:
            self._model_configs = {}

    def refresh(self) -> None:
        """Refresh configuration (reload file and environment variables)"""
        self._load_env()
        self._load_model_configs()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value

        Args:
            key: Configuration key, supports dot notation (e.g. "qwen-max.api_key")
            default: Default value

        Returns:
            Configuration value or default
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
        Get complete configuration for a specific model

        Args:
            model_name: Model name (e.g. "qwen-max")

        Returns:
            Model configuration dictionary
        """
        return self._model_configs.get(model_name, {})

    def get_api_key(self, model_name: str) -> Optional[str]:
        """
        Get model API Key (prioritize reading from environment variables)

        Args:
            model_name: Model name

        Returns:
            API Key or None
        """
        # Prioritize reading from environment variables
        env_key_map = {
            "qwen-max": "DASHSCOPE_API_KEY",
            "qwen-plus": "DASHSCOPE_API_KEY",
            "qwen-turbo": "DASHSCOPE_API_KEY",
        }
        env_var = env_key_map.get(model_name, "DASHSCOPE_API_KEY")
        api_key = os.getenv(env_var)

        if api_key:
            return api_key

        # Read from config file
        return self.get(f"{model_name}.api_key")

    @property
    def model_configs(self) -> Dict[str, Any]:
        """Get all model configurations"""
        return self._model_configs.copy()

    @property
    def env_loaded(self) -> bool:
        """Check if environment variables have been loaded"""
        return self._env_loaded

    # ===========================================
    # Alibaba Cloud Bailian configuration
    # ===========================================
    @property
    def dashscope_api_key(self) -> str:
        """Get GIA-specific API Key (isolated from Claude Code's DASHSCOPE_API_KEY)"""
        return os.getenv("GIA_DASHSCOPE_API_KEY", "")

    @property
    def dashscope_organization_id(self) -> str:
        """Get Alibaba Cloud Bailian organization ID"""
        return os.getenv("DASHSCOPE_ORGANIZATION_ID", "")

    @property
    def dashscope_model_name(self) -> str:
        """Get default model name"""
        return os.getenv("DASHSCOPE_MODEL_NAME", "qwen-max")

    @property
    def dashscope_base_url(self) -> str:
        """Get Alibaba Cloud Bailian API endpoint URL (shared with Claude Code)"""
        return os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com")

    # ===========================================
    # GitHub API configuration
    # ===========================================
    @property
    def github_token(self) -> str:
        """Get GitHub Token"""
        return os.getenv("GITHUB_TOKEN", "")

    @property
    def github_api_url(self) -> str:
        """Get GitHub API URL"""
        return os.getenv("GITHUB_API_URL", "https://api.github.com")

    @property
    def github_timeout(self) -> int:
        """Get GitHub API request timeout"""
        return int(os.getenv("GITHUB_TIMEOUT", "30"))

    @property
    def github_rate_limit(self) -> int:
        """Get GitHub API rate limit"""
        return int(os.getenv("GITHUB_RATE_LIMIT", "10"))

    # ===========================================
    # Model parameter configuration
    # ===========================================
    @property
    def model_temperature(self) -> float:
        """Get model temperature parameter"""
        return float(os.getenv("MODEL_TEMPERATURE", "0.7"))

    @property
    def model_max_tokens(self) -> int:
        """Get model maximum token count"""
        return int(os.getenv("MODEL_MAX_TOKENS", "2048"))

    @property
    def model_top_p(self) -> float:
        """Get model Top-P parameter"""
        return float(os.getenv("MODEL_TOP_P", "0.9"))

    @property
    def model_repetition_penalty(self) -> float:
        """Get model repetition penalty coefficient"""
        return float(os.getenv("MODEL_REPETITION_PENALTY", "1.1"))

    # ===========================================
    # Logging configuration
    # ===========================================
    @property
    def log_level(self) -> str:
        """Get log level"""
        return os.getenv("LOG_LEVEL", "INFO")

    @property
    def log_max_size_mb(self) -> int:
        """Get maximum log file size (MB)"""
        return int(os.getenv("LOG_MAX_SIZE_MB", "10"))

    @property
    def log_retention_days(self) -> int:
        """Get log retention days"""
        return int(os.getenv("LOG_RETENTION_DAYS", "7"))

    @property
    def log_dir(self) -> str:
        """Get log directory"""
        return os.getenv("LOG_DIR", "logs")

    # ===========================================
    # AgentScope configuration
    # ===========================================
    @property
    def agentscope_project(self) -> str:
        """Get AgentScope project name"""
        return os.getenv("AGENTSCOPE_PROJECT", "GitHub Insight Agent")

    @property
    def agentscope_run_name(self) -> str:
        """Get AgentScope run name"""
        return os.getenv("AGENTSCOPE_RUN_NAME", "main")

    @property
    def agentscope_enable_studio(self) -> bool:
        """Whether to enable AgentScope Studio"""
        return os.getenv("AGENTSCOPE_ENABLE_STUDIO", "false").lower() == "true"

    @property
    def agentscope_studio_url(self) -> str:
        """Get AgentScope Studio URL"""
        return os.getenv("AGENTSCOPE_STUDIO_URL", "http://localhost:3000")

    @property
    def agentscope_enable_tracing(self) -> bool:
        """Whether to enable tracing"""
        return os.getenv("AGENTSCOPE_ENABLE_TRACING", "false").lower() == "true"

    @property
    def agentscope_tracing_url(self) -> str:
        """Get tracing service URL"""
        return os.getenv("AGENTSCOPE_TRACING_URL", "")

    # ===========================================
    # Application configuration
    # ===========================================
    @property
    def project_root(self) -> str:
        """Get project root directory"""
        return os.getenv("PROJECT_ROOT", str(Path(__file__).parent.parent.parent))

    @property
    def config_dir(self) -> str:
        """Get configuration directory"""
        return os.getenv("CONFIG_DIR", "configs")

    @property
    def model_config_file(self) -> str:
        """Get model config file name"""
        return os.getenv("MODEL_CONFIG_FILE", "model_configs.json")

    @property
    def prompt_templates_dir(self) -> str:
        """Get prompt templates directory"""
        return os.getenv("PROMPT_TEMPLATES_DIR", "prompt_templates")

    @property
    def output_dir(self) -> str:
        """Get output directory"""
        return os.getenv("OUTPUT_DIR", "output")

    @property
    def temp_dir(self) -> str:
        """Get temporary directory"""
        return os.getenv("TEMP_DIR", "tmp")

    # ===========================================
    # Advanced configuration
    # ===========================================
    @property
    def max_retries(self) -> int:
        """Get maximum retry count"""
        return int(os.getenv("MAX_RETRIES", "3"))

    @property
    def retry_delay_seconds(self) -> float:
        """Get retry delay time (seconds)"""
        return float(os.getenv("RETRY_DELAY_SECONDS", "1"))

    @property
    def retry_backoff_multiplier(self) -> float:
        """Get retry backoff multiplier"""
        return float(os.getenv("RETRY_BACKOFF_MULTIPLIER", "2.0"))

    @property
    def request_timeout(self) -> int:
        """Get request timeout (seconds)"""
        return int(os.getenv("REQUEST_TIMEOUT", "60"))

    @property
    def debug_mode(self) -> bool:
        """Whether to enable debug mode"""
        return os.getenv("DEBUG_MODE", "false").lower() == "true"
