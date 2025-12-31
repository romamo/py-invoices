"""UBL Invoice generation service.

Provides UBL (Universal Business Language) XML generation using Jinja2.
"""

from typing import TYPE_CHECKING, Any

from py_invoices.core.html_service import HTMLService

if TYPE_CHECKING:
    pass


class UBLService(HTMLService):
    """Service for generating UBL XML invoices.

    Inherits from HTMLService to reuse Jinja2 logic.
    """

    def __init__(
        self,
        template_dir: str | None = None,
        output_dir: str = "output",
        default_template: str = "ubl_invoice.xml.j2",
    ):
        """Initialize UBL service.

        Args:
            template_dir: Directory containing Jinja2 templates (optional)
            output_dir: Directory for generated files
            default_template: Default UBL template filename
        """
        super().__init__(template_dir, output_dir, default_template)

    def generate_ubl(self, *args: Any, **kwargs: Any) -> str:
        """Alias for generate_html but for UBL content."""
        return self.generate_html(*args, **kwargs)

    def generate_ubl_bytes(self, *args: Any, **kwargs: Any) -> bytes:
        """Generate UBL XML as bytes."""
        return self.generate_ubl(*args, **kwargs).encode("utf-8")

    def save_ubl(self, *args: Any, **kwargs: Any) -> str:
        """Alias for save_html but for UBL files."""
        # Ensure correct extension if auto-generating filename
        kwargs = kwargs.copy()
        if not kwargs.get("output_filename"):
            # We rely on super() to handle rendering, but we want to intercept filename generation.
            # actually simpler to just let user provide filename or default to inheritance behavior
            pass

        # For simplicity, we just use save_html, but users should provide output_filename
        # or we might get .html extension by default from the base class if we don't override.

        return self.save_html(*args, **kwargs)

    def save_html(
        self,
        invoice: Any,
        company: dict[str, Any],
        output_filename: str | None = None,
        template_name: str | None = None,
        logo_path: str | None = None,
        **context: Any,
    ) -> str:
        """Override to default to .xml extension."""
        if not output_filename:
            output_filename = f"{invoice.number}.xml"
        return super().save_html(
            invoice,
            company,
            output_filename=output_filename,
            template_name=template_name,
            logo_path=logo_path,
            **context,
        )
