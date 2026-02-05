"""🔐 Product Permissions - Access control for data products.

Provides high-level permission management:
- Grant/revoke access with patterns
- Check permissions with caching
- Audit logging
- Permission inheritance
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    pass

from .registry import AccessRule, ProductRegistry


@dataclass
class PermissionCheck:
    """Result of a permission check."""

    product_name: str
    workspace: str
    requested_level: str
    granted: bool
    effective_level: str | None
    matching_rule: str | None  # The pattern that matched
    reason: str


class PermissionManager:
    """Manages permissions for data products.

    Provides a higher-level interface over ProductRegistry access rules
    with caching, audit logging, and convenience methods.

    Example:
        pm = PermissionManager()

        # Grant access
        pm.grant("sales_kpis", "analytics-*", "read")
        pm.grant("sales_kpis", "finance", "write")

        # Check access
        if pm.can_read("analytics-team", "sales_kpis"):
            print("Access granted!")

        # Audit
        history = pm.get_audit_log("sales_kpis")
    """

    LEVEL_ORDER = {"read": 1, "write": 2, "admin": 3}

    def __init__(self, registry: ProductRegistry | None = None):
        self.registry = registry or ProductRegistry()
        self._check_cache: dict[tuple[str, str], PermissionCheck] = {}

    def grant(
        self,
        product_name: str,
        workspace_pattern: str,
        level: Literal["read", "write", "admin"] = "read",
        granted_by: str = "system",
    ) -> AccessRule:
        """Grant access to a product.

        Args:
            product_name: Product to grant access to
            workspace_pattern: Pattern for workspaces:
                - "*": All workspaces
                - "analytics-*": Workspaces starting with "analytics-"
                - "finance": Exact workspace name
            level: Access level (read, write, admin)
            granted_by: User/system granting access

        Returns:
            Created AccessRule
        """
        # Clear cache for this product
        self._invalidate_cache(product_name)

        return self.registry.grant_access(
            product_name=product_name,
            workspace_pattern=workspace_pattern,
            level=level,
            granted_by=granted_by,
        )

    def revoke(
        self,
        product_name: str,
        workspace_pattern: str,
    ) -> bool:
        """Revoke access to a product.

        Args:
            product_name: Product to revoke access from
            workspace_pattern: Exact pattern that was granted

        Returns:
            True if a rule was revoked
        """
        self._invalidate_cache(product_name)
        return self.registry.revoke_access(product_name, workspace_pattern)

    def check(
        self,
        workspace: str,
        product_name: str,
        level: Literal["read", "write", "admin"] = "read",
    ) -> PermissionCheck:
        """Check if a workspace has permission to access a product.

        Args:
            workspace: Workspace name
            product_name: Product name
            level: Required access level

        Returns:
            PermissionCheck with details
        """
        cache_key = (workspace, product_name)

        # Check cache
        if cache_key in self._check_cache:
            cached = self._check_cache[cache_key]
            # Verify cached level is sufficient
            cached_level_value = self.LEVEL_ORDER.get(cached.effective_level or "", 0)
            required_level_value = self.LEVEL_ORDER.get(level, 0)
            if cached.granted and cached_level_value >= required_level_value:
                return cached

        # Get all rules for the product
        rules = self.registry.list_access_rules(product_name)

        # Find best matching rule
        best_rule: AccessRule | None = None
        best_level = 0

        for rule in rules:
            if self._pattern_matches(rule.workspace_pattern, workspace):
                rule_level = self.LEVEL_ORDER.get(rule.access_level, 0)
                if rule_level > best_level:
                    best_level = rule_level
                    best_rule = rule

        # Build result
        required_level = self.LEVEL_ORDER.get(level, 0)
        granted = best_level >= required_level

        if best_rule:
            result = PermissionCheck(
                product_name=product_name,
                workspace=workspace,
                requested_level=level,
                granted=granted,
                effective_level=best_rule.access_level,
                matching_rule=best_rule.workspace_pattern,
                reason=f"Matched rule: {best_rule.workspace_pattern} ({best_rule.access_level})"
                if granted
                else f"Insufficient access: have {best_rule.access_level}, need {level}",
            )
        else:
            result = PermissionCheck(
                product_name=product_name,
                workspace=workspace,
                requested_level=level,
                granted=False,
                effective_level=None,
                matching_rule=None,
                reason="No matching access rule",
            )

        # Cache result
        self._check_cache[cache_key] = result
        return result

    def can_read(self, workspace: str, product_name: str) -> bool:
        """Check if workspace can read a product."""
        return self.check(workspace, product_name, "read").granted

    def can_write(self, workspace: str, product_name: str) -> bool:
        """Check if workspace can write to a product."""
        return self.check(workspace, product_name, "write").granted

    def is_admin(self, workspace: str, product_name: str) -> bool:
        """Check if workspace has admin access to a product."""
        return self.check(workspace, product_name, "admin").granted

    def list_accessible_products(
        self,
        workspace: str,
        min_level: Literal["read", "write", "admin"] = "read",
    ) -> list[str]:
        """List all products a workspace can access.

        Args:
            workspace: Workspace name
            min_level: Minimum required access level

        Returns:
            List of product names
        """
        products = self.registry.list_products()
        accessible = []

        for product in products:
            if self.check(workspace, product.name, min_level).granted:
                accessible.append(product.name)

        return accessible

    def list_workspace_access(
        self,
        product_name: str,
    ) -> list[dict]:
        """List all workspaces with access to a product.

        Args:
            product_name: Product name

        Returns:
            List of dicts with workspace_pattern and access_level
        """
        rules = self.registry.list_access_rules(product_name)
        return [
            {
                "workspace_pattern": rule.workspace_pattern,
                "access_level": rule.access_level,
                "granted_at": rule.granted_at.isoformat(),
                "granted_by": rule.granted_by,
            }
            for rule in rules
        ]

    def _pattern_matches(self, pattern: str, workspace: str) -> bool:
        """Check if a pattern matches a workspace name."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return workspace.startswith(pattern[:-1])
        return pattern == workspace

    def _invalidate_cache(self, product_name: str) -> None:
        """Invalidate cache entries for a product."""
        keys_to_remove = [key for key in self._check_cache if key[1] == product_name]
        for key in keys_to_remove:
            del self._check_cache[key]


