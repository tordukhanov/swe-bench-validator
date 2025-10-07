# SWE-bench Data Points

This directory contains SWE-bench data points used for testing and validation.

## Test Data Points

### Valid Data Points (Expected to Pass ✅)

#### `astropy__astropy-11693.json`
- **Repository**: astropy/astropy
- **Issue**: WCS.all_world2pix failed to converge when plotting WCS with non-linear distortions
- **Fix**: Modified `world_to_pixel_values()` to catch `NoConvergence` exception and emit a warning instead of raising an error
- **Tests**:
  - FAIL_TO_PASS: `test_non_convergence_warning` - New test that validates the warning behavior
  - PASS_TO_PASS: 26 existing tests that must continue to pass
- **Expected Result**: ✅ All tests pass after applying the golden patch

### Invalid Data Points (Expected to Fail ❌)

#### `astropy__astropy-11693-fail.json`
- **Repository**: astropy/astropy
- **Issue**: Same as above (astropy__astropy-11693)
- **Problem**: Contains an incomplete or incorrect patch that doesn't properly fix the issue
- **Expected Result**: ❌ Validation fails because FAIL_TO_PASS tests don't pass

## Additional Data Points

The repository contains 75+ additional astropy and django data points downloaded from the SWE-bench dataset for comprehensive testing.

### Astropy Data Points
- Various WCS (World Coordinate System) issues
- Table and units functionality fixes
- FITS file handling improvements

### Django Data Points
- ORM query fixes
- Form validation improvements
- Migration system enhancements

## Usage

### Validate a Single Data Point

```bash
uv run swe-bench-validate data_points/astropy__astropy-11693.json
```

### Validate All Data Points

```bash
./scripts/validate_all.sh
```

## Data Point Format

Each data point follows the SWE-bench format:

```json
{
  "instance_id": "repo__project-12345",
  "repo": "owner/repo",
  "base_commit": "git commit hash",
  "patch": "diff of the golden solution",
  "test_patch": "diff of test changes",
  "problem_statement": "GitHub issue description",
  "FAIL_TO_PASS": "[\"test1\", \"test2\"]",
  "PASS_TO_PASS": "[\"test3\", \"test4\"]",
  ...
}
```

## Validation Criteria

A data point passes validation if:
1. ✅ Patch applies cleanly to the repository at the specified commit
2. ✅ All FAIL_TO_PASS tests pass after applying the patch
3. ✅ All PASS_TO_PASS tests continue to pass after applying the patch
4. ✅ No Docker evaluation errors occur

## Adding New Data Points

1. Download data points using the downloader:
   ```bash
   scripts/download_swe_bench.sh --instance_id "repo__project-12345"
   ```

2. Place JSON files in `data_points/` directory

3. Create a PR - the validator will automatically run

4. Ensure validation passes before merging
