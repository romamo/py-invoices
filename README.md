# py-invoices

Framework-agnostic invoice management with pluggable storage backends.

## Features

- **Pluggable Storage Backends**: Swap between SQLite, PostgreSQL, MySQL or in-memory storage
- **E-Invoicing Ready**: Built-in support for Factur-X (ZUGFeRD) and UBL standards
- **Audit Logging**: Integrated audit trail for tracking all invoice lifecycles
- **Framework-Agnostic**: Designed for integration into any Python application
- **Type-Safe**: Built on `pydantic-invoices` schemas with full type hints
- **Flexible**: Optional dependencies - install only what you need
- **In-Memory Operations**: HTML generation and byte-stream output supported out-of-the-box

## Installation

```bash
# Basic installation (includes HTML generation)
pip install py-invoices

# With CLI support (recommended for interactive use)
pip install "py-invoices[cli]"

# With SQLite support
pip install py-invoices[sqlite]

# With PostgreSQL support
pip install py-invoices[postgres]

# With MySQL support
pip install py-invoices[mysql]

# With PDF generation
pip install py-invoices[pdf]

# Everything
pip install py-invoices[all]
```

### PDF Generation Requirements

PDF generation uses **WeasyPrint**, which requires system-level libraries for rendering (Pango, GObject, Cairo).

**macOS:**
```bash
brew install pango libffi
# You may also need to set the library path:
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH
```

**Linux/Ubuntu:**
```bash
sudo apt-get install python3-pip python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0
```

For more details, see the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#installation).

## CLI Usage

The package includes a configured CLI tool `py-invoices`.

**Quick Start:**
```bash
# Create an invoice (and auto-create client)
py-invoices invoices create --client-name "Acme Corp" --amount 1500.00 --description "Consulting"
```

For full documentation on available commands (listing, generating PDFs, backend configuration), see the **[CLI Documentation](py_invoices/cli/README.md)**.


## Quick Start

```python
from datetime import datetime
from py_invoices import RepositoryFactory
from pydantic_invoices.schemas import ClientCreate, InvoiceCreate, InvoiceLineCreate, InvoiceStatus

# Initialize with memory backend
factory = RepositoryFactory(backend="memory")

# Get repositories
client_repo = factory.create_client_repository()
invoice_repo = factory.create_invoice_repository()

# Create a client
client = client_repo.create(ClientCreate(
    name="Acme Corp",
    address="123 Business St",
    tax_id="12-3456789"
))

# Create an invoice
invoice = invoice_repo.create(InvoiceCreate(
    number="INV-2025-0001",
    issue_date=datetime.now(),
    status=InvoiceStatus.UNPAID,
    client_id=client.id,
    client_name_snapshot=client.name,
    client_address_snapshot=client.address,
    client_tax_id_snapshot=client.tax_id,
    lines=[
        InvoiceLineCreate(
            description="Professional Services",
            quantity=40,
            unit_price=150.0
        )
    ]
))

print(f"Created invoice {invoice.number} for ${invoice.total_amount}")
```

## Configuration

### Environment Variables

Configure backends using environment variables or `.env` files:

```bash
# Set environment variables
export INVOICES_BACKEND=sqlite
export INVOICES_DATABASE_URL=sqlite:///invoices.db
export INVOICES_DATABASE_ECHO=false
```

```python
from py_invoices import RepositoryFactory

# Automatically loads from environment variables and .env file
factory = RepositoryFactory.from_settings()
```

### Using .env File

Create a `.env` file in your project root:

```bash
INVOICES_BACKEND=sqlite
INVOICES_DATABASE_URL=sqlite:///invoices.db
INVOICES_DATABASE_ECHO=false
# INVOICES_TEMPLATE_DIR=templates
INVOICES_OUTPUT_DIR=output
```

```python
from py_invoices import RepositoryFactory

# Loads configuration from .env file automatically
factory = RepositoryFactory.from_settings()
```

### Programmatic Configuration

```python
from py_invoices import InvoiceSettings, RepositoryFactory

settings = InvoiceSettings(
    backend="sqlite",
    database_url="sqlite:///invoices.db",
    database_echo=False
)

factory = RepositoryFactory.from_settings(settings)
```

### Available Settings

| Setting | Environment Variable | Default | Description |
|---------|---------------------|---------|-------------|
| `backend` | `INVOICES_BACKEND` | `memory` | Backend type: `memory`, `files`, `sqlite`, `postgres`, `mysql` |
| `database_url` | `INVOICES_DATABASE_URL` | `None` | Database connection URL |
| `database_echo` | `INVOICES_DATABASE_ECHO` | `false` | Enable SQL query logging |
| `file_format` | `INVOICES_FILE_FORMAT` | `md` | Format for files backend: `json`, `yaml`, `yml`, or `md` |
| `root_dir` | `INVOICES_ROOT_DIR` | `./data` | Root directory for files backend |
| `template_dir` | `INVOICES_TEMPLATE_DIR` | `None` | Directory for invoice templates (defaults to included) |
| `output_dir` | `INVOICES_OUTPUT_DIR` | `output` | Directory for generated files |

