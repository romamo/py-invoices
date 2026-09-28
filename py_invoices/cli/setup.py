from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from py_invoices.constants import APP_NAME, CLI_NAME
from py_invoices.operations import setup as ops

console = Console()


def install_with_progress(package: str, label: str) -> None:
    console.print(f"[dim]Installing {label}...[/dim]")
    if ops.install_package(package):
        console.print(f"[green]Installed {package}[/green]")
    else:
        console.print(f"[yellow]Failed to install {package}.[/yellow]")


def interactive_setup(
    backend: str = typer.Option(
        None, help="Backend to use (files, sqlite, postgres, mysql, memory)"
    ),
    storage_path: str = typer.Option(None, help="Storage path for files backend (default: ./data)"),
    file_format: str = typer.Option(
        None, help="File format for files backend (json, md, xml, default: json)"
    ),
    db_url: str = typer.Option(None, help="Database URL for SQL backends"),
    output_dir: str = typer.Option(
        None, help="Output directory for generated files (default: output)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing .env file without asking"
    ),
) -> None:
    """
    Configure settings interactively or via CLI arguments.
    Generates a .env file for persistent configuration.
    """
    if not ops.module_available("dotenv"):
        console.print("[dim]Installing python-dotenv...[/dim]")
        if ops.install_package("python-dotenv"):
            console.print("[green]Installed python-dotenv[/green]")
        else:
            console.print(
                "[yellow]Failed to install python-dotenv. Please install manually.[/yellow]"
            )

    env_path = Path(".env")
    if (
        env_path.exists()
        and not force
        and not Confirm.ask(f"[yellow]{env_path.absolute()} already exists. Overwrite?[/yellow]")
    ):
        console.print("[red]Aborted.[/red]")
        raise typer.Exit()

    if not backend:
        console.print(f"[bold cyan]Welcome to {APP_NAME} setup![/bold cyan]")
        backend = Prompt.ask("Choose a storage backend", choices=ops.BACKENDS, default="files")

    extra = ops.missing_backend_extra(backend)
    if extra:
        install_with_progress(extra, f"dependencies for {backend}")

    if backend == "files":
        if storage_path is None:
            storage_path = Prompt.ask("Enter storage path", default=ops.DEFAULT_STORAGE_PATH)
        if file_format is None:
            file_format = Prompt.ask(
                "Enter file format", choices=ops.FILE_FORMATS, default=ops.DEFAULT_FILE_FORMAT
            )
    elif backend in ["sqlite", "postgres", "mysql"] and db_url is None:
        db_url = Prompt.ask(f"Enter Database URL (e.g. {ops.db_url_example(backend)})")

    lines = ops.env_config_lines(backend, storage_path, file_format, db_url, output_dir)
    ops.write_env_file(env_path, lines)

    console.print(f"\n[green]Configuration saved to {env_path.absolute()}[/green]")
    console.print("\n[dim]Next step: Run initialization[/dim]")
    console.print(f"[bold]{CLI_NAME} init[/bold]")
