# Changelog

All notable changes to this project will be documented in this file.

## [2.0.1] - 2026-09-28

### Fixed
- **PDF system libraries**: when WeasyPrint is installed but cannot load Pango or GObject, the CLI and API (501) now name the missing library and give fix steps for the platform instead of suggesting `pip install`. On macOS, Homebrew libraries that are installed but not on the loader path are detected and the matching `export DYLD_FALLBACK_LIBRARY_PATH=...` is shown; Linux gets the apt packages to install
- **Install hint**: the CLI tip for a missing extra printed `pip install 'py-invoices'` because Rich read `[pdf]` as markup; it now shows `pip install 'py-invoices[pdf]'`

### Removed
- `CompanyNotFoundError` from `py_invoices.operations.errors`; company resolution no longer raises it

## [2.0.0] - 2026-09-28

Breaking: the HTTP API requires `INVOICES_API_KEY`, SQL databases from 1.x need the migration below, `credit-notes create --full-refund` is replaced by `--line`, and payment terms without a derivable due date need `--due-date`.

### Security
- **Template escaping**: HTML and UBL templates were rendered without autoescaping (`*.html.j2` / `*.xml.j2` did not match `select_autoescape`). Client names, addresses and line descriptions are now escaped; the `| safe` newline hack is replaced by an escaping `nl2br` filter.
- **API authentication**: every API route now requires the `X-API-Key` header matching `INVOICES_API_KEY`; without a configured key the API answers 503. CORS no longer allows every origin with credentials; extra origins come from `INVOICES_CORS_ORIGINS`.
- **Web app**: invoice fields are inserted as text, not HTML.
- **UBL upload**: validation reads uploads in memory with a 5 MB limit instead of via a temp file.

