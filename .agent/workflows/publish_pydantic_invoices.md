---
description: Publish new version of pydantic-invoices
---

1. Define the new version number (e.g. 1.2.0)

2. Update `CHANGELOG.md` with release notes (create if missing)

3. Update version file in `pyproject.toml` (set `version = "X.Y.Z"`)

4. Update version in `pydantic_invoices/__init__.py` (set `__version__ = "X.Y.Z"`)

5. Create a git annotated tag
```bash
git tag -a vX.Y.Z -m "Release version X.Y.Z"
```

6. Publish the package
```bash
uvx publish Romamo pydantic-invoices
```
