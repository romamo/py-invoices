"""HTML generation service.

Provides invoice HTML generation using Jinja2 templates.
"""

import os
from pathlib import Path
from typing import Any

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from pydantic_invoices.schemas import Invoice

from py_invoices.core.totals import cents, format_money, invoice_totals, line_net

PACKAGE_TEMPLATES_DIR = str(Path(__file__).parent.parent / "templates")

# Templates are named "*.html.j2" / "*.xml.j2"; the inner extension selects escaping.
AUTOESCAPE_EXTENSIONS = ("html", "xml", "html.j2", "xml.j2")


def is_safe_file_name(name: str) -> bool:
    """True for a plain file name: no directory part, no leading dot, no NUL."""
    return (
        bool(name)
        and name == os.path.basename(name)
        and not name.startswith(".")
        and "\\" not in name
        and "\0" not in name
    )


def output_path(output_dir: str, filename: str) -> str:
    """Path of `filename` inside `output_dir`.

    Raises:
        ValueError: If the name contains a directory part or starts with a dot, which would
            let a document number such as "../x" write outside `output_dir`
    """
    if not is_safe_file_name(filename):
        raise ValueError(f"Unsafe output file name: {filename!r}")
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, filename)


def nl2br(value: object) -> Markup:
    """Escape a value and turn its newlines (real or literal "\\n") into <br>."""
    if value is None:
        return Markup("")
    text = str(value).replace("\\n", "\n")
    return Markup("<br>").join(escape(part) for part in text.split("\n"))


class HTMLService:
    """Service for generating HTML invoices from templates.

    This service uses Jinja2 for templating.
    """

    def __init__(
        self,
        template_dir: str | None = None,
        output_dir: str = "output",
        default_template: str = "invoice.html.j2",
    ):
        """Initialize HTML service.

        Args:
            template_dir: Directory with templates that take precedence over the package ones
            output_dir: Directory for generated files, created on first save
            default_template: Default template filename
        """
        self.output_dir = output_dir
        self.default_template = default_template
        self.template_dir = template_dir or PACKAGE_TEMPLATES_DIR

        loaders = [FileSystemLoader(PACKAGE_TEMPLATES_DIR)]
        if template_dir:
            loaders.insert(0, FileSystemLoader(template_dir))

        self.env = Environment(
            loader=ChoiceLoader(loaders),
            autoescape=select_autoescape(AUTOESCAPE_EXTENSIONS),
        )
        self.env.filters["nl2br"] = nl2br
        self.env.filters["money"] = format_money
        self.env.filters["cents"] = cents
        self.env.globals["line_net"] = line_net

    def generate_html(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Render a template with the invoice, company, computed totals and extra context."""
        template = self.env.get_template(template_name or self.default_template)
        return template.render(
            invoice=invoice,
            company=company,
            totals=invoice_totals(invoice),
            **context,
        )

    def _write(self, filename: str, content: str) -> str:
        path = output_path(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def save_html(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        **context: Any,
    ) -> str:
        """Save invoice as HTML file and return its path (defaults to "<number>.html")."""
        html_content = self.generate_html(
            invoice=invoice, company=company, template_name=template_name, **context
        )
        return self._write(output_filename or f"{invoice.number}.html", html_content)
