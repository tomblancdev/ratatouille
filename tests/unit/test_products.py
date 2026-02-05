"""🧪 Tests for Data Products module."""

import pytest

from ratatouille.products.permissions import PermissionManager
from ratatouille.products.registry import (
    ProductRegistry,
)


class TestProductRegistry:
    """Tests for ProductRegistry class."""

    @pytest.fixture
    def registry(self, tmp_path):
        """Create a temporary registry for testing."""
        db_path = tmp_path / "test_products.db"
        return ProductRegistry(db_path)

    def test_register_product(self, registry):
        """Test registering a new product."""
        product = registry.register_product(
            name="sales_kpis",
            owner_workspace="analytics",
            description="Daily sales KPIs",
            tags=["sales", "kpi"],
        )

        assert product.name == "sales_kpis"
        assert product.owner_workspace == "analytics"
        assert product.description == "Daily sales KPIs"
        assert "sales" in product.tags

    def test_register_duplicate_fails(self, registry):
        """Test that registering duplicate product fails."""
        registry.register_product(name="test", owner_workspace="ws1")

        with pytest.raises(ValueError, match="already exists"):
            registry.register_product(name="test", owner_workspace="ws2")

    def test_get_product(self, registry):
        """Test retrieving a product by name."""
        registry.register_product(name="test", owner_workspace="ws1")

        product = registry.get_product("test")
        assert product is not None
        assert product.name == "test"

        # Non-existent product
        assert registry.get_product("nonexistent") is None

    def test_list_products(self, registry):
        """Test listing products with filters."""
        registry.register_product(name="prod1", owner_workspace="ws1", tags=["tag1"])
        registry.register_product(name="prod2", owner_workspace="ws2", tags=["tag2"])
        registry.register_product(
            name="prod3", owner_workspace="ws1", tags=["tag1", "tag2"]
        )

        # All products
        all_products = registry.list_products()
        assert len(all_products) == 3

        # Filter by owner
        ws1_products = registry.list_products(owner_workspace="ws1")
        assert len(ws1_products) == 2

        # Filter by tag
        tag1_products = registry.list_products(tag="tag1")
        assert len(tag1_products) == 2

    def test_publish_version(self, registry):
        """Test publishing a product version."""
        registry.register_product(name="test", owner_workspace="ws1")

        version = registry.publish_version(
            product_name="test",
            version="1.0.0",
            source_workspace="ws1",
            source_table="gold.metrics",
            schema_snapshot={"col1": {"type": "string"}},
            s3_location="s3://warehouse/_products/test/v1.0.0/",
            row_count=1000,
        )

        assert version.version == "1.0.0"
        assert version.row_count == 1000

    def test_publish_version_wrong_workspace(self, registry):
        """Test that only owner can publish versions."""
        registry.register_product(name="test", owner_workspace="ws1")

        with pytest.raises(ValueError, match="Only owner workspace"):
            registry.publish_version(
                product_name="test",
                version="1.0.0",
                source_workspace="ws2",  # Wrong workspace!
                source_table="gold.metrics",
                schema_snapshot={},
                s3_location="s3://test/",
            )

    def test_get_latest_version(self, registry):
        """Test getting latest version by semver."""
        registry.register_product(name="test", owner_workspace="ws1")

        registry.publish_version(
            product_name="test",
            version="1.0.0",
            source_workspace="ws1",
            source_table="t",
            schema_snapshot={},
            s3_location="s3://v1/",
        )
        registry.publish_version(
            product_name="test",
            version="1.1.0",
            source_workspace="ws1",
            source_table="t",
            schema_snapshot={},
            s3_location="s3://v2/",
        )
        registry.publish_version(
            product_name="test",
            version="2.0.0",
            source_workspace="ws1",
            source_table="t",
            schema_snapshot={},
            s3_location="s3://v3/",
        )

        latest = registry.get_latest_version("test")
        assert latest.version == "2.0.0"

    def test_resolve_version_constraints(self, registry):
        """Test version constraint resolution."""
        registry.register_product(name="test", owner_workspace="ws1")

        for v in ["1.0.0", "1.1.0", "1.2.0", "2.0.0", "2.1.0"]:
            registry.publish_version(
                product_name="test",
                version=v,
                source_workspace="ws1",
                source_table="t",
                schema_snapshot={},
                s3_location=f"s3://v{v}/",
            )

        # Exact version
        assert registry.resolve_version("test", "1.1.0").version == "1.1.0"

        # Latest
        assert registry.resolve_version("test", "latest").version == "2.1.0"

        # Caret (^) - compatible with
        assert registry.resolve_version("test", "^1.0.0").version == "1.2.0"

        # Tilde (~) - patch only
        assert registry.resolve_version("test", "~1.1.0").version == "1.1.0"

        # Major wildcard
        assert registry.resolve_version("test", "1.x").version == "1.2.0"


