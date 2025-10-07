"""
Validator functionality for SWE-bench data points.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from swebench.harness.run_evaluation import run_instances
from swebench.harness.docker_build import build_instance_images, build_env_images
import docker

@dataclass
class ValidationResult:
    """Result of validating a data point"""
    instance_id: str
    passed: bool
    message: str
    details: Optional[Dict] = None


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

    def load_datapoint(self, json_path: Path) -> Dict:
        """
        Load and validate JSON structure

        Raises:
            ValueError: If JSON is malformed or missing required fields
        """
        required_fields = [
            "instance_id", "repo", "base_commit", "patch",
            "FAIL_TO_PASS", "PASS_TO_PASS"
        ]

        with open(json_path) as f:
            data = json.load(f)

        # Validate structure
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        return data

    def create_prediction(self, datapoint: Dict) -> Dict:
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
            "model_name_or_path": "golden-validator"
        }

    def build_docker_images(self, datapoint: Dict, force_rebuild: bool = False):
        """
        Build required Docker images for evaluation

        Args:
            datapoint: The data point to build images for
            force_rebuild: Whether to force rebuild even if images exist
        """
        self.logger.info("Building Docker images (this may take a while on first run)...")

        # Get Docker client
        client = docker.from_env()

        # Build environment image first (repo-level dependencies)
        self.logger.info(f"Building environment image for {datapoint['repo']}...")
        build_env_images(
            client=client,
            dataset=[datapoint],
            force_rebuild=force_rebuild,
            max_workers=1
        )

        # Build instance image (specific commit + patches)
        self.logger.info(f"Building instance image for {datapoint['instance_id']}...")
        build_instance_images(
            client=client,
            dataset=[datapoint],
            force_rebuild=force_rebuild,
            max_workers=1,
            namespace="swebench",
            tag="latest"
        )

        self.logger.info("Docker images built successfully")

    def run_swebench_evaluation(
        self,
        datapoint: Dict,
        prediction: Dict,
        timeout: int = 900  # 15 minutes default
    ) -> Dict:
        """
        Run SWE-bench evaluation in Docker

        Returns:
            Evaluation results from run_instances
        """
        from datetime import datetime

        # Build Docker images first
        self.build_docker_images(datapoint, force_rebuild=False)

        # Create instances list (SWE-bench format)
        instances = [datapoint]

        # Create predictions dict: {instance_id: prediction}
        predictions = {
            datapoint["instance_id"]: prediction
        }

        # Generate unique run ID
        run_id = f"validate_{datapoint['instance_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Run evaluation using SWE-bench harness
        results = run_instances(
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
            rewrite_reports=False
        )

        # Results is a list of tuples: (instance_id, report)
        if results:
            _, report = results[0]
            return report
        else:
            raise RuntimeError("No evaluation results returned")

    def validate_test_results(self, datapoint: Dict, eval_result: Dict) -> ValidationResult:
        """
        Check that all required tests pass

        Validates:
        - All FAIL_TO_PASS tests now pass
        - All PASS_TO_PASS tests still pass
        """
        import json as json_lib

        fail_to_pass = json_lib.loads(datapoint["FAIL_TO_PASS"])
        pass_to_pass = json_lib.loads(datapoint["PASS_TO_PASS"])

        # Extract test results from eval_result
        # SWE-bench returns: eval_result["test_results"]
        test_results = eval_result.get("test_results", {})

        failed_tests = []

        # Check FAIL_TO_PASS tests
        for test in fail_to_pass:
            if test not in test_results or not test_results[test]:
                failed_tests.append(f"FAIL_TO_PASS test failed: {test}")

        # Check PASS_TO_PASS tests
        for test in pass_to_pass:
            if test not in test_results or not test_results[test]:
                failed_tests.append(f"PASS_TO_PASS test failed: {test}")

        if failed_tests:
            return ValidationResult(
                instance_id=datapoint["instance_id"],
                passed=False,
                message=f"Test failures: {len(failed_tests)} test(s) failed",
                details={"failed_tests": failed_tests}
            )

        return ValidationResult(
            instance_id=datapoint["instance_id"],
            passed=True,
            message="All tests passed"
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
                details={"error_type": type(e).__name__}
            )
