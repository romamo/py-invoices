# Changelog

All notable changes to this project will be documented in this file.
 
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
