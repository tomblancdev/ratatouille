#!/bin/bash
# 🐀 Ratatouille Security Hook - Pre-Bash Validation
# Blocks commands that might access data or secrets

COMMAND="$1"

# Patterns that should be blocked
BLOCKED_PATTERNS=(
    # Data file access
    "cat.*\.parquet"
    "cat.*\.csv"
    "cat.*\.duckdb"
    "head.*\.parquet"
    "head.*\.csv"
    "tail.*\.parquet"
    "tail.*\.csv"
    "less.*\.parquet"
    "less.*\.csv"

    # Environment/secrets
    "cat.*\.env"
    "cat.*credentials"
    "cat.*secret"
    "echo.*\$.*KEY"
    "echo.*\$.*SECRET"
    "echo.*\$.*TOKEN"
    "echo.*\$.*PASSWORD"
    "printenv.*KEY"
    "printenv.*SECRET"

    # S3/MinIO data access
    "aws s3 cp"
    "aws s3 cat"
    "mc cat"
    "mc cp.*s3://"

    # DuckDB direct data access
    "duckdb.*SELECT.*FROM"
    "SELECT \* FROM"

    # Data directory access
    "cat.*/data/"
    "ls.*/data/"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern"; then
        echo "⛔ BLOCKED: Command matches restricted pattern: $pattern" >&2
        echo "This workspace restricts direct data access for security." >&2
        echo "Use SDK methods or ask user to run data queries manually." >&2
        exit 1
    fi
done

# Command is allowed
exit 0
