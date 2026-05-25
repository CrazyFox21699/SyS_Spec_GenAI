#!/usr/bin/env python3
"""CLI entry for ALEX (spec trace and review)."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline import run_analyze  # noqa: E402

app = typer.Typer(help="ALEX — extract, trace evidence, review, test-spec candidates.")


@app.command()
def analyze(
    input_dir: Path = typer.Option(Path("input"), "--input", "-i", help="Folder with customer documents"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o", help="Output folder for YAML + review/"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Path to config.yaml"),
    force: bool = typer.Option(False, "--force", help="Skip timestamped backup of existing outputs"),
) -> None:
    """Classify → parse → model → review package → test spec candidates (no GTest codegen in v0.1)."""
    bundle = run_analyze(input_dir.resolve(), output_dir.resolve(), config.resolve(), force=force)
    typer.echo(f"Done. Review package: {output_dir.resolve() / 'review'}")
    if bundle.get("summary"):
        typer.echo(f"Summary: {bundle['summary']}")


@app.command("classify")
def classify_only(
    input_dir: Path = typer.Option(Path("input"), "--input", "-i"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
) -> None:
    typer.echo("v0.1: use `analyze` for the full pipeline (classify is included). Stub retained for CLI compatibility.")


@app.command("extract")
def extract_only(
    input_dir: Path = typer.Option(Path("input"), "--input", "-i"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c"),
) -> None:
    typer.echo("v0.1: use `analyze` (extract is included).")


@app.command("generate-review")
def generate_review(
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
) -> None:
    typer.echo("v0.1: review markdown is produced by `analyze` from intermediate YAML.")


@app.command("generate-test-spec")
def generate_test_spec(
    output_dir: Path = typer.Option(Path("output"), "--output", "-o"),
) -> None:
    typer.echo("v0.1: test spec candidates are produced by `analyze`.")


if __name__ == "__main__":
    app()
