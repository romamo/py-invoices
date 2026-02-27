import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

console = Console()


def install_package(package: str) -> bool:
    """Install a package using uv (preferred) or pip."""
    try:
        # Try uv first
        uv_path = shutil.which("uv")
        if uv_path:
            subprocess.run(  # nosec B603
                [uv_path, "pip", "install", package], check=True, capture_output=True
            )
            return True

        # Fallback to pip
        subprocess.run(  # nosec B603
            [sys.executable, "-m", "pip", "install", package], check=True, capture_output=True
        )
        return True
    except subprocess.CalledProcessError:
        return False


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
    Configure py-invoices settings interactively or via CLI arguments.
    Generates a .env file for persistent configuration.
    """
    # Check/Install python-dotenv
    try:
        import dotenv  # noqa: F401
    except ImportError:
        console.print("[dim]Installing python-dotenv...[/dim]")
        if install_package("python-dotenv"):
            console.print("[green]Installed python-dotenv[/green]")
        else:
            console.print(
                "[yellow]Failed to install python-dotenv. Please install manually.[/yellow]"
            )

    env_path = Path(".env")
    if env_path.exists() and not force:
        if not Confirm.ask(f"[yellow]{env_path.absolute()} already exists. Overwrite?[/yellow]"):
            console.print("[red]Aborted.[/red]")
            raise typer.Exit()

    # --- Configuration Logic ---

    # Defaults
    default_storage_path = "./data"
    # Actually checking settings.py: default file_format is "md".
    default_format_real = "md"

    # 1. Backend
    if not backend:
        console.print("[bold cyan]Welcome to py-invoices setup![/bold cyan]")
        backend = Prompt.ask(
            "Choose a storage backend",
            choices=["files", "sqlite", "postgres", "mysql", "memory"],
            default="files",
        )

    # Check/Install backend dependencies
    backend_extras = {
        "sqlite": "py-invoices[sqlite]",
        "postgres": "py-invoices[postgres]",
        "mysql": "py-invoices[mysql]",
    }

    if backend in backend_extras:
        extra_pkg = backend_extras[backend]
        # Check if sqlmodel is installed (common dep for all SQL backends)
        try:
            import sqlmodel  # noqa: F401

            # For postgres/mysql specifically check drivers?
            # Keeping it simple: if generic sqlmodel missing, install extra.
            if backend == "postgres":
                import psycopg2  # noqa: F401
            elif backend == "mysql":
                import pymysql  # noqa: F401
        except ImportError:
            console.print(f"[dim]Installing dependencies for {backend}...[/dim]")
            if install_package(extra_pkg):
                console.print(f"[green]Installed {extra_pkg}[/green]")
            else:
                console.print(f"[yellow]Failed to install {extra_pkg}.[/yellow]")

    config_lines = [
        f"INVOICES_BACKEND={backend}",
    ]

    # 2. Specific Configs
    if backend == "files":
        # Storage Path
        if storage_path is None:
            storage_path = Prompt.ask("Enter storage path", default=default_storage_path)
        config_lines.append(f"INVOICES_STORAGE_PATH={storage_path}")

        # format
        if file_format is None:
            file_format = Prompt.ask(
                "Enter file format", choices=["json", "xml", "md"], default=default_format_real
            )
        config_lines.append(f"INVOICES_FILE_FORMAT={file_format}")

    elif backend in ["sqlite", "postgres", "mysql"]:
        if db_url is None:
            example = "sqlite:///invoices.db"
            if backend == "postgres":
                example = "postgresql://user:pass@localhost/db"
            elif backend == "mysql":
                example = "mysql://user:pass@localhost/db"

            db_url = Prompt.ask(f"Enter Database URL (e.g. {example})")

        if db_url:
            config_lines.append(f"INVOICES_DATABASE_URL={db_url}")

    # 3. Output Directory
    if output_dir:
        config_lines.append(f"INVOICES_OUTPUT_DIR={output_dir}")

    # Write to .env
    with open(env_path, "w") as f:
        f.write("# Generated by py-invoices setup\n")
        f.write("\n".join(config_lines))
        f.write("\n")

    console.print(f"\n[green]Configuration saved to {env_path.absolute()}[/green]")

    console.print("\n[dim]Next step: Run initialization[/dim]")
    console.print("[bold]py-invoices init[/bold]")
