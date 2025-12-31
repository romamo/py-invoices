"""HTML generation service.

Provides invoice HTML generation using Jinja2 templates.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from pydantic_invoices.schemas import Invoice  # type: ignore[import-untyped]


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
            template_dir: Directory containing Jinja2 templates (optional)
            output_dir: Directory for generated files
            default_template: Default template filename

        Raises:
            ImportError: If jinja2 is not installed
        """
        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
        except ImportError:
            raise ImportError(
                "Jinja2 is required for HTML generation. "
                "Install it with: pip install py-invoices[html]"
            )

        self.output_dir = output_dir
        self.default_template = default_template

        # Ensure output directory exists
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Determine template directory and loader
        # 1. If explicit template_dir provided, use it
        # 2. Use package templates
        loader: Any
        if template_dir:
            self.template_dir = template_dir
            loader = FileSystemLoader(template_dir)
        else:
            # Package loader - default
            # Try to use PackageLoader if possible,
            # but FileSystemLoader on absolute path is also fine
            # We don't store a path str here as it's internal to the package
            self.template_dir = str(Path(__file__).parent.parent / "templates")
            loader = FileSystemLoader(self.template_dir)

        # Setup Jinja2 environment
        self.env: Environment = Environment(
            loader=loader,
            autoescape=select_autoescape(["html", "xml"])
        )

    def generate_html(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        template_name: str | None = None,
        logo_path: str | None = None,
        **context: Any,
    ) -> str:
        """Generate HTML from invoice data.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            template_name: Template to use (defaults to default_template)
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template(template_name or self.default_template)

        return template.render(
            invoice=invoice,
            company=company,
            logo_path=logo_path,
            **context,
        )

    def save_html(
        self,
        invoice: Invoice,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        logo_path: str | None = None,
        **context: Any,
    ) -> str:
        """Save invoice as HTML file.

        Args:
            invoice: Invoice schema instance
            company: Company information dictionary
            output_filename: Custom output filename (defaults to invoice number)
            template_name: Template to use (defaults to default_template)
            logo_path: Optional path to company logo
            **context: Additional template context variables

        Returns:
            Path to generated HTML file
        """
        # Generate HTML
        html_content = self.generate_html(
            invoice=invoice,
            company=company,
            template_name=template_name,
            logo_path=logo_path,
            **context,
        )

        # Determine output path
        if not output_filename:
            output_filename = f"{invoice.number}.html"

        output_path = os.path.join(self.output_dir, output_filename)

        # Save HTML
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path
