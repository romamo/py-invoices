"""Storage backends for py-invoices.

Backends are lazy-loaded when RepositoryFactory is initialized.
This allows optional dependencies to work correctly - users only need
to install dependencies for the backends they actually use.
"""

__all__ = ["memory", "sqlite"]
