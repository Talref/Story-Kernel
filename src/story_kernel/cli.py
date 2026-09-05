"""Unified local launcher for the experiment harness."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .ui import build_interface, create_harness

app = typer.Typer(help="Story Kernel Experiment 0.1a")


@app.command()
def run(
    database: Annotated[
        Path, typer.Option("--database", "-d", help="SQLite database path.")
    ] = Path(".story-kernel/story-kernel.db"),
    host: Annotated[str, typer.Option(help="Local interface host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Local interface port.")] = 7860,
    open_browser: Annotated[
        bool, typer.Option("--open-browser", help="Open the browser on launch.")
    ] = False,
) -> None:
    """Initialize persistence and launch the complete Gradio experiment harness."""
    harness = create_harness(database)
    build_interface(harness).launch(
        server_name=host, server_port=port, inbrowser=open_browser
    )


@app.command("init")
def initialize(
    database: Annotated[
        Path, typer.Option("--database", "-d", help="SQLite database path.")
    ] = Path(".story-kernel/story-kernel.db"),
) -> None:
    """Initialize the local database without launching Gradio."""
    create_harness(database)
    typer.echo(f"Initialized Story Kernel at {database}")


if __name__ == "__main__":
    app()
