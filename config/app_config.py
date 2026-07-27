"""Application configuration and environment loading.

This module centralizes runtime settings so agents and pipelines can share a
single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    cleaned = value.strip()
    return cleaned if cleaned else default


class AppConfig:
    """Centralized configuration with path resolution and validation."""

    def __init__(self, dotenv_path: Path | str | None = None) -> None:
        self.project_root = self._detect_project_root()
        env_path = Path(dotenv_path) if dotenv_path is not None else self.project_root / ".env"
        self._load_env(env_path)
        self._validate_required_vars()

    def _detect_project_root(self) -> Path:
        env_root = os.getenv("PROJECT_ROOT")
        if env_root:
            return Path(env_root).resolve()

        current = Path(__file__).resolve()
        for parent in [current] + list(current.parents):
            if (parent / "requirements.txt").exists() or (parent / "README.md").exists():
                return parent

        return Path(__file__).resolve().parents[1]

    def _load_env(self, dotenv_path: Path) -> None:
        if load_dotenv and dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path)

    def _validate_required_vars(self) -> None:
        provider_needs_key = self.vision_agent_provider == "openai" or self.testcase_agent_provider == "openai"
        if provider_needs_key and not self.openai_api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY is required when using the 'openai' provider. "
                "Set OPENAI_API_KEY in .env or use the 'mock' provider."
            )

    @property
    def vision_agent_provider(self) -> str:
        return os.getenv("VISION_AGENT_PROVIDER", "mock")

    @property
    def testcase_agent_provider(self) -> str:
        return os.getenv("TESTCASE_AGENT_PROVIDER", "mock")

    @property
    def openai_api_key(self) -> str:
        value = os.getenv("OPENAI_API_KEY", "")
        return "" if value == "your_openai_api_key_here" else value

    @property
    def openai_model(self) -> str:
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    @property
    def openai_api_base(self) -> Optional[str]:
        return os.getenv("OPENAI_API_BASE")

    @property
    def appium_server_url(self) -> str:
        return os.getenv("APPIUM_SERVER_URL", "http://127.0.0.1:4723")

    @property
    def app_package(self) -> str:
        return os.getenv("APP_PACKAGE", "com.saucelabs.mydemoapp.android")

    @property
    def app_activity(self) -> str:
        return os.getenv("APP_ACTIVITY", "com.saucelabs.mydemoapp.android.view.activities.SplashActivity")

    @property
    def app_profile_preset(self) -> str:
        configured = _env_str("APP_PROFILE_PRESET", "auto").lower()
        allowed = {"auto", "generic", "ecommerce", "banking", "social"}
        if configured not in allowed:
            configured = "auto"
        if configured != "auto":
            return configured

        package = (self.app_package or "").strip().lower()
        if "saucelabs" in package:
            return "ecommerce"
        return "generic"

    @property
    def is_reference_demo_profile(self) -> bool:
        return self.app_profile_preset == "ecommerce"

    @property
    def app_specific_locator_hints_enabled(self) -> bool:
        value = os.getenv("ENABLE_APP_SPECIFIC_LOCATOR_HINTS")
        if value is None:
            return self.app_profile_preset in {"ecommerce", "banking"}
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @property
    def app_specific_navigation_enabled(self) -> bool:
        value = os.getenv("ENABLE_APP_SPECIFIC_NAVIGATION")
        if value is None:
            return self.app_profile_preset in {"ecommerce", "social"}
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @property
    def strict_config_validation(self) -> bool:
        return _env_bool("STRICT_CONFIG_VALIDATION", True)

    @property
    def dynamic_journey_enabled(self) -> bool:
        return _env_bool("ENABLE_DYNAMIC_JOURNEY_MODE", True)

    @property
    def artifact_retention_days(self) -> int:
        return max(1, _env_int("ARTIFACT_RETENTION_DAYS", 14))

    @property
    def telemetry_enabled(self) -> bool:
        return _env_bool("ENABLE_STAGE_TELEMETRY", True)

    @property
    def telemetry_dir(self) -> Path:
        return self.project_root / os.getenv("TELEMETRY_DIR", "artifacts/telemetry")

    @property
    def platform_name(self) -> str:
        return os.getenv("PLATFORM_NAME", "Android")

    @property
    def automation_name(self) -> str:
        return os.getenv("AUTOMATION_NAME", "UiAutomator2")

    @property
    def device_name(self) -> str:
        return os.getenv("DEVICE_NAME", "Android Emulator")

    @property
    def app_path(self) -> Path:
        app_path = Path(os.getenv("APP_PATH", "demo_mobile_apps/mda-2.2.0-25.apk"))
        if not app_path.is_absolute():
            app_path = self.project_root / app_path
        return app_path.resolve()

    @property
    def artifacts_dir(self) -> Path:
        return self.project_root / os.getenv("ARTIFACTS_DIR", "artifacts")

    @property
    def input_screenshots_dir(self) -> Path:
        return self.project_root / os.getenv("INPUT_SCREENSHOTS_DIR", "artifacts/input_screenshots")

    @property
    def ssm_output_dir(self) -> Path:
        return self.project_root / os.getenv("SSM_OUTPUT_DIR", "artifacts/ssm_json_output")

    @property
    def manual_testcases_dir(self) -> Path:
        return self.project_root / os.getenv("MANUAL_TESTCASES_DIR", "artifacts/manual_testcases")

    @property
    def locator_output_dir(self) -> Path:
        return self.project_root / os.getenv("LOCATOR_OUTPUT_DIR", "artifacts/locator_output")

    @property
    def generated_scripts_dir(self) -> Path:
        return self.project_root / os.getenv("GENERATED_SCRIPTS_DIR", "artifacts/generated_appium_scripts")

    @property
    def review_reports_dir(self) -> Path:
        return self.project_root / os.getenv("REVIEW_REPORTS_DIR", "artifacts/review_reports")

    @property
    def test_reports_dir(self) -> Path:
        return self.project_root / os.getenv("TEST_REPORTS_DIR", "artifacts/test_execution_reports")

    @property
    def self_healing_enabled(self) -> bool:
        return _env_bool("SELF_HEALING_ENABLED", True)

    @property
    def healing_max_retries(self) -> int:
        return _env_int("HEALING_MAX_RETRIES", 3)

    @property
    def ai_vision_healing(self) -> bool:
        return _env_bool("AI_VISION_HEALING", True)

    @property
    def healing_repository_enabled(self) -> bool:
        return _env_bool("HEALING_REPOSITORY_ENABLED", True)

    @property
    def explicit_wait_timeout(self) -> int:
        return _env_int("EXPLICIT_WAIT_TIMEOUT", 10)

    @property
    def implicit_wait_timeout(self) -> int:
        return _env_int("IMPLICIT_WAIT_TIMEOUT", 5)

    @property
    def auto_open_browser(self) -> bool:
        return _env_bool("AUTO_OPEN_BROWSER", True)

    @property
    def log_level(self) -> str:
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def log_format(self) -> str:
        return os.getenv("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(message)s")

    @property
    def enable_llm_cache(self) -> bool:
        return _env_bool("ENABLE_LLM_CACHE", True)

    @property
    def cache_backend(self) -> str:
        return os.getenv("CACHE_BACKEND", "file")

    @property
    def cache_ttl(self) -> int:
        return _env_int("CACHE_TTL", 86400)

    @property
    def enable_token_tracking(self) -> bool:
        return _env_bool("ENABLE_TOKEN_TRACKING", True)

    @property
    def token_tracking_log(self) -> Path:
        return self.project_root / os.getenv("TOKEN_TRACKING_LOG", "artifacts/token_usage.log")


_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def load_environment(dotenv_path: Path | None = None) -> None:
    global _config
    _config = AppConfig(dotenv_path=dotenv_path)
