"""Backward-compatible import surface for centralized app configuration."""

from config.app_config import AppConfig as Config
from config.app_config import get_config, load_environment

__all__ = ["Config", "get_config", "load_environment"]
