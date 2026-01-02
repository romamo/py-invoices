
# CLI Usage

The package includes a configured CLI tool `py-invoices`.

## Global Options

- `--help`: Show help message.

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

You can select the storage backend using the `--backend` option or `PY_INVOICES_BACKEND` environment variable.

- `memory` (default for dev): Data is lost after command exits (mostly useful for testing logic).
- `sqlite`: Persistent local database.
- `postgres`: PostgreSQL database.

**Initialize/Switch Backend:**
The CLI mostly auto-intializes on use, but you can verify with:
```bash
py-invoices init --backend sqlite
```
