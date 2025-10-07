"""
Command-line interface for the SWE-bench data point validator.
"""

import click
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .validator import SWEBenchValidator, ValidationResult

console = Console()


@click.command()
@click.argument(
    'datapoint_path',
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    '--timeout',
    type=int,
    default=900,
    help='Timeout for evaluation in seconds (default: 900 / 15 minutes)',
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Enable verbose output',
)
def main(datapoint_path: Path, timeout: int, verbose: bool):
    """
    Validate a SWE-bench data point using the official evaluation harness.

    This validator:
    - Loads the data point from JSON
    - Runs SWE-bench evaluation in Docker using the golden patch
    - Validates that all FAIL_TO_PASS tests pass after applying the patch
    - Validates that all PASS_TO_PASS tests still pass

    Examples:

        # Validate a single data point
        swe-bench-validate data_points/astropy__astropy-11693.json

        # Validate with custom timeout
        swe-bench-validate data_points/django__django-10087.json --timeout 1200

        # Validate with verbose output
        swe-bench-validate data_points/astropy__astropy-11693.json -v
    """
    try:
        # Display header
        console.print(
            Panel.fit(
                f"[bold cyan]SWE-bench Data Point Validator[/bold cyan]\n"
                f"Data point: [yellow]{datapoint_path.name}[/yellow]",
                border_style="cyan",
            )
        )

        # Initialize validator
        validator = SWEBenchValidator(timeout=timeout, verbose=verbose)

        # Run validation
        with console.status(
            "[bold green]Running validation...",
            spinner="dots"
        ):
            result = validator.validate(datapoint_path)

        # Display results
        _display_result(result)

        # Exit with appropriate code
        sys.exit(0 if result.passed else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Validation interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[bold red] Unexpected error: {str(e)}[/bold red]")
        if verbose:
            console.print_exception()
        sys.exit(1)


def _display_result(result: ValidationResult):
    """Display validation result in a formatted way"""

    # Create result table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Instance ID", result.instance_id)
    table.add_row(
        "Status",
        f"[bold green] PASSED[/bold green]" if result.passed else "[bold red] FAILED[/bold red]"
    )
    table.add_row("Message", result.message)

    console.print("\n")
    console.print(table)

    # Display detailed error information if available
    if result.details and not result.passed:
        console.print("\n[bold red]Error Details:[/bold red]")

        if "failed_tests" in result.details:
            console.print("\n[bold]Failed Tests:[/bold]")
            for test in result.details["failed_tests"]:
                console.print(f"  • {test}")

        if "error_type" in result.details:
            console.print(f"\n[bold]Error Type:[/bold] {result.details['error_type']}")

    console.print()


if __name__ == "__main__":
    main()
