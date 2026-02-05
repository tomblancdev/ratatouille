"""📋 Business Rules Template - Document data validation logic.

Generates business_rules.md with:
- Rules from config.yaml documentation section
- Rules extracted from SQL WHERE clauses
- Rules derived from column tests
- Custom data tests
"""

from __future__ import annotations

from datetime import datetime

from ..models import EnhancedPipelineConfig, BusinessRule


def generate_business_rules(
    config: EnhancedPipelineConfig,
    pipeline_name: str,
    layer: str,
    sql_rules: list[BusinessRule] | None = None,
) -> str:
    """Generate business_rules.md content for a pipeline.

    Args:
        config: Pipeline configuration
        pipeline_name: Name of the pipeline
        layer: Layer (bronze, silver, gold)
        sql_rules: Optional rules extracted from SQL

    Returns:
        Generated business_rules.md content
    """
    sections = []

    # Header
    display_name = pipeline_name.replace("_", " ").title()
    sections.append(f"# Business Rules: {display_name}")
    sections.append("")
    sections.append(f"> 🐀 Auto-generated | Layer: `{layer}` | Last updated: {datetime.now().strftime('%Y-%m-%d')}")
    sections.append("")

    # Collect all rules
    all_rules: list[tuple[str, BusinessRule]] = []

    # 1. Explicit rules from documentation section
    for rule in config.get_business_rules():
        all_rules.append(("documented", rule))

    # 2. Rules from SQL WHERE clauses
    if sql_rules:
        for rule in sql_rules:
            all_rules.append(("sql", rule))

    # 3. Rules implied by column tests
    test_rules = _extract_rules_from_tests(config)
    for rule in test_rules:
        all_rules.append(("test", rule))

    # 4. Custom data tests
    for test in config.tests:
        rule = BusinessRule(
            name=test.name,
            description=f"Custom test: {test.name}",
            sql=test.sql,
            source="test",
        )
        all_rules.append(("test", rule))

    if not all_rules:
        sections.append("*No business rules documented or detected.*")
        sections.append("")
        sections.append("To add rules, either:")
        sections.append("1. Add them to the `documentation.rules` section in config.yaml")
        sections.append("2. Add column tests (not_null, unique, positive, etc.)")
        sections.append("3. Add WHERE clauses to your SQL (they'll be extracted automatically)")
        return "\n".join(sections)

    # Summary
    sections.append("## Summary")
    sections.append("")
    sections.append(f"Total rules: **{len(all_rules)}**")
    sections.append("")

    # Count by source
    by_source = {}
    for source, _ in all_rules:
        by_source[source] = by_source.get(source, 0) + 1

    sections.append("| Source | Count |")
    sections.append("|--------|-------|")
    for source, count in sorted(by_source.items()):
        icon = _source_icon(source)
        sections.append(f"| {icon} {source.title()} | {count} |")
    sections.append("")

    # Documented rules (explicit in config)
    documented = [(s, r) for s, r in all_rules if s == "documented"]
    if documented:
        sections.append("## 📝 Documented Rules")
        sections.append("")
        sections.append("These rules are explicitly documented in config.yaml:")
        sections.append("")
        for _, rule in documented:
            sections.extend(_format_rule(rule))
        sections.append("")

    # SQL-derived rules
    sql_derived = [(s, r) for s, r in all_rules if s == "sql"]
    if sql_derived:
        sections.append("## 🔍 SQL Filter Rules")
        sections.append("")
        sections.append("These rules were extracted from SQL WHERE clauses:")
        sections.append("")
        for _, rule in sql_derived:
            sections.extend(_format_rule(rule))
        sections.append("")

    # Test-derived rules
    test_derived = [(s, r) for s, r in all_rules if s == "test"]
    if test_derived:
        sections.append("## ✅ Test-Based Rules")
        sections.append("")
        sections.append("These rules are enforced through column tests and custom data tests:")
        sections.append("")
        for _, rule in test_derived:
            sections.extend(_format_rule(rule))
        sections.append("")

    # Rule reference table
    sections.append("## Quick Reference")
    sections.append("")
    sections.append("| Rule | Source | SQL |")
    sections.append("|------|--------|-----|")
    for source, rule in all_rules:
        sql_snippet = f"`{rule.sql[:40]}...`" if rule.sql and len(rule.sql) > 40 else f"`{rule.sql}`" if rule.sql else "-"
        sections.append(f"| {rule.name} | {source} | {sql_snippet} |")
    sections.append("")

    return "\n".join(sections)


def _extract_rules_from_tests(config: EnhancedPipelineConfig) -> list[BusinessRule]:
    """Extract business rules implied by column tests."""
    rules = []

    for col in config.columns:
        for test in col.tests:
            rule = _test_to_rule(col.name, test)
            if rule:
                rules.append(rule)

    return rules


def _test_to_rule(column: str, test: str | dict) -> BusinessRule | None:
    """Convert a column test to a business rule."""
    if isinstance(test, str):
        if test == "not_null":
            return BusinessRule(
                name=f"required_{column}",
                description=f"{column} is required (cannot be NULL)",
                sql=f"{column} IS NOT NULL",
                source="test",
            )
        elif test == "unique":
            return BusinessRule(
                name=f"unique_{column}",
                description=f"{column} must be unique",
                sql=f"COUNT(DISTINCT {column}) = COUNT({column})",
                source="test",
            )
        elif test == "positive":
            return BusinessRule(
                name=f"positive_{column}",
                description=f"{column} must be greater than zero",
                sql=f"{column} > 0",
                source="test",
            )
    elif isinstance(test, dict):
        for key, value in test.items():
            if key == "accepted_values":
                values_str = ", ".join(f"'{v}'" for v in value)
                return BusinessRule(
                    name=f"valid_{column}",
                    description=f"{column} must be one of: {', '.join(str(v) for v in value)}",
                    sql=f"{column} IN ({values_str})",
                    source="test",
                )
            elif key == "min":
                return BusinessRule(
                    name=f"min_{column}",
                    description=f"{column} must be at least {value}",
                    sql=f"{column} >= {value}",
                    source="test",
                )
            elif key == "max":
                return BusinessRule(
                    name=f"max_{column}",
                    description=f"{column} must be at most {value}",
                    sql=f"{column} <= {value}",
                    source="test",
                )
    return None


def _format_rule(rule: BusinessRule) -> list[str]:
    """Format a single rule for display."""
    lines = []
    lines.append(f"### {rule.name}")
    lines.append("")
    lines.append(rule.description)
    if rule.sql:
        lines.append("")
        lines.append("```sql")
        lines.append(rule.sql)
        lines.append("```")
    lines.append("")
    return lines


def _source_icon(source: str) -> str:
    """Get icon for rule source."""
    icons = {
        "documented": "📝",
        "sql": "🔍",
        "test": "✅",
        "config": "⚙️",
    }
    return icons.get(source, "•")
