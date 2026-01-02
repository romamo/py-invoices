# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-01-02

### Added
- **Credit Notes Support**: Use `CreditService` to create Credit Notes linked to original invoices.
- **Strict State Machine**: Invoices now follow a strict lifecycle (`DRAFT` -> `SENT` -> `PAID`/`CANCELLED`).
    - `SENT` and `PAID` invoices are immutable to ensure data integrity.
- **New Statuses**: Support for `DRAFT`, `SENT`, `REFUNDED`, `CREDITED` statuses.
- **Validation**: `BusinessValidator` enforces state transitions and modification rules.

### Changed
- CLI structure improved (internal).
- Dependency updates (`pydantic-invoices` -> 1.2.0).
