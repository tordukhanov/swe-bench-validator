"""
Validator functionality for SWE-bench data points.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import docker
from swebench.harness.docker_build import build_env_images, build_instance_images
from swebench.harness.run_evaluation import run_instances


@dataclass
class ValidationResult:
    """Result of validating a data point"""

    instance_id: str
    passed: bool
    message: str
    details: dict | None = None


class SWEBenchValidator:
    def __init__(self, timeout: int = 900, verbose: bool = False):
        self.timeout = timeout
        self.verbose = verbose
        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger("swe_bench_validator")
        level = logging.DEBUG if self.verbose else logging.INFO
        logger.setLevel(level)
        return logger

    def load_datapoint(self, json_path: Path) -> dict:
        """
        Load and validate JSON structure

        Raises:
            ValueError: If JSON is malformed or missing required fields
        """
        required_fields = [
            "instance_id",
            "repo",
            "base_commit",
            "patch",
            "FAIL_TO_PASS",
            "PASS_TO_PASS",
        ]

        with open(json_path) as f:
            data = json.load(f)

        # Validate structure
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        return data

    def create_prediction(self, datapoint: dict) -> dict:
        """
        Convert data point to SWE-bench prediction format

        The prediction format is what run_evaluation expects:
        {
            "instance_id": "...",
            "model_patch": "...",  # Use the golden patch
            "model_name_or_path": "validator"
        }
        """
        return {
            "instance_id": datapoint["instance_id"],
            "model_patch": datapoint["patch"],
            "model_name_or_path": "golden-validator",
        }

    def build_docker_images(self, datapoint: dict, force_rebuild: bool = False):
        """
        Build required Docker images for evaluation

        Args:
            datapoint: The data point to build images for
            force_rebuild: Whether to force rebuild even if images exist
        """
        self.logger.info(
            "Building Docker images (this may take a while on first run)..."
        )

        # Get Docker client
        client = docker.from_env()

        # Build environment image first (repo-level dependencies)
        self.logger.info(f"Building environment image for {datapoint['repo']}...")
        build_env_images(
            client=client,
            dataset=[datapoint],
            force_rebuild=force_rebuild,
            max_workers=1,
        )

        # Build instance image (specific commit + patches)
        self.logger.info(f"Building instance image for {datapoint['instance_id']}...")
        build_instance_images(
            client=client,
            dataset=[datapoint],
            force_rebuild=force_rebuild,
            max_workers=1,
            namespace="swebench",
            tag="latest",
        )

        self.logger.info("Docker images built successfully")

    def run_swebench_evaluation(
        self,
        datapoint: dict,
        prediction: dict,
        timeout: int = 900,  # 15 minutes default
    ) -> dict:
        """
        Run SWE-bench evaluation in Docker

        Returns:
            Evaluation results from run_instances
        """
        # Build Docker images first
        self.build_docker_images(datapoint, force_rebuild=False)

        # Create instances list (SWE-bench format)
        instances = [datapoint]

        # Create predictions dict: {instance_id: prediction}
        predictions = {datapoint["instance_id"]: prediction}

        # Generate unique run ID
        run_id = f"validate_{datapoint['instance_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run evaluation using SWE-bench harness
        run_instances(
            predictions=predictions,
            instances=instances,
            cache_level="env",  # Cache at environment level for speed
            clean=False,  # Don't clean images
            force_rebuild=False,  # Use cached images if available
            max_workers=1,
            run_id=run_id,
            timeout=timeout,
            namespace="swebench",
            instance_image_tag="latest",
            rewrite_reports=False,
        )

        # Read the report from disk (run_instances writes to logs/)
        report_path = (
            Path("logs")
            / "run_evaluation"
            / run_id
            / prediction["model_name_or_path"]
            / datapoint["instance_id"]
            / "report.json"
        )

        if not report_path.exists():
            raise RuntimeError(f"Evaluation report not found at {report_path}")

        with open(report_path) as f:
            full_report = json.load(f)

        # Extract the report for this instance
        if datapoint["instance_id"] not in full_report:
            raise RuntimeError(
                f"Instance {datapoint['instance_id']} not found in report"
            )

        return full_report[datapoint["instance_id"]]

    def validate_test_results(
        self, datapoint: dict, eval_result: dict
    ) -> ValidationResult:
        """
        Check that all required tests pass

        Validates:
        - All FAIL_TO_PASS tests now pass
        - All PASS_TO_PASS tests still pass
        """
        # Extract test results from eval_result
        # SWE-bench format: eval_result["tests_status"]["FAIL_TO_PASS"]["success"/"failure"]
        tests_status = eval_result.get("tests_status", {})

        failed_tests = []

        # Check FAIL_TO_PASS tests - all should be in success list
        fail_to_pass_status = tests_status.get("FAIL_TO_PASS", {})
        fail_to_pass_failures = fail_to_pass_status.get("failure", [])

        for test in fail_to_pass_failures:
            failed_tests.append(f"FAIL_TO_PASS test failed: {test}")

        # Check PASS_TO_PASS tests - all should be in success list
        pass_to_pass_status = tests_status.get("PASS_TO_PASS", {})
        pass_to_pass_failures = pass_to_pass_status.get("failure", [])

        for test in pass_to_pass_failures:
            failed_tests.append(f"PASS_TO_PASS test failed: {test}")

        # Check if patch was applied successfully
        if not eval_result.get("patch_successfully_applied", False):
            failed_tests.append("Patch failed to apply")

        # Check if tests resolved the issue
        if not eval_result.get("resolved", False):
            failed_tests.append(
                "Issue not resolved (not all FAIL_TO_PASS tests passed)"
            )

        if failed_tests:
            return ValidationResult(
                instance_id=datapoint["instance_id"],
                passed=False,
                message=f"Test failures: {len(failed_tests)} test(s) failed",
                details={"failed_tests": failed_tests},
            )

        return ValidationResult(
            instance_id=datapoint["instance_id"],
            passed=True,
            message="All tests passed",
        )

    def validate(self, datapoint_path: Path) -> ValidationResult:
        """
        Main validation entry point

        Args:
            datapoint_path: Path to JSON data point file

        Returns:
            ValidationResult with pass/fail status
        """
        try:
            # 1. Load data point
            self.logger.info(f"Loading data point: {datapoint_path}")
            datapoint = self.load_datapoint(datapoint_path)

            # 2. Create prediction
            self.logger.info(f"Creating prediction for {datapoint['instance_id']}")
            prediction = self.create_prediction(datapoint)

            # 3. Run evaluation
            self.logger.info("Running SWE-bench evaluation in Docker...")
            eval_result = self.run_swebench_evaluation(
                datapoint, prediction, self.timeout
            )

            # 4. Validate results
            self.logger.info("Validating test results...")
            result = self.validate_test_results(datapoint, eval_result)

            return result

        except Exception as e:
            return ValidationResult(
                instance_id=datapoint.get("instance_id", "unknown"),
                passed=False,
                message=f"Validation error: {str(e)}",
                details={"error_type": type(e).__name__},
            )
