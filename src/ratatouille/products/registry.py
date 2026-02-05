"""📦 Product Registry - Central catalog for data products.

Uses SQLite for metadata storage with support for:
- Product registration and versioning (semver)
- Schema snapshots at publish time
- Access control rules
- SLA tracking
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from packaging import version as semver


@dataclass
class ProductVersion:
    """A specific version of a data product."""

    product_name: str
    version: str
    source_workspace: str
    source_table: str
    schema_snapshot: dict[str, Any]  # Column names, types, descriptions
    row_count: int
    s3_location: str
    nessie_commit: str | None
    published_at: datetime
    published_by: str
    changelog: str = ""

    @property
    def semver(self) -> semver.Version:
        """Parse version as semver."""
        return semver.parse(self.version)


@dataclass
class Product:
    """A data product with metadata and access rules."""

    name: str
    owner_workspace: str
    description: str
    tags: list[str] = field(default_factory=list)
    sla_freshness_hours: int | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_deprecated: bool = False
    deprecation_message: str | None = None


@dataclass
class AccessRule:
    """Access control rule for a product."""

    product_name: str
    workspace_pattern: (
        str  # "*" for all, "analytics-*" for pattern, "finance" for exact
    )
    access_level: Literal["read", "write", "admin"]
    granted_at: datetime = field(default_factory=datetime.now)
    granted_by: str = "system"


class ProductRegistry:
    """Central registry for data products.

    Stores product metadata, versions, and access rules in SQLite.
    Each workspace can publish products that other workspaces consume.

    Example:
        registry = ProductRegistry()

        # Register a new product
        registry.register_product(
            name="sales_kpis",
            owner_workspace="analytics",
            description="Daily sales KPIs"
        )

        # Publish a version
        registry.publish_version(
            product_name="sales_kpis",
            version="1.0.0",
            source_workspace="analytics",
            source_table="gold.daily_sales",
            schema_snapshot={"sale_date": "date", "revenue": "decimal(14,2)"},
            s3_location="s3://warehouse/products/sales_kpis/v1.0.0/"
        )

        # Grant access
        registry.grant_access("sales_kpis", workspace_pattern="*", level="read")
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | Path | None = None):
        """Initialize registry with SQLite database.

        Args:
            db_path: Path to SQLite database (default: from env or /data/products.db)
        """
        if db_path is None:
            db_path = os.getenv(
                "PRODUCT_REGISTRY_DB",
                str(Path(os.getenv("DATA_DIR", "/data")) / "products.db"),
            )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.executescript("""
                -- Schema versioning
                CREATE TABLE IF NOT EXISTS _schema_version (
                    version INTEGER PRIMARY KEY
                );

                -- Products metadata
                CREATE TABLE IF NOT EXISTS products (
                    name TEXT PRIMARY KEY,
                    owner_workspace TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    tags TEXT DEFAULT '[]',  -- JSON array
                    sla_freshness_hours INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_deprecated INTEGER DEFAULT 0,
                    deprecation_message TEXT
                );

                -- Product versions (immutable)
                CREATE TABLE IF NOT EXISTS product_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_workspace TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    schema_snapshot TEXT NOT NULL,  -- JSON
                    row_count INTEGER DEFAULT 0,
                    s3_location TEXT NOT NULL,
                    nessie_commit TEXT,
                    published_at TEXT NOT NULL,
                    published_by TEXT NOT NULL,
                    changelog TEXT DEFAULT '',
                    FOREIGN KEY (product_name) REFERENCES products(name),
                    UNIQUE (product_name, version)
                );

                -- Access rules
                CREATE TABLE IF NOT EXISTS access_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    workspace_pattern TEXT NOT NULL,
                    access_level TEXT NOT NULL CHECK (access_level IN ('read', 'write', 'admin')),
                    granted_at TEXT NOT NULL,
                    granted_by TEXT NOT NULL,
                    FOREIGN KEY (product_name) REFERENCES products(name),
                    UNIQUE (product_name, workspace_pattern)
                );

                -- Subscriptions (which workspaces consume which products)
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_name TEXT NOT NULL,
                    consumer_workspace TEXT NOT NULL,
                    version_constraint TEXT DEFAULT 'latest',
                    local_alias TEXT,
                    subscribed_at TEXT NOT NULL,
                    FOREIGN KEY (product_name) REFERENCES products(name),
                    UNIQUE (product_name, consumer_workspace)
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_versions_product ON product_versions(product_name);
                CREATE INDEX IF NOT EXISTS idx_versions_published ON product_versions(published_at);
                CREATE INDEX IF NOT EXISTS idx_access_product ON access_rules(product_name);
                CREATE INDEX IF NOT EXISTS idx_subs_consumer ON subscriptions(consumer_workspace);
            """)

            # Check/update schema version
            result = conn.execute("SELECT MAX(version) FROM _schema_version").fetchone()
            if result[0] is None:
                conn.execute(
                    "INSERT INTO _schema_version (version) VALUES (?)",
                    (self.SCHEMA_VERSION,),
                )

    # ========== Product Management ==========

    def register_product(
        self,
        name: str,
        owner_workspace: str,
        description: str = "",
        tags: list[str] | None = None,
        sla_freshness_hours: int | None = None,
    ) -> Product:
        """Register a new data product.

        Args:
            name: Unique product identifier
            owner_workspace: Workspace that owns this product
            description: Human-readable description
            tags: Searchable tags
            sla_freshness_hours: Expected data freshness SLA

        Returns:
            Created Product instance

        Raises:
            ValueError: If product already exists
        """
        now = datetime.now().isoformat()
        tags = tags or []

        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO products (name, owner_workspace, description, tags,
                                         sla_freshness_hours, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        owner_workspace,
                        description,
                        json.dumps(tags),
                        sla_freshness_hours,
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as err:
                raise ValueError(f"Product '{name}' already exists") from err

        return Product(
            name=name,
            owner_workspace=owner_workspace,
            description=description,
            tags=tags,
            sla_freshness_hours=sla_freshness_hours,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def get_product(self, name: str) -> Product | None:
        """Get product metadata by name."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM products WHERE name = ?", (name,)
            ).fetchone()

            if row is None:
                return None

            return Product(
                name=row["name"],
                owner_workspace=row["owner_workspace"],
                description=row["description"],
                tags=json.loads(row["tags"]),
                sla_freshness_hours=row["sla_freshness_hours"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                is_deprecated=bool(row["is_deprecated"]),
                deprecation_message=row["deprecation_message"],
            )

    def list_products(
        self,
        owner_workspace: str | None = None,
        tag: str | None = None,
        include_deprecated: bool = False,
    ) -> list[Product]:
        """List products with optional filters."""
        query = "SELECT * FROM products WHERE 1=1"
        params: list[Any] = []

        if owner_workspace:
            query += " AND owner_workspace = ?"
            params.append(owner_workspace)

        if tag:
            query += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')

        if not include_deprecated:
            query += " AND is_deprecated = 0"

        query += " ORDER BY name"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                Product(
                    name=row["name"],
                    owner_workspace=row["owner_workspace"],
                    description=row["description"],
                    tags=json.loads(row["tags"]),
                    sla_freshness_hours=row["sla_freshness_hours"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    is_deprecated=bool(row["is_deprecated"]),
                    deprecation_message=row["deprecation_message"],
                )
                for row in rows
            ]

    def deprecate_product(self, name: str, message: str = "") -> None:
        """Mark a product as deprecated."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE products
                SET is_deprecated = 1, deprecation_message = ?, updated_at = ?
                WHERE name = ?
                """,
                (message, datetime.now().isoformat(), name),
            )

    # ========== Version Management ==========

    def publish_version(
        self,
        product_name: str,
        version: str,
        source_workspace: str,
        source_table: str,
        schema_snapshot: dict[str, Any],
        s3_location: str,
        row_count: int = 0,
        nessie_commit: str | None = None,
        published_by: str = "system",
        changelog: str = "",
    ) -> ProductVersion:
        """Publish a new version of a product.

        Args:
            product_name: Product to publish version for
            version: Semver version string (e.g., "1.2.0")
            source_workspace: Workspace publishing this version
            source_table: Source table (e.g., "gold.daily_sales")
            schema_snapshot: Schema at publish time
            s3_location: S3 path to versioned data
            row_count: Number of rows in this version
            nessie_commit: Optional Nessie commit hash for reproducibility
            published_by: User/system publishing
            changelog: What changed in this version

        Returns:
            Created ProductVersion

        Raises:
            ValueError: If product doesn't exist or version already exists
        """
        # Validate semver
        try:
            semver.parse(version)
        except Exception as err:
            raise ValueError(f"Invalid semver version: {version}") from err

        now = datetime.now().isoformat()

        with self._connect() as conn:
            # Check product exists
            product = conn.execute(
                "SELECT owner_workspace FROM products WHERE name = ?", (product_name,)
            ).fetchone()

            if product is None:
                raise ValueError(
                    f"Product '{product_name}' not found. Register it first."
                )

            if product["owner_workspace"] != source_workspace:
                raise ValueError(
                    f"Only owner workspace '{product['owner_workspace']}' can publish versions, "
                    f"not '{source_workspace}'"
                )

            try:
                conn.execute(
                    """
                    INSERT INTO product_versions
                    (product_name, version, source_workspace, source_table, schema_snapshot,
                     row_count, s3_location, nessie_commit, published_at, published_by, changelog)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_name,
                        version,
                        source_workspace,
                        source_table,
                        json.dumps(schema_snapshot),
                        row_count,
                        s3_location,
                        nessie_commit,
                        now,
                        published_by,
                        changelog,
                    ),
                )
            except sqlite3.IntegrityError as err:
                raise ValueError(
                    f"Version {version} already exists for product '{product_name}'"
                ) from err

            # Update product timestamp
            conn.execute(
                "UPDATE products SET updated_at = ? WHERE name = ?", (now, product_name)
            )

        return ProductVersion(
            product_name=product_name,
            version=version,
            source_workspace=source_workspace,
            source_table=source_table,
            schema_snapshot=schema_snapshot,
            row_count=row_count,
            s3_location=s3_location,
            nessie_commit=nessie_commit,
            published_at=datetime.fromisoformat(now),
            published_by=published_by,
            changelog=changelog,
        )

    def get_version(self, product_name: str, version: str) -> ProductVersion | None:
        """Get a specific version of a product."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM product_versions WHERE product_name = ? AND version = ?",
                (product_name, version),
            ).fetchone()

            if row is None:
                return None

            return self._row_to_version(row)

    def get_latest_version(self, product_name: str) -> ProductVersion | None:
        """Get the latest version of a product (by semver, not date)."""
        versions = self.list_versions(product_name)
        if not versions:
            return None

        return max(versions, key=lambda v: v.semver)

    def list_versions(self, product_name: str) -> list[ProductVersion]:
        """List all versions of a product."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM product_versions WHERE product_name = ? ORDER BY published_at DESC",
                (product_name,),
            ).fetchall()

            return [self._row_to_version(row) for row in rows]

    def resolve_version(
        self, product_name: str, constraint: str = "latest"
    ) -> ProductVersion | None:
        """Resolve a version constraint to a specific version.

        Args:
            product_name: Product name
            constraint: Version constraint:
                - "latest": Most recent version
                - "1.2.3": Exact version
                - "^1.2.0": Compatible with (>=1.2.0, <2.0.0)
                - "~1.2.0": Patch-level changes only (>=1.2.0, <1.3.0)
                - "1.x": Any 1.x version
                - ">=1.2.0": Greater than or equal

        Returns:
            Resolved ProductVersion or None
        """
        if constraint == "latest":
            return self.get_latest_version(product_name)

        versions = self.list_versions(product_name)
        if not versions:
            return None

        # Exact version (but not patterns like "1.x")
        if (
            constraint.replace(".", "").replace("-", "").replace("+", "").isalnum()
            and not constraint.endswith(".x")
            and not constraint.startswith(("^", "~", ">", "<"))
        ):
            for v in versions:
                if v.version == constraint:
                    return v
            return None

        # Parse constraint
        matching = []
        for v in versions:
            if self._matches_constraint(v.version, constraint):
                matching.append(v)

        if not matching:
            return None

        return max(matching, key=lambda v: v.semver)

    def _matches_constraint(self, version_str: str, constraint: str) -> bool:
        """Check if a version matches a constraint."""
        v = semver.parse(version_str)

        # Handle x.y.z format
        if constraint.endswith(".x"):
            prefix = constraint[:-2]
            parts = prefix.split(".")
            if len(parts) == 1:
                return v.major == int(parts[0])
            elif len(parts) == 2:
                return v.major == int(parts[0]) and v.minor == int(parts[1])

        # Caret (^) - compatible with
        if constraint.startswith("^"):
            base = semver.parse(constraint[1:])
            return v >= base and v.major == base.major

        # Tilde (~) - patch only
        if constraint.startswith("~"):
            base = semver.parse(constraint[1:])
            return v >= base and v.major == base.major and v.minor == base.minor

        # Comparison operators
        if constraint.startswith(">="):
            return v >= semver.parse(constraint[2:])
        if constraint.startswith(">"):
            return v > semver.parse(constraint[1:])
        if constraint.startswith("<="):
            return v <= semver.parse(constraint[2:])
        if constraint.startswith("<"):
            return v < semver.parse(constraint[1:])

        return False

    def _row_to_version(self, row: sqlite3.Row) -> ProductVersion:
        """Convert database row to ProductVersion."""
        return ProductVersion(
            product_name=row["product_name"],
            version=row["version"],
            source_workspace=row["source_workspace"],
            source_table=row["source_table"],
            schema_snapshot=json.loads(row["schema_snapshot"]),
            row_count=row["row_count"],
            s3_location=row["s3_location"],
            nessie_commit=row["nessie_commit"],
            published_at=datetime.fromisoformat(row["published_at"]),
            published_by=row["published_by"],
            changelog=row["changelog"],
        )

    # ========== Access Control ==========

    def grant_access(
        self,
        product_name: str,
        workspace_pattern: str,
        level: Literal["read", "write", "admin"] = "read",
        granted_by: str = "system",
    ) -> AccessRule:
        """Grant access to a product.

        Args:
            product_name: Product to grant access to
            workspace_pattern: Workspace pattern ("*", "analytics-*", "finance")
            level: Access level
            granted_by: User granting access

        Returns:
            Created AccessRule
        """
        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO access_rules
                (product_name, workspace_pattern, access_level, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_name, workspace_pattern, level, now, granted_by),
            )

        return AccessRule(
            product_name=product_name,
            workspace_pattern=workspace_pattern,
            access_level=level,
            granted_at=datetime.fromisoformat(now),
            granted_by=granted_by,
        )

    def revoke_access(self, product_name: str, workspace_pattern: str) -> bool:
        """Revoke access to a product."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM access_rules WHERE product_name = ? AND workspace_pattern = ?",
                (product_name, workspace_pattern),
            )
            return cursor.rowcount > 0

    def check_access(
        self,
        product_name: str,
        workspace: str,
        required_level: Literal["read", "write", "admin"] = "read",
    ) -> bool:
        """Check if a workspace has access to a product.

        Args:
            product_name: Product to check
            workspace: Workspace requesting access
            required_level: Minimum required access level

        Returns:
            True if access is granted
        """
        level_order = {"read": 1, "write": 2, "admin": 3}

        with self._connect() as conn:
            rules = conn.execute(
                "SELECT * FROM access_rules WHERE product_name = ?", (product_name,)
            ).fetchall()

            for rule in rules:
                pattern = rule["workspace_pattern"]

                # Check if pattern matches workspace
                if self._pattern_matches(pattern, workspace):
                    rule_level = level_order.get(rule["access_level"], 0)
                    required = level_order.get(required_level, 0)
                    if rule_level >= required:
                        return True

        return False

    def _pattern_matches(self, pattern: str, workspace: str) -> bool:
        """Check if a pattern matches a workspace name."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return workspace.startswith(pattern[:-1])
        return pattern == workspace

    def list_access_rules(self, product_name: str) -> list[AccessRule]:
        """List all access rules for a product."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM access_rules WHERE product_name = ?", (product_name,)
            ).fetchall()

            return [
                AccessRule(
                    product_name=row["product_name"],
                    workspace_pattern=row["workspace_pattern"],
                    access_level=row["access_level"],
                    granted_at=datetime.fromisoformat(row["granted_at"]),
                    granted_by=row["granted_by"],
                )
                for row in rows
            ]

    # ========== Subscriptions ==========

    def subscribe(
        self,
        product_name: str,
        consumer_workspace: str,
        version_constraint: str = "latest",
        local_alias: str | None = None,
    ) -> None:
        """Subscribe a workspace to a product.

        Args:
            product_name: Product to subscribe to
            consumer_workspace: Workspace subscribing
            version_constraint: Version constraint (default: "latest")
            local_alias: Optional local name for the product
        """
        # Verify access
        if not self.check_access(product_name, consumer_workspace, "read"):
            raise PermissionError(
                f"Workspace '{consumer_workspace}' does not have access to product '{product_name}'"
            )

        now = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO subscriptions
                (product_name, consumer_workspace, version_constraint, local_alias, subscribed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    product_name,
                    consumer_workspace,
                    version_constraint,
                    local_alias,
                    now,
                ),
            )

    def unsubscribe(self, product_name: str, consumer_workspace: str) -> bool:
        """Unsubscribe a workspace from a product."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM subscriptions WHERE product_name = ? AND consumer_workspace = ?",
                (product_name, consumer_workspace),
            )
            return cursor.rowcount > 0

    def get_subscriptions(self, consumer_workspace: str) -> list[dict[str, Any]]:
        """Get all subscriptions for a workspace."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT s.*, p.description, p.owner_workspace, p.sla_freshness_hours
                FROM subscriptions s
                JOIN products p ON s.product_name = p.name
                WHERE s.consumer_workspace = ?
                """,
                (consumer_workspace,),
            ).fetchall()

            return [
                {
                    "product_name": row["product_name"],
                    "version_constraint": row["version_constraint"],
                    "local_alias": row["local_alias"],
                    "subscribed_at": row["subscribed_at"],
                    "owner_workspace": row["owner_workspace"],
                    "description": row["description"],
                    "sla_freshness_hours": row["sla_freshness_hours"],
                }
                for row in rows
            ]

    def get_subscribers(self, product_name: str) -> list[str]:
        """Get all workspaces subscribed to a product."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT consumer_workspace FROM subscriptions WHERE product_name = ?",
                (product_name,),
            ).fetchall()
            return [row["consumer_workspace"] for row in rows]
