#!/bin/bash
# Validate only changed data points (compared to main branch)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "SWE-bench Changed Files Validator"
echo "========================================"
echo ""

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Get the base branch (default to main)
BASE_BRANCH="${1:-main}"

# Check if base branch exists
if ! git rev-parse --verify "$BASE_BRANCH" > /dev/null 2>&1; then
    echo "⚠️  Warning: Branch '$BASE_BRANCH' not found, using current HEAD"
    BASE_BRANCH="HEAD"
fi

echo "Comparing against: $BASE_BRANCH"
echo ""

# Get changed JSON files in data_points directory
changed_files=$(git diff --name-only "$BASE_BRANCH" -- 'data_points/*.json' 2>/dev/null || true)

if [ -z "$changed_files" ]; then
    echo "ℹ️  No changed data point files found"
    echo "✅ Nothing to validate"
    exit 0
fi

# Count changed files
file_count=$(echo "$changed_files" | wc -l | tr -d ' ')
echo "Found $file_count changed data point(s):"
echo "$changed_files" | sed 's/^/  - /'
echo ""

# Validate each changed file
success_count=0
fail_count=0
failed_files=()

while IFS= read -r file; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        filename=$(basename "$file")
        echo "----------------------------------------"
        echo "Validating: $filename"
        echo "----------------------------------------"

        if uv run swe-bench-validate "$PROJECT_DIR/$file" --timeout 1800; then
            echo "✓ PASSED: $filename"
            success_count=$((success_count + 1))
        else
            echo "✗ FAILED: $filename"
            failed_files+=("$filename")
            fail_count=$((fail_count + 1))
        fi
        echo ""
    else
        echo "⚠️  File deleted or not found: $file"
        echo ""
    fi
done <<< "$changed_files"

# Print summary
echo "========================================"
echo "Validation Summary"
echo "========================================"
echo "Total validated: $file_count"
echo "Passed: $success_count"
echo "Failed: $fail_count"

if [ $fail_count -gt 0 ]; then
    echo ""
    echo "❌ Failed files:"
    for file in "${failed_files[@]}"; do
        echo "  - $file"
    done
    exit 1
else
    echo ""
    echo "✅ All validations passed!"
fi