class TestAccessControl:
    """Tests for access control."""

    @pytest.fixture
    def registry(self, tmp_path):
        db_path = tmp_path / "test_products.db"
        return ProductRegistry(db_path)

    def test_grant_access(self, registry):
        """Test granting access."""
        registry.register_product(name="test", owner_workspace="ws1")

        rule = registry.grant_access("test", "*", "read")
        assert rule.workspace_pattern == "*"
        assert rule.access_level == "read"

    def test_check_access_wildcard(self, registry):
        """Test wildcard access pattern."""
        registry.register_product(name="test", owner_workspace="ws1")
        registry.grant_access("test", "*", "read")

        assert registry.check_access("test", "any_workspace", "read") is True
        assert registry.check_access("test", "another", "read") is True

    def test_check_access_prefix_pattern(self, registry):
        """Test prefix pattern matching."""
        registry.register_product(name="test", owner_workspace="ws1")
        registry.grant_access("test", "analytics-*", "read")

        assert registry.check_access("test", "analytics-bi", "read") is True
        assert registry.check_access("test", "analytics-reporting", "read") is True
        assert registry.check_access("test", "finance", "read") is False

    def test_check_access_exact_match(self, registry):
        """Test exact workspace matching."""
        registry.register_product(name="test", owner_workspace="ws1")
        registry.grant_access("test", "finance", "write")

        assert registry.check_access("test", "finance", "read") is True
        assert registry.check_access("test", "finance", "write") is True
        assert registry.check_access("test", "finance-team", "read") is False

    def test_access_level_hierarchy(self, registry):
        """Test that higher access levels include lower ones."""
        registry.register_product(name="test", owner_workspace="ws1")
        registry.grant_access("test", "admin-ws", "admin")

        assert registry.check_access("test", "admin-ws", "read") is True
        assert registry.check_access("test", "admin-ws", "write") is True
        assert registry.check_access("test", "admin-ws", "admin") is True


class TestSubscriptions:
    """Tests for subscriptions."""

    @pytest.fixture
    def registry(self, tmp_path):
        db_path = tmp_path / "test_products.db"
        return ProductRegistry(db_path)

    def test_subscribe(self, registry):
        """Test subscribing to a product."""
        registry.register_product(name="test", owner_workspace="ws1")
        registry.grant_access("test", "*", "read")

        registry.subscribe(
            product_name="test",
            consumer_workspace="ws2",
            version_constraint="^1.0.0",
            local_alias="test_data",
        )

        subs = registry.get_subscriptions("ws2")
        assert len(subs) == 1
        assert subs[0]["product_name"] == "test"
        assert subs[0]["local_alias"] == "test_data"

    def test_subscribe_without_access_fails(self, registry):
        """Test that subscription requires access."""
        registry.register_product(name="test", owner_workspace="ws1")
        # No access granted!

        with pytest.raises(PermissionError):
            registry.subscribe(
                product_name="test",
                consumer_workspace="ws2",
            )


class TestPermissionManager:
    """Tests for PermissionManager."""

    @pytest.fixture
    def pm(self, tmp_path):
        db_path = tmp_path / "test_products.db"
        registry = ProductRegistry(db_path)
        return PermissionManager(registry)

    def test_convenience_methods(self, pm):
        """Test can_read, can_write, is_admin helpers."""
        pm.registry.register_product(name="test", owner_workspace="ws1")
        pm.grant("test", "readers", "read")
        pm.grant("test", "writers", "write")
        pm.grant("test", "admins", "admin")

        assert pm.can_read("readers", "test") is True
        assert pm.can_write("readers", "test") is False

        assert pm.can_read("writers", "test") is True
        assert pm.can_write("writers", "test") is True
        assert pm.is_admin("writers", "test") is False

        assert pm.is_admin("admins", "test") is True

    def test_check_returns_details(self, pm):
        """Test that check() returns detailed PermissionCheck."""
        pm.registry.register_product(name="test", owner_workspace="ws1")
        pm.grant("test", "analytics-*", "read")

        check = pm.check("analytics-bi", "test", "read")

        assert check.granted is True
        assert check.matching_rule == "analytics-*"
        assert check.effective_level == "read"
