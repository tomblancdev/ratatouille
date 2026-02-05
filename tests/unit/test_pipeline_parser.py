"""🧪 Tests for SQL Pipeline Parser."""

import pytest

from ratatouille.pipeline.parser import ParsedPipeline, SQLParser


class TestSQLParser:
    """Tests for SQLParser class."""

    @pytest.fixture
    def parser(self):
        return SQLParser()

    def test_parse_simple_sql(self, parser):
        """Test parsing simple SQL without metadata."""
        sql = "SELECT * FROM users"
        result = parser.parse_string(sql)

        assert isinstance(result, ParsedPipeline)
        assert result.raw_sql == sql
        assert result.name == "inline"  # default name
        assert result.materialized == "table"  # default

    def test_parse_with_metadata(self, parser):
        """Test parsing SQL with metadata comments."""
        sql = """
-- @name: silver_sales
-- @materialized: incremental
-- @unique_key: txn_id
-- @partition_by: _date
-- @owner: data-team

SELECT * FROM bronze.raw_sales
"""
        result = parser.parse_string(sql)

        assert result.name == "silver_sales"
        assert result.materialized == "incremental"
        assert "txn_id" in result.unique_key
        assert "_date" in result.partition_by
        assert result.owner == "data-team"

    def test_parse_extracts_refs(self, parser):
        """Test that {{ ref() }} calls are extracted."""
        sql = """
SELECT *
FROM {{ ref('bronze.sales') }}
JOIN {{ ref('silver.products') }} ON ...
"""
        result = parser.parse_string(sql)

        assert "bronze.sales" in result.dependencies
        assert "silver.products" in result.dependencies
        assert len(result.dependencies) == 2

    def test_is_incremental_detection(self, parser):
        """Test detection of incremental pipelines."""
        incremental_sql = """
-- @materialized: incremental
SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
"""
        result = parser.parse_string(incremental_sql)
        assert result.is_incremental is True

        non_incremental_sql = "SELECT * FROM source"
        result = parser.parse_string(non_incremental_sql)
        assert result.is_incremental is False

    def test_compile_resolves_refs(self, parser):
        """Test that compile() resolves {{ ref() }} calls."""
        sql = "SELECT * FROM {{ ref('bronze.sales') }}"
        parsed = parser.parse_string(sql)

        compiled = parser.compile(parsed)

        # ref() should be resolved to S3 path
        assert "bronze" in compiled and "sales" in compiled
        assert "{{ ref" not in compiled

    def test_compile_incremental_false(self, parser):
        """Test compile with is_incremental=False removes conditional."""
        sql = """
SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
"""
        parsed = parser.parse_string(sql)
        compiled = parser.compile(parsed, is_incremental=False)

        assert "WHERE updated_at" not in compiled
        assert "watermark" not in compiled

    def test_compile_incremental_true(self, parser):
        """Test compile with is_incremental=True includes conditional."""
        sql = """
-- @materialized: incremental
SELECT * FROM source
{% if is_incremental() %}
  WHERE updated_at > '{{ watermark("updated_at") }}'
{% endif %}
"""
        parsed = parser.parse_string(sql)
        watermarks = {"updated_at": "2024-01-01 00:00:00"}
        compiled = parser.compile(parsed, is_incremental=True, watermarks=watermarks)

        assert "WHERE updated_at > '2024-01-01 00:00:00'" in compiled


class TestParsedPipeline:
    """Tests for ParsedPipeline dataclass."""

    def test_incremental_flag(self):
        """Test that is_incremental is set based on materialized."""
        # Incremental materialization
        parsed = ParsedPipeline(
            name="silver_sales",
            materialized="incremental",
            raw_sql="SELECT 1",
        )
        assert parsed.is_incremental is True

        # Table materialization
        parsed = ParsedPipeline(
            name="gold_kpis",
            materialized="table",
            raw_sql="SELECT 1",
        )
        assert parsed.is_incremental is False

    def test_dependencies_list(self):
        """Test dependencies field."""
        parsed = ParsedPipeline(
            name="silver_sales",
            raw_sql="SELECT 1",
            dependencies=["bronze.raw_sales", "bronze.products"],
        )
        assert len(parsed.dependencies) == 2
        assert "bronze.raw_sales" in parsed.dependencies
