"""Server subcommand."""

import typer

app = typer.Typer(name="server", help="Server management commands")


@app.command("start")
def start_server():
    """Start the Callosum gateway server."""
    # Delayed import to prevent loading the entire gateway on CLI init
    from callosum.gateway.app import run_server
    typer.echo("Starting Helix-Callosum gateway server...")
    run_server()