### Fixed
- **Invoice numbering**: the next number continues from the highest number issued in the same series and year, instead of "invoice count + 1" (which reused numbers after deletions, never reset yearly, and was shifted by credit notes).
- **Credit notes**: own `CN-<year>-<nnnn>` series; cannot exceed the tax-inclusive amount left to credit; cannot credit a credit note, draft, cancelled, refunded or already credited invoice; a line can be credited only once; a refused credit leaves nothing stored; `POST /invoices` no longer accepts credit notes (use `POST /credit-notes`); invalid or duplicate line indices are errors; crediting an overdue invoice no longer fails on its past due date; a fully credited invoice becomes `CREDITED`; UBL output uses the UBL `CreditNote` document (type 381) with a billing reference.
- **Summaries**: one calculation for all backends, in tax-inclusive amounts (what the documents show). Credit notes reduce `total_amount`, drafts and cancelled invoices are excluded, and `total_due` counts only open invoices after payments and credits. Memory and files backends now include recorded payments. Invoices in several currencies raise `MixedCurrencyError` (API 409, CLI error) instead of crashing.
- **Currencies**: memory and files backends kept only the amount of money values and silently turned every currency into USD. Money is now stored with its currency; files written by earlier versions still load (as USD).
- **Concurrency**: memory and files backends hand out IDs under a lock, so parallel API requests no longer overwrite each other's records. The memory payment-note repository reused IDs after a deletion.
- **Document numbers** become file names, so numbers with `/`, `\` or a leading `.` are rejected (they could write outside the output directory).
- **SQL backends**: money is stored as exact `NUMERIC` with its currency (was `float`); line `tax_rate`, `payment_note_ids` and currency were silently dropped and are now stored; `issue_date` is a date. Each API request gets its own session; `cleanup()` disposes the engine; list queries are ordered by ID so paging is stable. Opening a database whose tables lack new columns (or, outside SQLite, still use float money or datetime dates) fails with a clear error instead of breaking later. Audit entries are returned oldest first like the other backends.
- **Files backend**: a corrupt `_meta.json` is an error instead of silently resetting IDs (which overwrote entity 1); new IDs never collide with files on disk; writes are atomic; updating a record keeps its file name and format; Markdown values may contain `---`; two files for one ID are reported.
- **API**: one factory per process (the memory backend lost all data between requests, and SQL settings like `database_url` were ignored); `offset` works for invoices, clients and products; creating an invoice with a used number returns 409 and is audited; HTML/PDF use the same company, template, logo and payment-note resolution as the CLI; `Content-Disposition` is RFC 5987 encoded; the API reports the package version.
- **Invoice CLI**: `--payment-terms "Net N"` sets the due date (unparseable terms need `--due-date`); `clone` keeps the original payment period and company snapshots; `create` snapshots the default company; `--format` values, company details, logo and PDF support are checked before anything is created; missing PDF dependencies exit with code 1; the client or preferred template is used for exported files; a number that looks like an ID is looked up as a number first; a missing logo file is an error instead of a broken image.
- **Amounts**: `--amount` is parsed as an exact decimal and `--currency` sets its currency; displays use the invoice currency instead of a hard-coded `$`; HTML and UBL show per-rate tax and the tax-inclusive total (UBL line amounts and totals were empty or 0); line amounts are rounded before summing (EN16931 BR-CO-10). Factur-X PDFs of credit notes embed a CreditNote XML.
- **Audit**: entries are typed `AuditLogEntry` in every backend; `get_logs` applies all filters and reads beyond the first 100 entries; `get_summary` reads the repository; invoice and credit-note creation are logged.
- **Backends loading**: only the requested backend is imported; a missing driver reports the extra to install instead of "Unknown backend".
- **Examples** run again with current `pydantic-invoices` (tax IDs are value objects).

### Changed
- `credit-notes create --full-refund` (never used) is replaced by `--line INDEX` for partial credits.
- `CreditService(invoice_repo)` no longer needs a numbering service; pass one only to change the series.
- `HTMLService` creates the output directory on first save, not on construction.
- Plugins declare `name` (and SQL plugins `default_url`) as class attributes.
- `python-multipart` is only a dependency of the `api` extra; `all` now includes `yaml`.
- Ruff also checks bugbear, blind-except, simplify, ruff and bandit rules.

### Migration (SQL databases created by earlier versions)
`create_all` never alters existing tables, so add the new columns once. SQLite:

```sql
ALTER TABLE invoice_lines ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'USD';
ALTER TABLE invoice_lines ADD COLUMN tax_rate NUMERIC(5, 2) NOT NULL DEFAULT 0;
ALTER TABLE payments ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'USD';
ALTER TABLE invoices ADD COLUMN payment_note_ids JSON;
UPDATE invoices SET issue_date = substr(issue_date, 1, 10);
```

SQLite keeps the old column types, so amounts already stored as `REAL` stay binary floats; recreate the tables (export and re-import) for exact storage of existing rows.

PostgreSQL/MySQL: add the same columns and convert `issue_date` to `DATE` and the `unit_price`/`amount` columns to `NUMERIC(18, 4)`; the schema check refuses the old types.

## [1.11.0] - 2026-03-27

### Added
- **Dynamic Invoice Logos**: Support for resolving and embedding company logos as Base64 Data URIs in HTML and PDF invoices. Logos can be provided via CLI options or resolved from company records and invoice snapshots.
- **Image Utility**: New utility for converting image files to Base64 data URIs.

### Changed
- **Service Refactoring**: `HTMLService` and `PDFService` no longer take `logo_path` as a direct argument; logos are now passed via the rendering context.
- **Default Template**: Updated `invoice.html.j2` to display the company logo if provided.

## [1.10.0] - 2026-03-26

### Added
- **CLI Company Resolution**: Enhanced `pdf`, `html`, and `create` commands to automatically resolve company details (name, address, tax ID, email) from CLI options, invoice snapshots, or live lookup via `company_id`.
- **Company Snapshots**: Added `company_name_snapshot`, `company_address_snapshot`, and `company_tax_id_snapshot` to the `SQLModel` backend to ensure historical data integrity for company information.

### Fixed
- **CLI VAT Resolution**: Automatically fetch and resolve company tax ID from the repository if missing from CLI arguments or invoice snapshots.
- **CLI Optional Arguments**: Changed `--company-name` and `--company-address` from required to optional in `pdf` and `html` commands when resolution is possible.

## [1.9.1] - 2026-03-02

### Fixed
- **Tax ID Handling**: Coerce `tax_id` to `str` in CLI display (`clients list`, `clients search`, `companies list`) and in memory client search to support `TaxID` value objects.
- **Date/Datetime Compatibility**: Fixed `MemoryPaymentRepository.get_by_date_range` to handle mixed `date`/`datetime` comparisons without errors.
- **Invoice Dates**: Use `date` (not `datetime`) when creating and cloning invoices to align with schema expectations.
- **CLI Error Handling**: Replace silent `pass` with `raise typer.Exit(code=1)` when required company args are missing during invoice create/clone.
- **CLI Detail Display**: Use `client.preferred_template` attribute directly instead of `getattr` fallback.
- **Code Quality**: Remove swallowed `ImportError` in `RepositoryFactory` for always-available backends (memory, files); fail fast on import errors.
- **Typing**: Add `type: ignore[import-untyped]` for `weasyprint` import in `PDFService` to fix strict Mypy runs.

### Changed
- **Dependencies**: Bumped minimum versions — `pydantic-invoices>=1.4.1`, `pydantic>=2.10.0`, `sqlmodel>=0.0.37`, `fastapi>=0.135.1`, `uvicorn>=0.41.0`, `ruff>=0.15.4`. Added `python-multipart` to the `api` extra.

## [1.8.4] - 2026-02-27

### Fixed
- **Packaging**: Excluded internal development materials (`uv.lock`, `.agent`, `.github`) from source distributions.
- **Dependencies**: Removed local path overrides for `pydantic-invoices` to ensure proper PyPI resolution.

## [1.8.3] - 2026-02-27

### Fixed
- **Code Quality**: Extensive refactoring for enhanced code safety, including replacing broad exceptions with fail-fast mechanisms.
- **Security**: Introduced `defusedxml` for secure XML parsing.
- **Typing & Abstractions**: Strict Mypy compliance and abstract methods cleanup.

## [1.8.2] - 2026-01-25
 
### Fixed
- **CLI Invoices**: Fixed `AttributeError` in `invoices details` command where `line_total` was accessed instead of `total`.
- **Regression Tests**: Added CLI regression tests for invoice details.


## [1.8.1] - 2026-01-06

### Fixed
- **CLI Configuration**: Fixed an issue where CLI commands ignored `file_format` and `storage_path` settings.

## [1.8.0] - 2026-01-06

### Added
- **Setup Output Dir**: Added `--output-dir` argument to the `setup` command to configure the default output directory.

## [1.7.0] - 2026-01-05

### Added
- **Setup Wizard**: Added `setup` command to interactively configure the application and backend.
- **Auto-Install**: The `setup` command automatically installs missing dependencies (like `python-dotenv` or database drivers) using `uv` or `pip`.
- **Dotenv Support**: Optional `.env` file loading via `[dotenv]` extra.

## [1.6.0] - 2026-01-05

### Added
- **Config Command**: Added `config` command to CLI to show current configuration details (`py-invoices config show`).

## [1.5.0] - 2026-01-05

### Added
- **CLI Creation Commands**: Added `create` command for:
    - Companies (`py-invoices companies create`)
    - Products (`py-invoices products create`)
    - Payment Notes (`py-invoices payment-notes create`)

## [1.4.1] - 2026-01-04

### Documentation
- Updated `README.md` to include information about friendly filename support in the Files backend.
- Updated release workflow to include documentation update steps.

## [1.4.0] - 2026-01-04

### Added
- **Friendly Filenames**: Added support for reading entity files with friendly filenames (e.g., `1.Customer Name.json`) in the files backend.

## [1.3.1] - 2026-01-04

### Documentation
- Updated `README.md` with YAML storage details.
- Updated `py_invoices/cli/README.md` with all available CLI commands (stats, clone, details, etc.) and entity management sections.

## [1.3.0] - 2026-01-04

### Added
- **YAML Storage**: Added YAML support to the files backend.
- **CLI Enhancements**: Migrated `stats` and `clone-invoice` commands to the main CLI.
- **Testing**: Added unit tests for YAML storage and no-extras scenarios.

### Removed
- **Legacy Data**: Cleaned up unused data files from project root.

## [1.2.1] - 2026-01-03

### Added
- **Release Workflow**: Added GitHub release workflow.

## [1.2.0] - 2026-01-03

### Added
- **Files Backend**: New storage mechanism using local files (JSON/Markdown) for invoices, clients, etc.
- **Extended API**: Added endpoints for products, companies, credit notes, payment notes, and payments.
- **Extended CLI**: New commands for managing all entities (products, companies, etc.).
- **Validation**: Integrated `UBLValidator` for compliance checking via CLI and API.

### Fixed
- **Integration Tests**: Fixed state isolation issues in API integration tests.

## [1.1.0] - 2026-01-02

### Added
- **Credit Notes Support**: Use `CreditService` to create Credit Notes linked to original invoices.
- **Strict State Machine**: Invoices now follow a strict lifecycle (`DRAFT` -> `SENT` -> `PAID`/`CANCELLED`).
    - `SENT` and `PAID` invoices are immutable to ensure data integrity.
- **New Statuses**: Support for `DRAFT`, `SENT`, `REFUNDED`, `CREDITED` statuses.
- **Validation**: `BusinessValidator` enforces state transitions and modification rules.

### Changed
- CLI structure improved (internal).
- Dependency updates (`pydantic-invoices` -> 1.2.2).
