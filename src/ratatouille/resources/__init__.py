"""⚙️ Resource Management - Configurable limits for any VM size.

Profiles:
- tiny: 4GB VM (Raspberry Pi, etc.)
- small: 20GB VM (default)
- medium: 64GB VM
- large: 128GB+ VM

All limits are configurable per-workspace.
"""

from .config import ResourceConfig, get_resource_config
from .profiles import PROFILES, load_profile

__all__ = [
    "ResourceConfig",
    "get_resource_config",
    "load_profile",
    "PROFILES",
]
