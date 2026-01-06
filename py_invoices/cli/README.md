
# CLI Usage

The package includes a configured CLI tool `py-invoices`.

## Global Options

- `--help`: Show help message.

## Setup & Configuration

Configure the application interactively or via CLI arguments.

**Interactive Wizard:**
```bash
py-invoices setup
```

**Automated Setup (Agent Friendly):**
```bash
py-invoices setup --backend files --storage-path ./my-invoices --output-dir ./Outbox --force
```

**Initialize Backend:**
After setup, run initialization to prepare the database or storage:
```bash
py-invoices init
```

## Clients Management

Manage your client database.

**List Clients:**
```bash
py-invoices clients list
```

**Create Client:**
```bash
py-invoices clients create --name "Acme Corp" --address "123 Industrial Way" --tax-id "US-999" --email "contact@acme.com"
```

## Invoices Management

Manage and generate invoices.

**List Invoices:**
```bash
py-invoices invoices list
```

**Create Invoice:**
```bash
py-invoices invoices create --client-name "Acme Corp" --amount 1500.00 --description "Web Development"
```

*Create with Format Generation & Custom Details:*
```bash
py-invoices invoices create \
  --client-name "Acme Corp" \
  --amount 1500.00 \
  --description "Project X" \
  --invoice-number "0001" \
  --payment-terms "Net 30" \
  --bank-account "IBAN: US123456" \
  --format pdf --format html \
  --company-name "My Company" \
  --company-address "123 Business Rd"
```

*Auto-Create Client with Contact Info:*
```bash
py-invoices invoices create \
  --client-name "new Client" \
  --client-email "new@client.com" \
  --client-phone "+1234567890" \
  --amount 500 \
  --description "Services"
```

**Details:**
```bash
py-invoices invoices details <invoice_number_or_id>
```

**Overdue Invoices:**
```bash
py-invoices invoices overdue
```

**Statistics:**
```bash
py-invoices invoices stats --start-date 2024-01-01 --end-date 2024-12-31
```

**Clone Invoice:**
```bash
py-invoices invoices clone <invoice_number_or_id>
```

**Generate PDF:**
```bash
py-invoices invoices pdf <invoice_number_or_id> --company-name "My Company" --company-address "123 Business Rd"
```
*Example:*
```bash
py-invoices invoices pdf INV-2024-001 --output ./my-invoices --company-name "Dev Shop" --company-address "1 Main St"
```

**Generate HTML:**
```bash
py-invoices invoices html <invoice_number_or_id> --company-name "My Company" --company-address "123 Business Rd"
```
*Example:*
```bash
py-invoices invoices html INV-2024-001
```


## Products Management

Manage your product catalog.

**List Products:**
```bash
py-invoices products list
```

**Create Product:**
```bash
py-invoices products create --name "Consulting" --price 150.00 --sku "CONS-001"
```

## Companies Management

Manage company profiles.

**List Companies:**
```bash
py-invoices companies list
```

**Create Company:**
```bash
py-invoices companies create --name "My Configured Company" --address "123 HQ Blvd" --tax-id "US-TAX-ID"
```

## Credit Notes Management

Manage credit notes.

**List Credit Notes:**
```bash
py-invoices credit-notes list
```

**Create Credit Note:**
```bash
py-invoices credit-notes create --invoice-number "INV-2024-001" --reason "Refund"
```

## Payments Management

Manage payments.

**List Payments:**
```bash
py-invoices payments list
```

**Create Payment:**
```bash
py-invoices payments create --invoice-number "INV-2024-001" --amount 1500.00 --reference "Wire Transfer"
```

## Validation

Validate generated UBL XML files for compliance.

```bash
py-invoices validate invoice <path_to_xml>
```
*Example:*
```bash
py-invoices validate invoice output/INV-2024-0001.xml
```

## Storage Backends

You can select the storage backend using the `--backend` option or `INVOICES_BACKEND` environment variable.

- `memory` (default for dev): Data is lost after command exits (mostly useful for testing logic).
- `files`: Local file storage (JSON, YAML, Markdown).
- `sqlite`: Persistent local database.
- `postgres`: PostgreSQL database.

**Initialize/Switch Backend:**
The CLI mostly auto-intializes on use, but you can verify with:
```bash
py-invoices init --backend sqlite
```
