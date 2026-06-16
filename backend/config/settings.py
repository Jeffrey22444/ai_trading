"""
Configuration loading module
"""
from .agent_config import get_config, reload_config as reload_app_config

# Export main configuration (lazy loading)
config = get_config()


def reload_config():
    """Reload config/agent.yaml into the shared in-memory config object."""
    return reload_app_config()
