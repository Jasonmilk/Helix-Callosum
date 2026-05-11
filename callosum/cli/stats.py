"""Stats subcommand."""

import httpx
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="stats", help="Cache statistics commands")
console = Console()


@app.command("show")
def show_stats(
    host: str = typer.Option("http://localhost:8687", help="Server host"),
    namespace: str = typer.Option(None, help="Filter by namespace"),
    model: str = typer.Option(None, help="Filter by model"),
):
    """Show cache usage statistics."""
    try:
        resp = httpx.get(
            f"{host}/v1/usage-stats",
            params={"namespace": namespace, "model": model},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        
        # Print summary
        console.print("[bold]Helix-Callosum Cache Statistics[/bold]")
        console.print(f"Total Requests: {data['total_requests']}")
        console.print(f"Hit Rate: {data['overall_hit_rate']:.2%}")
        console.print(f"Tokens Saved: {data['total_tokens_saved']:,}")
        console.print(f"Cost Saved: ${data['total_cost_saved_usd']:.2f}")
        
        # Print namespace table
        if data["by_namespace"]:
            table = Table(title="By Namespace")
            table.add_column("Namespace")
            table.add_column("Requests")
            table.add_column("Hit Rate")
            table.add_column("Tokens Saved")
            
            for ns, stats in data["by_namespace"].items():
                table.add_row(
                    ns,
                    str(stats["requests"]),
                    f"{stats['hit_rate']:.2%}",
                    f"{stats['tokens_saved']:,}",
                )
            console.print(table)
        
        # Print model table
        if data["by_model"]:
            table = Table(title="By Model")
            table.add_column("Model")
            table.add_column("Requests")
            table.add_column("Hit Rate")
            table.add_column("Tokens Saved")
            
            for mid, stats in data["by_model"].items():
                table.add_row(
                    mid,
                    str(stats["requests"]),
                    f"{stats['hit_rate']:.2%}",
                    f"{stats['tokens_saved']:,}",
                )
            console.print(table)
            
    except Exception as e:
        typer.echo(f"Failed to fetch stats: {e}", err=True)
        raise typer.Exit(1)
