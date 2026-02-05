"""🔍 SQL Rules Parser - Extract business rules from SQL WHERE clauses.

Parses SQL files to identify:
- WHERE clause conditions as implicit business rules
- Comments describing business logic
- Filtering conditions that represent data quality rules

Example:
    sql = '''
    SELECT * FROM sales
    WHERE quantity > 0           -- Filter invalid quantities
      AND unit_price > 0         -- Must have positive price
      AND txn_id IS NOT NULL     -- Require transaction ID
    '''

    rules = extract_business_rules(sql)
    # Returns:
    # [
    #   BusinessRule(name="positive_quantity", description="Quantity must be positive", sql="quantity > 0"),
    #   BusinessRule(name="positive_price", description="Unit price must be positive", sql="unit_price > 0"),
    #   BusinessRule(name="required_txn_id", description="Transaction ID is required", sql="txn_id IS NOT NULL"),
    # ]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..models import BusinessRule


@dataclass
class WhereCondition:
    """A parsed WHERE clause condition."""

    expression: str
    comment: str | None = None
    column: str | None = None
    operator: str | None = None


class SQLRulesParser:
    """Parse SQL files to extract business rules from WHERE clauses.

    Business rules are identified from:
    1. WHERE clause conditions (e.g., quantity > 0)
    2. Inline comments explaining conditions
    3. HAVING clause conditions
    """

    # Pattern to match WHERE/AND/OR conditions with optional inline comments
    CONDITION_PATTERN = re.compile(
        r"(?:WHERE|AND|OR)\s+"
        r"(?P<condition>[^-\n]+?)"  # The condition itself
        r"(?:\s*--\s*(?P<comment>.+?))?$",  # Optional inline comment
        re.IGNORECASE | re.MULTILINE,
    )

    # Pattern to extract column name from condition
    COLUMN_PATTERN = re.compile(
        r"^(?P<column>\w+)\s*"
        r"(?P<operator>IS\s+NOT\s+NULL|IS\s+NULL|>|<|>=|<=|=|!=|<>|IN|NOT\s+IN|LIKE|BETWEEN)",
        re.IGNORECASE,
    )

    # Operators and their human-readable descriptions
    OPERATOR_DESCRIPTIONS = {
        ">": "must be greater than",
        "<": "must be less than",
        ">=": "must be at least",
        "<=": "must be at most",
        "=": "must equal",
        "!=": "must not equal",
        "<>": "must not equal",
        "IS NOT NULL": "is required",
        "IS NULL": "must be null",
        "IN": "must be one of",
        "NOT IN": "must not be one of",
        "LIKE": "must match pattern",
        "BETWEEN": "must be between",
    }

    def __init__(self) -> None:
        self._rules: list[BusinessRule] = []

    def parse_file(self, path: Path | str) -> list[BusinessRule]:
        """Parse a SQL file and extract business rules.

        Args:
            path: Path to the SQL file

        Returns:
            List of BusinessRule objects
        """
        with open(path) as f:
            sql = f.read()
        return self.parse_string(sql)

    def parse_string(self, sql: str) -> list[BusinessRule]:
        """Parse SQL string and extract business rules.

        Args:
            sql: SQL content

        Returns:
            List of BusinessRule objects
        """
        self._rules = []
        conditions = self._extract_conditions(sql)

        for condition in conditions:
            rule = self._condition_to_rule(condition)
            if rule:
                self._rules.append(rule)

        return self._rules

    def _extract_conditions(self, sql: str) -> list[WhereCondition]:
        """Extract WHERE clause conditions from SQL."""
        conditions = []

        for match in self.CONDITION_PATTERN.finditer(sql):
            raw_condition = match.group("condition").strip()
            comment = match.group("comment")

            # Skip Jinja conditionals and template blocks
            if "{%" in raw_condition or "{{" in raw_condition:
                continue

            # Clean up the condition (remove trailing clauses)
            condition = self._clean_condition(raw_condition)
            if not condition:
                continue

            # Extract column and operator
            column_match = self.COLUMN_PATTERN.match(condition)
            column = column_match.group("column") if column_match else None
            operator = column_match.group("operator").upper() if column_match else None

            conditions.append(
                WhereCondition(
                    expression=condition,
                    comment=comment.strip() if comment else None,
                    column=column,
                    operator=operator,
                )
            )

        return conditions

    def _clean_condition(self, condition: str) -> str:
        """Clean a condition by removing trailing clauses."""
        # Remove trailing keywords that start new clauses
        condition = re.sub(
            r"\s+(GROUP|ORDER|LIMIT|HAVING|UNION|EXCEPT|INTERSECT)\s.*$",
            "",
            condition,
            flags=re.IGNORECASE,
        )
        return condition.strip()

    def _condition_to_rule(self, condition: WhereCondition) -> BusinessRule | None:
        """Convert a WHERE condition to a BusinessRule."""
        if not condition.column:
            return None

        # Generate rule name from column
        rule_name = self._generate_rule_name(condition)

        # Generate description from comment or condition
        description = self._generate_description(condition)

        return BusinessRule(
            name=rule_name,
            description=description,
            sql=condition.expression,
            source="sql",
        )

    def _generate_rule_name(self, condition: WhereCondition) -> str:
        """Generate a snake_case rule name from condition."""
        column = condition.column.lower()
        operator = (condition.operator or "").lower().replace(" ", "_")

        if "not_null" in operator:
            return f"required_{column}"
        elif operator in (">", ">="):
            return f"positive_{column}"
        elif operator in ("<", "<="):
            return f"max_{column}"
        elif operator == "in":
            return f"valid_{column}"
        elif operator == "not_in":
            return f"excluded_{column}"
        else:
            return f"check_{column}"

    def _generate_description(self, condition: WhereCondition) -> str:
        """Generate human-readable description for a condition."""
        # Use inline comment if available
        if condition.comment:
            return condition.comment

        # Generate from condition structure
        column = condition.column or "Value"
        operator = condition.operator or ""

        desc = self.OPERATOR_DESCRIPTIONS.get(operator, "must satisfy condition")

        # Make it human readable
        column_display = column.replace("_", " ").title()
        return f"{column_display} {desc}"


def extract_business_rules(sql: str | Path) -> list[BusinessRule]:
    """Convenience function to extract business rules from SQL.

    Args:
        sql: SQL string or path to SQL file

    Returns:
        List of BusinessRule objects
    """
    parser = SQLRulesParser()

    if isinstance(sql, Path) or (isinstance(sql, str) and Path(sql).exists()):
        return parser.parse_file(sql)
    return parser.parse_string(sql)
