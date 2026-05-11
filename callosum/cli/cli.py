"""CLI root command group."""

import typer
from . import server
from . import stats

app = typer.Typer(
    name="callosum",
    help="Helix-Callosum: Context Memory Allocator for AI Agents",
    add_completion=False,
)

# Add subcommands
app.add_typer(server.app, name="server", help="Server management commands")
app.add_typer(stats.app, name="stats", help="Cache statistics commands")


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
