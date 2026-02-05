"""📝 SQL Template Parser - dbt-like Jinja templating for SQL.

Supports:
- {{ ref('bronze.sales') }} - Reference another table
- {% if is_incremental() %} - Conditional incremental logic
- {{ watermark('column') }} - Get the last processed value
- {{ this }} - Reference the target table
- {{ run_started_at }} - Current run timestamp
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from jinja2 import BaseLoader, Environment, TemplateSyntaxError, Undefined

if TYPE_CHECKING:
    from ratatouille.workspace.manager import Workspace


@dataclass
class ParsedPipeline:
    """Result of parsing a SQL pipeline file."""

    # Metadata from SQL comments
    name: str
    materialized: str = "table"  # table, view, incremental
    unique_key: list[str] = field(default_factory=list)
    partition_by: list[str] = field(default_factory=list)
    owner: str | None = None

    # Parsed content
    raw_sql: str = ""
    dependencies: list[str] = field(default_factory=list)

    # Computed
    is_incremental: bool = False

    def __post_init__(self):
        self.is_incremental = self.materialized == "incremental"


class PipelineTemplateLoader(BaseLoader):
    """Jinja2 loader that returns SQL templates as-is."""

    def __init__(self, source: str):
        self.source = source

    def get_source(self, environment: Environment, template: str):
        return self.source, None, lambda: True


class SQLParser:
    """Parse SQL pipeline files with dbt-like templating.

    Example:
        parser = SQLParser(workspace)
        parsed = parser.parse_file("pipelines/silver/sales.sql")
        sql = parser.compile(parsed, is_incremental=True)
    """

    # Regex for metadata comments like -- @name: silver_sales
    METADATA_PATTERN = re.compile(r"^--\s*@(\w+):\s*(.+)$", re.MULTILINE)

    def __init__(self, workspace: Workspace | None = None):
        self.workspace = workspace
        self._dependencies: list[str] = []
        self._env = self._create_jinja_env()

    def _create_jinja_env(self) -> Environment:
        """Create Jinja2 environment with custom functions."""
        env = Environment(
            loader=BaseLoader(),
            # Use {% %} for blocks, {{ }} for expressions
            block_start_string="{%",
            block_end_string="%}",
            variable_start_string="{{",
            variable_end_string="}}",
            comment_start_string="{#",
            comment_end_string="#}",
            # Don't auto-escape SQL
            autoescape=False,
            # Keep undefined references for later processing
            undefined=Undefined,
        )
        return env

    def parse_file(self, path: str) -> ParsedPipeline:
        """Parse a SQL pipeline file.

        Args:
            path: Path to the SQL file

        Returns:
            ParsedPipeline with metadata and dependencies
        """
        with open(path) as f:
            content = f.read()

        return self.parse_string(content, name=path)

    def parse_string(self, sql: str, name: str = "inline") -> ParsedPipeline:
        """Parse a SQL string.

        Args:
            sql: SQL content with templates
            name: Pipeline name (default: filename or 'inline')

        Returns:
            ParsedPipeline with metadata and dependencies
        """
        # Extract metadata from comments
        metadata = self._extract_metadata(sql)

        # Get pipeline name from metadata or filename
        pipeline_name = metadata.get("name", name.replace(".sql", "").split("/")[-1])

        # Parse unique_key and partition_by as lists
        unique_key = metadata.get("unique_key", "")
        if isinstance(unique_key, str):
            unique_key = [k.strip() for k in unique_key.split(",") if k.strip()]

        partition_by = metadata.get("partition_by", "")
        if isinstance(partition_by, str):
            partition_by = [k.strip() for k in partition_by.split(",") if k.strip()]

        # Extract dependencies from {{ ref() }} calls
        dependencies = self._extract_dependencies(sql)

        return ParsedPipeline(
            name=pipeline_name,
            materialized=metadata.get("materialized", "table"),
            unique_key=unique_key,
            partition_by=partition_by,
            owner=metadata.get("owner"),
            raw_sql=sql,
            dependencies=dependencies,
        )

    def _extract_metadata(self, sql: str) -> dict[str, str]:
        """Extract metadata from SQL comment headers."""
        metadata = {}
        for match in self.METADATA_PATTERN.finditer(sql):
            key = match.group(1).lower()
            value = match.group(2).strip()
            metadata[key] = value
        return metadata

    def _extract_dependencies(self, sql: str) -> list[str]:
        """Extract table references from {{ ref('table') }} calls."""
        # Match ref('table') or ref("table")
        pattern = re.compile(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}")
        return list(set(pattern.findall(sql)))

    def compile(
        self,
        parsed: ParsedPipeline,
        is_incremental: bool = False,
        watermarks: dict[str, Any] | None = None,
        run_started_at: datetime | None = None,
    ) -> str:
        """Compile a parsed pipeline to executable SQL.

        Args:
            parsed: ParsedPipeline from parse_file/parse_string
            is_incremental: Whether this is an incremental run
            watermarks: Dict of column -> last value for incremental
            run_started_at: Timestamp of run start

        Returns:
            Executable SQL string
        """
        if watermarks is None:
            watermarks = {}
        if run_started_at is None:
            run_started_at = datetime.utcnow()

        # Create template context
        context = {
            "ref": self._make_ref_function(),
            "is_incremental": lambda: is_incremental and parsed.is_incremental,
            "watermark": self._make_watermark_function(watermarks),
            "this": self._resolve_table(parsed.name),
            "run_started_at": run_started_at.isoformat(),
        }

        # Render template
        try:
            template = self._env.from_string(parsed.raw_sql)
            sql = template.render(**context)
        except TemplateSyntaxError as e:
            raise ValueError(f"Template syntax error in {parsed.name}: {e}") from e

        # Clean up SQL (remove metadata comments, extra whitespace)
        sql = self._clean_sql(sql)

        return sql

    def _make_ref_function(self) -> Callable[[str], str]:
        """Create the ref() function for templates."""

        def ref(table: str) -> str:
            """Reference another table.

            Converts logical table name to S3 path for DuckDB.
            """
            return self._resolve_table(table)

        return ref

    def _make_watermark_function(
        self, watermarks: dict[str, Any]
    ) -> Callable[[str], str]:
        """Create the watermark() function for templates."""

        def watermark(column: str) -> str:
            """Get the last processed value for a column.

            Used in incremental pipelines to filter for new data.
            """
            value = watermarks.get(column)
            if value is None:
                # Default to epoch for first run
                return "1970-01-01 00:00:00"
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        return watermark

    def _resolve_table(self, table: str) -> str:
        """Resolve a logical table name to a DuckDB-readable path.

        For now, converts to S3 parquet glob pattern.
        With Nessie/Iceberg, this would resolve to catalog reference.
        """
        # Split into namespace.table if present
        if "." in table:
            layer, name = table.split(".", 1)
        else:
            layer = "bronze"
            name = table

        if self.workspace:
            return f"'{self.workspace.s3_path(layer, name)}*.parquet'"
        else:
            # Default path without workspace
            warehouse = "s3://warehouse"
            return f"'{warehouse}/{layer}/{name}/*.parquet'"

    def _clean_sql(self, sql: str) -> str:
        """Clean up compiled SQL."""
        # Remove metadata comments
        sql = self.METADATA_PATTERN.sub("", sql)

        # Remove empty lines at start
        lines = sql.split("\n")
        while lines and not lines[0].strip():
            lines.pop(0)

        # Remove excessive blank lines
        cleaned = []
        prev_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            cleaned.append(line)
            prev_blank = is_blank

        return "\n".join(cleaned).strip()
