"""🧪 Pytest configuration and shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def workspaces_dir(project_root):
    """Get workspaces directory."""
    return project_root / "workspaces"


@pytest.fixture
def test_workspace(tmp_path):
    """Create a temporary test workspace."""
    from ratatouille.workspace.manager import Workspace

    return Workspace.create(
        name="test",
        base_dir=tmp_path,
        description="Test workspace",
    )


@pytest.fixture
def sample_sql_pipeline():
    """Sample SQL pipeline content."""
    return """
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT
    txn_id,
    store_id,
    product_id,
    quantity,
    unit_price,
    quantity * unit_price AS total_amount,
    CAST(transaction_time AS DATE) AS _date
FROM {{ ref('bronze.raw_sales') }}
WHERE quantity > 0
  AND unit_price > 0
{% if is_incremental() %}
  AND transaction_time > '{{ watermark("transaction_time") }}'
{% endif %}
"""


@pytest.fixture
def sample_yaml_config():
    """Sample YAML pipeline config."""
    return """
description: |
  Cleaned and validated sales transactions.

owner: data-team@acme.com

columns:
  - name: txn_id
    type: string
    description: Unique transaction identifier
    tests: [not_null, unique]

  - name: total_amount
    type: decimal(12,2)
    description: Total transaction amount
    tests: [not_null, positive]

freshness:
  warn_after:
    hours: 6
  error_after:
    hours: 24

tests:
  - name: total_equals_qty_times_price
    sql: |
      SELECT COUNT(*)
      FROM {{ this }}
      WHERE ABS(total_amount - quantity * unit_price) > 0.01
    expect: 0
"""


# Environment setup for tests
@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, tmp_path):
    """Set up environment variables for tests."""
    # Use temp paths for data
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PRODUCT_REGISTRY_DB", str(tmp_path / "products.db"))

    # Default S3 config (will be overridden in integration tests)
    monkeypatch.setenv("S3_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("S3_ACCESS_KEY", "test")
    monkeypatch.setenv("S3_SECRET_KEY", "test123")
    monkeypatch.setenv("ICEBERG_WAREHOUSE", "s3://test-warehouse")
    monkeypatch.setenv("NESSIE_URI", "http://localhost:19120/api/v2")