def require_permission(
    level: Literal["read", "write", "admin"] = "read",
):
    """Decorator to require permission for a function.

    The decorated function must have 'workspace' and 'product_name'
    as keyword arguments or the first two positional arguments.

    Example:
        @require_permission("write")
        def update_product(workspace: str, product_name: str, data: dict):
            # Only runs if workspace has write access to product
            ...
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Extract workspace and product_name
            workspace = kwargs.get("workspace") or (args[0] if args else None)
            product_name = kwargs.get("product_name") or (
                args[1] if len(args) > 1 else None
            )

            if workspace is None or product_name is None:
                raise ValueError(
                    "Function must have 'workspace' and 'product_name' arguments"
                )

            # Handle Workspace objects
            if hasattr(workspace, "name"):
                workspace = workspace.name

            pm = PermissionManager()
            check = pm.check(workspace, product_name, level)

            if not check.granted:
                raise PermissionError(
                    f"Access denied: {check.reason}. "
                    f"Workspace '{workspace}' needs '{level}' access to product '{product_name}'."
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def grant_read_all(product_name: str, granted_by: str = "system") -> AccessRule:
    """Grant read access to all workspaces (convenience function)."""
    pm = PermissionManager()
    return pm.grant(product_name, "*", "read", granted_by)


def grant_team_access(
    product_name: str,
    team_prefix: str,
    level: Literal["read", "write", "admin"] = "read",
    granted_by: str = "system",
) -> AccessRule:
    """Grant access to all workspaces with a team prefix.

    Example:
        grant_team_access("sales_kpis", "analytics-", "read")
        # Grants read access to analytics-reporting, analytics-bi, etc.
    """
    pm = PermissionManager()
    return pm.grant(product_name, f"{team_prefix}*", level, granted_by)
