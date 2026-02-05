"""📊 Resource Profiles - Predefined configurations for different VM sizes."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

ProfileName = Literal["tiny", "small", "medium", "large"]

# Profile descriptions for documentation
PROFILES: dict[ProfileName, str] = {
    "tiny": "4GB RAM - Raspberry Pi, minimal VMs",
    "small": "20GB RAM - Typical self-hosted setup (default)",
    "medium": "64GB RAM - Production workloads",
    "large": "128GB+ RAM - Large-scale processing",
}


def get_profiles_dir() -> Path:
    """Get the profiles directory path."""
    # Check for config in current directory first
    local_config = Path("config/profiles")
    if local_config.exists():
        return local_config

    # Check /app/config (container)
    app_config = Path("/app/config/profiles")
    if app_config.exists():
        return app_config

    # Fallback to package directory
    package_dir = Path(__file__).parent.parent.parent.parent
    return package_dir / "config" / "profiles"


def get_profile_path(profile: ProfileName) -> Path:
    """Get the path to a profile YAML file."""
    profiles_dir = get_profiles_dir()
    path = profiles_dir / f"{profile}.yaml"

    if not path.exists():
        raise FileNotFoundError(
            f"Profile '{profile}' not found at {path}. "
            f"Available profiles: {list(PROFILES.keys())}"
        )

    return path


def load_profile(profile: ProfileName) -> dict:
    """Load a profile as a dictionary."""
    import yaml

    path = get_profile_path(profile)
    with open(path) as f:
        return yaml.safe_load(f)


def list_profiles() -> list[dict]:
    """List all available profiles with their descriptions."""
    result = []
    for name, description in PROFILES.items():
        try:
            get_profile_path(name)
            exists = True
        except FileNotFoundError:
            exists = False

        result.append(
            {
                "name": name,
                "description": description,
                "available": exists,
            }
        )
    return result
