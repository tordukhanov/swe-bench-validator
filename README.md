# SWE-bench Data Point Validator

Infrastructure tools for validating SWE-bench data points using the official evaluation harness.

## Overview

This repository provides a validation system that ensures the quality and correctness of SWE-bench data points. It uses Docker-based evaluation to verify that golden patches correctly fix the issues they claim to address.

## Features

- ✅ **Automated Validation**: Validates data points using SWE-bench's official evaluation harness
- 🐳 **Docker-Based Testing**: Runs tests in isolated containers matching the exact environment
- 🚀 **GitHub Actions Integration**: Automatically validates changed data points in pull requests
- 📊 **Detailed Reporting**: Provides clear error messages and validation results
- ⚡ **Optimized Performance**: Only validates changed files, caches Docker images

## Prerequisites

- **Python 3.10+**
- **Docker**: Required for running SWE-bench evaluations
- **uv**: Fast Python package manager ([installation guide](https://github.com/astral-sh/uv))

## Installation

### Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install dependencies

```bash
uv sync
```

This will:
- Create a virtual environment
- Install all dependencies including SWE-bench
- Set up the `swe-bench-validate` CLI command

## Usage

### Validate a Single Data Point

```bash
uv run swe-bench-validate data_points/astropy__astropy-11693.json
```

With verbose output:

```bash
uv run swe-bench-validate data_points/astropy__astropy-11693.json --verbose
```

With custom timeout (in seconds):

```bash
uv run swe-bench-validate data_points/astropy__astropy-11693.json --timeout 1800
```

### Validate All Data Points

```bash
./scripts/validate_all.sh
```

### Validate Only Changed Files

```bash
# Compare against main branch
./scripts/validate_changed.sh

# Compare against specific branch
./scripts/validate_changed.sh develop
```

## GitHub Actions Integration

The repository includes a GitHub Action that automatically validates data points in pull requests.

### Workflow: `.github/workflows/validate-datapoints.yml`

**Triggers:**
- Pushes to `data_points/**/*.json`
- Pull requests modifying `data_points/**/*.json`

**What it does:**
1. Detects changed data point files
2. Validates each changed file using the SWE-bench harness
3. Reports results as status checks
4. Uploads validation logs as artifacts
5. Comments on PR if validation fails

**Example PR checks:**
- ✅ Green check: All FAIL_TO_PASS and PASS_TO_PASS tests pass
- ❌ Red check: Some tests fail or patch doesn't apply

## Data Point Format

Each data point is a JSON file in the `data_points/` directory containing:

```json
{
  "instance_id": "repo__project-12345",
  "repo": "owner/repo",
  "base_commit": "abc123...",
  "patch": "diff --git ...",
  "FAIL_TO_PASS": "[\"test1\", \"test2\"]",
  "PASS_TO_PASS": "[\"test3\", \"test4\"]",
  ...
}
```

### Validation Criteria

A data point is valid if:

1. **Patch applies cleanly** to the repository at the specified commit
2. **All FAIL_TO_PASS tests pass** after applying the patch
3. **All PASS_TO_PASS tests still pass** after applying the patch
4. **No Docker evaluation errors** occur

## Examples

### Valid Data Point

```bash
$ uv run swe-bench-validate data_points/astropy__astropy-11693.json

╭─────────────────────────────────────────╮
│ SWE-bench Data Point Validator          │
│ Data point: astropy__astropy-11693.json │
╰─────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field                ┃ Value                 ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ Instance ID          │ astropy__astropy-11693│
│ Status               │ ✓ PASSED              │
│ Message              │ All tests passed      │
└──────────────────────┴───────────────────────┘
```

### Invalid Data Point

```bash
$ uv run swe-bench-validate data_points/astropy__astropy-11693-fail.json

╭──────────────────────────────────────────────╮
│ SWE-bench Data Point Validator               │
│ Data point: astropy__astropy-11693-fail.json │
╰──────────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field                ┃ Value                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Instance ID          │ astropy__astropy-11693           │
│ Status               │ ✗ FAILED                         │
│ Message              │ Test failures: 1 test(s) failed  │
└──────────────────────┴──────────────────────────────────┘

Error Details:

Failed Tests:
  • FAIL_TO_PASS test failed: astropy/wcs/wcsapi/tests/test_fitswcs.py::test_non_convergence_warning
```

## Architecture

### Validator Components

1. **[swe_bench_validator/validator.py](swe_bench_validator/validator.py)**: Core validation logic
2. **[swe_bench_validator/cli.py](swe_bench_validator/cli.py)**: Command-line interface
3. **[.github/workflows/validate-datapoints.yml](.github/workflows/validate-datapoints.yml)**: GitHub Actions workflow

### Docker Image Layers

SWE-bench uses a 3-layer Docker architecture:

1. **Base Image**: Python environment
2. **Environment Image**: Repository + dependencies (cached per repo)
3. **Instance Image**: Specific commit + test setup (cached per data point)

Images are automatically built and cached for faster subsequent validations.

### Validation Flow

```
Load Data Point
      ↓
Build Docker Images (if needed)
      ↓
Apply Golden Patch
      ↓
Run Tests in Container
      ↓
Validate Results
      ↓
Report Pass/Fail
```

## Performance Notes

### First Run

The first validation of a repository takes **10-30 minutes** because it:
- Builds Docker images from scratch
- Clones the repository
- Installs all dependencies

### Subsequent Runs

Subsequent validations of the same repository are **much faster** (2-5 minutes) because:
- Docker images are cached
- Only instance-specific setup is needed

### CI/CD Optimization

The GitHub Action only validates **changed files**, making PR checks fast even with large datasets.

## Troubleshooting

### Docker Permission Errors

If you see Docker permission errors:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Docker Image Build Failures

Check the logs in `logs/run_evaluation/` for detailed error messages.

### Timeout Errors

Increase the timeout for slow tests:

```bash
uv run swe-bench-validate data_points/slow-test.json --timeout 3600
```

## Development

### Project Structure

```
.
├── swe_bench_validator/      # Validator implementation
│   ├── validator.py          # Core validation logic
│   ├── cli.py                # CLI interface
│   └── utils.py              # Helper utilities
├── swe_bench_downloader/     # Data point downloader (existing)
├── data_points/              # SWE-bench data points
├── scripts/                  # Helper scripts
│   ├── validate_all.sh       # Validate all data points
│   └── validate_changed.sh   # Validate changed files only
├── .github/workflows/        # GitHub Actions
│   └── validate-datapoints.yml
└── pyproject.toml            # Project configuration
```

### Running Tests

```bash
# Test with a known-good data point
uv run swe-bench-validate data_points/astropy__astropy-11693.json -v

# Test with a known-bad data point
uv run swe-bench-validate data_points/astropy__astropy-11693-fail.json -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add or modify data points
4. The validator will automatically run on your PR
5. Ensure all validations pass before requesting review

## License

See [LICENSE](LICENSE) file for details.

## Resources

- [SWE-bench Repository](https://github.com/princeton-nlp/SWE-bench)
- [SWE-bench Evaluation Guide](https://www.swebench.com/SWE-bench/guides/evaluation/)
- [Docker Documentation](https://docs.docker.com/)
