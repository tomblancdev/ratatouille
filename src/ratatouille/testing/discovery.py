"""Discover tests in pipeline folders.

Pipeline folder structure:
```
pipelines/
└── silver/
    └── sales/
        ├── pipeline.sql
        ├── config.yaml
        ├── tests/
        │   ├── mocks/
        │   │   └── bronze_sales.yaml
        │   ├── quality/
        │   │   └── unique_txn.sql
        │   └── unit/
        │       └── test_transform.sql
        └── docs/
            └── README.md
```
"""

import re
from collections.abc import Iterator
from pathlib import Path

import yaml

from .models import (
    DiscoveredPipeline,
    DiscoveredTest,
    ExpectedResult,
    TestConfig,
    TestSeverity,
)


def discover_pipelines(workspace_path: Path) -> list[DiscoveredPipeline]:
    """Discover all pipelines in a workspace.

    Supports both new folder structure (pipeline.sql in folder) and
    legacy flat structure (sales.sql directly in layer folder).

    Folder structure takes precedence - if a folder exists, the legacy
    file is ignored.
    """
    pipelines_path = workspace_path / "pipelines"
    if not pipelines_path.exists():
        return []

    discovered = []
    discovered_names: set[tuple[str, str]] = set()  # (layer, name)

    for layer in ["bronze", "silver", "gold"]:
        layer_path = pipelines_path / layer
        if not layer_path.exists():
            continue

        # First pass: folder-based pipelines (preferred)
        for item in layer_path.iterdir():
            if item.is_dir():
                pipeline = _discover_pipeline_folder(item, layer)
                if pipeline:
                    discovered.append(pipeline)
                    discovered_names.add((layer, pipeline.name))

        # Second pass: legacy flat files (only if folder doesn't exist)
        for item in layer_path.iterdir():
            if item.is_file() and item.suffix in (".sql", ".py"):
                name = item.stem
                # Skip if folder version already discovered
                if (layer, name) in discovered_names:
                    continue

                pipeline = _discover_legacy_pipeline(item, layer)
                if pipeline:
                    discovered.append(pipeline)
                    discovered_names.add((layer, name))

    return discovered


def _discover_pipeline_folder(folder: Path, layer: str) -> DiscoveredPipeline | None:
    """Discover a pipeline from a folder structure."""
    name = folder.name

    # Look for pipeline file
    pipeline_sql = folder / "pipeline.sql"
    pipeline_py = folder / "pipeline.py"

    pipeline_file = None
    if pipeline_sql.exists():
        pipeline_file = pipeline_sql
    elif pipeline_py.exists():
        pipeline_file = pipeline_py

    if not pipeline_file:
        return None

    # Look for config
    config_file = folder / "config.yaml"
    if not config_file.exists():
        config_file = None

    # Look for tests
    tests_path = folder / "tests"
    mocks_path = tests_path / "mocks" if tests_path.exists() else None
    quality_path = tests_path / "quality" if tests_path.exists() else None
    unit_path = tests_path / "unit" if tests_path.exists() else None

    # Discover quality tests
    quality_tests = []
    if quality_path and quality_path.exists():
        for sql_file in quality_path.glob("*.sql"):
            test = _parse_sql_test(sql_file, "quality")
            if test:
                quality_tests.append(test)

    # Discover unit tests
    unit_tests = []
    if unit_path and unit_path.exists():
        for test_file in unit_path.iterdir():
            if test_file.suffix == ".sql":
                test = _parse_sql_test(test_file, "unit_sql")
                if test:
                    unit_tests.append(test)
            elif test_file.suffix == ".py" and test_file.name.startswith("test_"):
                test = _parse_python_test(test_file)
                if test:
                    unit_tests.append(test)

    # Look for docs
    docs_path = folder / "docs"
    readme_file = folder / "README.md"
    if not readme_file.exists():
        readme_file = None

    return DiscoveredPipeline(
        name=name,
        layer=layer,
        path=folder,
        pipeline_file=pipeline_file,
        config_file=config_file,
        tests_path=tests_path if tests_path.exists() else None,
        mocks_path=mocks_path if mocks_path and mocks_path.exists() else None,
        quality_tests=quality_tests,
        unit_tests=unit_tests,
        docs_path=docs_path if docs_path.exists() else None,
        readme_file=readme_file,
    )


def _discover_legacy_pipeline(file: Path, layer: str) -> DiscoveredPipeline | None:
    """Discover a pipeline from legacy flat file structure."""
    name = file.stem

    # Check for matching folder with tests
    folder = file.parent / name
    tests_path = folder / "tests" if folder.exists() else None

    # Look for config
    config_file = file.with_suffix(".yaml")
    if not config_file.exists():
        config_file = None

    # Discover tests if folder exists
    quality_tests = []
    unit_tests = []

    if tests_path and tests_path.exists():
        quality_path = tests_path / "quality"
        if quality_path.exists():
            for sql_file in quality_path.glob("*.sql"):
                test = _parse_sql_test(sql_file, "quality")
                if test:
                    quality_tests.append(test)

        unit_path = tests_path / "unit"
        if unit_path.exists():
            for test_file in unit_path.iterdir():
                if test_file.suffix == ".sql":
                    test = _parse_sql_test(test_file, "unit_sql")
                    if test:
                        unit_tests.append(test)
                elif test_file.suffix == ".py" and test_file.name.startswith("test_"):
                    test = _parse_python_test(test_file)
                    if test:
                        unit_tests.append(test)

    return DiscoveredPipeline(
        name=name,
        layer=layer,
        path=file.parent,
        pipeline_file=file,
        config_file=config_file,
        tests_path=tests_path,
        mocks_path=tests_path / "mocks" if tests_path else None,
        quality_tests=quality_tests,
        unit_tests=unit_tests,
        docs_path=folder / "docs"
        if folder.exists() and (folder / "docs").exists()
        else None,
        readme_file=None,
    )


