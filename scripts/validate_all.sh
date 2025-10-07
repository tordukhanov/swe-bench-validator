#!/bin/bash
# Validate all data points in the data_points directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_DIR/data_points"

echo "========================================"
echo "SWE-bench Data Point Validator"
echo "========================================"
echo ""

# Check if data_points directory exists
if [ ! -d "$DATA_DIR" ]; then
    echo "❌ Error: data_points directory not found at $DATA_DIR"
    exit 1
fi

# Count total files
total_files=$(find "$DATA_DIR" -name "*.json" | wc -l | tr -d ' ')
echo "Found $total_files data point(s) to validate"
echo ""

# Validate each file
success_count=0
fail_count=0
failed_files=()

for file in "$DATA_DIR"/*.json; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        echo "----------------------------------------"
        echo "Validating: $filename"
        echo "----------------------------------------"

        if uv run swe-bench-validate "$file" --timeout 1800; then
            echo "✓ PASSED: $filename"
            success_count=$((success_count + 1))
        else
            echo "✗ FAILED: $filename"
            failed_files+=("$filename")
            fail_count=$((fail_count + 1))
        fi
        echo ""
    fi
done

# Print summary
echo "========================================"
echo "Validation Summary"
echo "========================================"
echo "Total validated: $total_files"
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
