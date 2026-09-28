"""Configuration and template discovery operations."""

import os
from dataclasses import dataclass
from pathlib import Path

from py_invoices.config import InvoiceSettings
from py_invoices.operations.invoices import package_template_dir


@dataclass(frozen=True, slots=True)
class SettingsOverview:
    backend: str
    masked_database_url: str | None
    file_format: str
    output_dir: str
    template_dir: str | None


def settings_overview(settings: InvoiceSettings) -> SettingsOverview:
    """Effective settings with absolute paths and the database credentials masked."""
    masked_url = None
    if settings.database_url:
        scheme, sep, _ = settings.database_url.partition("://")
        masked_url = f"{scheme}://***" if sep else "***"
    return SettingsOverview(
        backend=settings.backend,
        masked_database_url=masked_url,
        file_format=settings.file_format,
        output_dir=os.path.abspath(settings.output_dir),
        template_dir=os.path.abspath(settings.template_dir) if settings.template_dir else None,
    )


@dataclass(frozen=True, slots=True)
class TemplateEntry:
    name: str
    source: str
    path: str


@dataclass(frozen=True, slots=True)
class TemplateCatalog:
    templates: list[TemplateEntry]
    package_dir: Path
    user_dir: Path | None


def _j2_files(directory: Path) -> list[Path]:
    """Selectable templates; names starting with "_" are partials used by other templates."""
    return [
        f
        for f in directory.iterdir()
        if f.is_file() and f.suffix == ".j2" and not f.name.startswith("_")
    ]


def template_catalog(settings: InvoiceSettings) -> TemplateCatalog:
    """Packaged and user templates by name; a user template overrides a packaged one."""
    package_dir = Path(package_template_dir())
    user_dir = Path(settings.template_dir) if settings.template_dir else None

    found: dict[str, tuple[str, str]] = {}
    if package_dir.exists():
        for f in _j2_files(package_dir):
            found[f.name] = ("Packaged", str(f.absolute()))
    if user_dir and user_dir.exists():
        for f in _j2_files(user_dir):
            source = "User Override" if f.name in found else "User"
            found[f.name] = (source, str(f.absolute()))

    templates = [
        TemplateEntry(name, source, path) for name, (source, path) in sorted(found.items())
    ]
    return TemplateCatalog(templates=templates, package_dir=package_dir, user_dir=user_dir)
