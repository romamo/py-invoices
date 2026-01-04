# Changelog

All notable changes to this project will be documented in this file.

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
