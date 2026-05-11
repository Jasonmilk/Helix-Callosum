"""Server subcommand."""

import typer
from callosum.gateway.app import run_server

app = typer.Typer(name="server", help="Server management commands")


@app.command("start")
def start_server():
    """Start the Callosum gateway server."""
    typer.echo("Starting Helix-Callosum gateway server...")
    run_server()
