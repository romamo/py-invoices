
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

Manage and generate invoices. The `invoices` commands run on [treaty](https://pypi.org/project/treaty/): off a terminal they print one JSON envelope (`ok`, `data`, `error`, `warnings`, `meta`), at a terminal the tables below, and `--format json` or `--format plain` picks one. Flags go after the command.

**List Invoices:**
```bash
py-invoices invoices list             # newest first, 10 at a time; --cursor from meta.pagination for the next page
py-invoices invoices list --limit 0   # every invoice
```

**Lifecycle: draft, then issue.** `create` and `clone` make a `DRAFT` numbered `DRAFT-<id>`; a draft can be edited and renders with a DRAFT watermark. `issue` gives it the next number of its series (gapless, in the order of issue), stores a SHA-256 hash of its content and marks it `SENT`. An issued invoice cannot be edited or deleted in any backend: correct it with `credit-notes create` and a new invoice (EU VAT Directive 2006/112/EC, art. 219 and 233). `--issue` on `create` or `clone` does both steps at once.

```bash
py-invoices invoices create --client-name "Acme Corp" --amount 1500.00 --description "Web Development"
py-invoices invoices update DRAFT-12 --unit-price 1450   # a line, --date, --due-date, --payment-terms
py-invoices invoices issue DRAFT-12                      # -> INV-2026-0007, locked
```

**Create Invoice:**
```bash
py-invoices invoices create --client-name "Acme Corp" --amount 1500.00 --description "Web Development" --issue
```

*Create and export files* (`-e`/`--export` takes `pdf`, `html`, `ubl`, `json`, repeated):
```bash
py-invoices invoices create \
  --client-name "Acme Corp" \
  --amount 1500.00 \
  --currency EUR \
  --description "Project X" \
  --invoice-number "0001" \
  --payment-terms "Net 30" \
  --bank-account "IBAN: US123456" \
  -e pdf -e html --output-dir ./Outbox \
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
py-invoices invoices summary   # counts by payment state and totals
py-invoices invoices stats     # the short form
```

**Clone Invoice:**
```bash
py-invoices invoices clone <invoice_number_or_id> --date 2026-10-01 --issue -e pdf
py-invoices invoices clone INV-2026-0003 --unit-price 950 --description "October"   # a draft with a new price
```
Line flags (`--description`, `--quantity`, `--unit-price`/`--amount`) change the copy's only line; for an original with several lines, clone it and use `invoices update <draft> --line N`.

**Generate PDF:**
```bash
py-invoices invoices pdf <invoice_number_or_id> --company-name "My Company" --company-address "123 Business Rd"
```
*Example:*
```bash
py-invoices invoices pdf INV-2024-001 --output-dir ./my-invoices --company-name "Dev Shop" --company-address "1 Main St"
```

**Generate HTML:**
```bash
py-invoices invoices html <invoice_number_or_id> --company-name "My Company" --company-address "123 Business Rd"
```
*Example:*
```bash
py-invoices invoices html INV-2024-001
```

**Exit codes:**

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 2 | Invalid arguments; nothing ran, and `error.errors` lists every problem |
| 4 | A precondition failed: company details, a logo file, or PDF dependencies are missing; the invoice is not a draft (`INVOICE_NOT_DRAFT`); a line flag names no line of the invoice (`LINE_SELECTION`); a due date before the issue date (`error.code` says which) |
| 5 | The invoice or client does not exist |
| 6 | `--invoice-number` is already used |

`py-invoices manifest` lists every invoice command with its flags, output schema, and exit codes as JSON; `py-invoices invoices <command> --schema` shows one.

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

**Create Credit Note** (whole invoice, or only chosen lines with `--line`, 0-based):
```bash
py-invoices credit-notes create "INV-2024-0001" --reason "Refund"
py-invoices credit-notes create "INV-2024-0001" --reason "Partial refund" --line 0
```

Credit notes are numbered in their own `CN-<year>-<nnnn>` series. The total credited can never
exceed the invoice total, and a fully credited invoice becomes `CREDITED`.

**Show Credit Note:**
```bash
py-invoices credit-notes get "CN-2024-0001"
```

## Payment Notes

A payment note's text is never edited, since issued invoices print it. To change bank details, create a new note, make it the default, and retire the old one; each step is audited, and issued invoices keep the notes they were issued with.

```bash
py-invoices payment-notes create --title "Bank" --content "IBAN DE00 ..." --is-default   # replaces the previous default of its company
py-invoices payment-notes set-default 4
py-invoices payment-notes deactivate 3   # refused while 3 is the default
```

## Payments Management

Manage payments.

**List Payments for an invoice:**
```bash
py-invoices payments list "INV-2024-0001"
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

Check that no issued invoice changed since it was issued (exit 1 if one did):
```bash
py-invoices validate data
py-invoices validate data --seal   # once: record hashes for invoices issued before 6.0.0
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