def _parse_sql_test(file: Path, test_type: str) -> DiscoveredTest | None:
    """Parse a SQL test file to extract config and content.

    SQL test files use comment metadata:
    ```sql
    -- @name: unique_transaction_ids
    -- @description: Transaction IDs must be unique
    -- @severity: error
    -- @mocks: mocks/bronze_sales.yaml
    -- @expect_count: 0

    SELECT ...
    ```
    """
    content = file.read_text()

    # Extract metadata from comments
    metadata: dict[str, str | list[str]] = {}

    for match in re.finditer(r"^--\s*@(\w+):\s*(.+)$", content, re.MULTILINE):
        key = match.group(1)
        value = match.group(2).strip()

        # Handle list values (mocks, expect)
        if key in ("mocks",) and value.startswith("["):
            # Parse YAML list inline
            metadata[key] = yaml.safe_load(value)
        elif key == "mocks" and "," in value:
            metadata[key] = [v.strip() for v in value.split(",")]
        elif key == "mocks":
            metadata.setdefault("mocks", []).append(value)  # type: ignore
        else:
            metadata[key] = value

    # Build test config
    name = metadata.get("name", file.stem)
    if isinstance(name, list):
        name = name[0]

    description = metadata.get("description", "")
    if isinstance(description, list):
        description = description[0]

    severity_str = metadata.get("severity", "error")
    if isinstance(severity_str, list):
        severity_str = severity_str[0]
    severity = TestSeverity.WARN if severity_str == "warn" else TestSeverity.ERROR

    # Parse mocks
    mocks = metadata.get("mocks", [])
    if isinstance(mocks, str):
        mocks = [mocks]

    # Parse mode
    mode_str = metadata.get("mode", "full_refresh")
    if isinstance(mode_str, list):
        mode_str = mode_str[0]
    mode = "incremental" if mode_str == "incremental" else "full_refresh"

    # Parse watermarks (YAML format in comments)
    watermarks = {}
    watermarks_str = metadata.get("watermarks")
    if watermarks_str:
        if isinstance(watermarks_str, str):
            try:
                watermarks = yaml.safe_load(watermarks_str)
            except yaml.YAMLError:
                pass

    # Parse expected result
    expect = None
    expect_count = metadata.get("expect_count")
    expect_rows = metadata.get("expect")
    expect_columns = metadata.get("expect_columns")

    if expect_count or expect_rows or expect_columns:
        row_count = None
        if expect_count:
            try:
                row_count = (
                    int(expect_count) if isinstance(expect_count, str) else expect_count
                )
            except (ValueError, TypeError):
                pass

        rows = None
        if expect_rows:
            if isinstance(expect_rows, str):
                try:
                    parsed = yaml.safe_load(expect_rows)
                    if isinstance(parsed, list):
                        rows = parsed
                except yaml.YAMLError:
                    pass
            elif isinstance(expect_rows, list):
                rows = expect_rows

        columns = None
        if expect_columns:
            if isinstance(expect_columns, str):
                try:
                    parsed = yaml.safe_load(expect_columns)
                    if isinstance(parsed, list):
                        columns = parsed
                except yaml.YAMLError:
                    pass
            elif isinstance(expect_columns, list):
                columns = expect_columns

        expect = ExpectedResult(
            rows=rows,
            columns=columns,
            row_count=row_count,
        )

    config = TestConfig(
        name=name,  # type: ignore
        description=description,  # type: ignore
        severity=severity,
        mocks=mocks,  # type: ignore
        mode=mode,  # type: ignore
        watermarks=watermarks,
        expect=expect,
    )

    # Extract SQL (remove metadata comments)
    sql = re.sub(r"^--\s*@\w+:.*$", "", content, flags=re.MULTILINE)
    sql = sql.strip()

    return DiscoveredTest(
        path=file,
        test_type=test_type,  # type: ignore
        config=config,
        sql=sql,
    )


def _parse_python_test(file: Path) -> DiscoveredTest | None:
    """Parse a Python test file to extract basic metadata.

    Python test files can have metadata in comments:
    ```python
    # @name: test_sales_ingestion
    # @description: Test POS data ingestion logic
    # @mocks: mocks/api_emulator.py
    ```
    """
    content = file.read_text()

    # Extract metadata from comments
    metadata: dict[str, str | list[str]] = {}

    for match in re.finditer(r"^#\s*@(\w+):\s*(.+)$", content, re.MULTILINE):
        key = match.group(1)
        value = match.group(2).strip()
        metadata[key] = value

    name = metadata.get("name", file.stem)
    if isinstance(name, list):
        name = name[0]

    description = metadata.get("description", "")
    if isinstance(description, list):
        description = description[0]

    mocks = metadata.get("mocks", [])
    if isinstance(mocks, str):
        mocks = [mocks]

    config = TestConfig(
        name=name,  # type: ignore
        description=description,  # type: ignore
        mocks=mocks,  # type: ignore
    )

    return DiscoveredTest(
        path=file,
        test_type="unit_python",
        config=config,
        module_path=str(file),
    )


def discover_workspace_tests(
    workspace_path: Path,
) -> Iterator[tuple[DiscoveredPipeline, list[DiscoveredTest]]]:
    """Discover all tests across a workspace.

    Yields:
        Tuples of (pipeline, tests) for each pipeline with tests
    """
    pipelines = discover_pipelines(workspace_path)

    for pipeline in pipelines:
        all_tests = pipeline.quality_tests + pipeline.unit_tests
        if all_tests:
            yield pipeline, all_tests