## Core Services

### PDF Generation

Generate professional PDF/HTML invoices using Jinja2 templates:

```python
from py_invoices.core import PDFService

# Company details for the invoice header
company = {
    "name": "My Company",
    "address": "123 HQ Blvd, Tech City",
    "tax_id": "US-99999"
}

pdf_service = PDFService(output_dir="output")

# Generate to file
pdf_path = pdf_service.generate_pdf(invoice=invoice, company=company)

# Generate to memory (bytes)
pdf_bytes = pdf_service.generate_pdf_bytes(invoice=invoice, company=company)
```

### HTML Generation

For scenarios where you only need HTML (e.g. emails) or don't want the heavy WeasyPrint dependency:

```python
from py_invoices.core import HTMLService

# Uses only Jinja2 (no WeasyPrint)
html_service = HTMLService(output_dir="output")

# Generate HTML string
html_content = html_service.generate_html(invoice=invoice, company=company)

# Save to HTML file
html_path = html_service.save_html(invoice=invoice, company=company)
```

### Industry Standard (Factur-X / UBL)

Generate enterprise-ready invoices compliant with European standards:

**Factur-X (PDF/A-3 + XML):**
A standard PDF that includes the invoice data as a structured XML file (Factur-X/ZUGFeRD compliant).

```python
# Requires py-invoices[pdf]
facturx_path = pdf_service.generate_facturx(invoice=invoice, company=company)
```

**UBL (XML Only):**
Universal Business Language Version 2.1 XML invoices.

```python
from py_invoices.core import UBLService

ubl_service = UBLService(output_dir="output")
ubl_path = ubl_service.save_ubl(invoice, company)
```

### In-Memory Generation (Bytes)

Generate files directly to memory without saving to disk:

```python
# Generate Factur-X bytes
pdf_bytes = pdf_service.generate_facturx_bytes(invoice, company)

# Generate UBL XML bytes
xml_bytes = ubl_service.generate_ubl_bytes(invoice, company)
```

### Audit Logging

Track every change in the invoice lifecycle:

```python
from py_invoices.core import AuditService

audit_service = AuditService(audit_repo=factory.create_audit_repository())

# Log event
audit_service.log_invoice_created(invoice, user_id="system_admin")
audit_service.log_payment_added(invoice, payment, user_id="cashier_01")

# Retrieve logs
logs = audit_service.get_logs(invoice_id=invoice.id)
```

### Invoice Numbering

Generate sequential, formatted invoice numbers:

```python
from py_invoices.core import NumberingService

# Default format: INV-{year}-{sequence:04d}
numbering = NumberingService(invoice_repo=invoice_repo)
next_number = numbering.generate_number()
```

## Storage Backends

### Memory (Testing)

Perfect for development and testing:

```python
factory = RepositoryFactory(backend="memory")
```

### SQLite (Production-Ready)

For single-file database storage:

```python
factory = RepositoryFactory(
    backend="sqlite",
    database_url="sqlite:///invoices.db"
)
```

### PostgreSQL (Enterprise)

For production deployments:

```python
factory = RepositoryFactory(
    backend="postgres",
    database_url="postgresql://user:pass@localhost/invoices"
)
```

### MySQL

For common web server setups:

```python
factory = RepositoryFactory(
    backend="mysql",
    database_url="mysql+pymysql://user:pass@localhost/invoices"
)
```
### Files (Local Storage)

Stores data as individual files (JSON, YAML, XML, or Markdown) in a local directory. Markdown format is recommended for human readability and direct editing.

```python
factory = RepositoryFactory(
    backend="files",
    root_dir="./data",
    file_format="yaml"  # Defaults to "md" for *writing* new files
)
```

**Note:** The backend automatically detects and reads files in any supported format (`json`, `yaml`, `xml`, `md`) regardless of the `file_format` setting. This allows you to mix formats or manually edit files in your preferred format. It also supports friendly filenames for better organization (e.g., `1.Customer Name.json` instead of just `1.json`).
## Architecture

```
py-invoices (business logic)
    ↓ depends on
pydantic-invoices (schemas)
```

## Development

```bash
# Clone repository
git clone https://github.com/Romamo/py-invoices
cd py-invoices

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy py_invoices

# Linting
ruff check py_invoices
```

## License

MIT License - see LICENSE file for details.

## Related Packages

- [`pydantic-invoices`](https://pypi.org/project/pydantic-invoices/) - Pydantic schemas and interfaces
- [`pydantic`](https://docs.pydantic.dev/) - Data validation using Python type hints
