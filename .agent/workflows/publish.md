---
description: Bump version and publish to PyPI
---

1. Run tests to ensure stability and version sync
// turbo
```bash
uv run pytest
```

2. Update `CHANGELOG.md` with release notes (create if missing)

3. Update `version` in `pyproject.toml`
4. Update `__version__` in `py_invoices/__init__.py`

5. Verify strict version match
// turbo
```bash
uv run pytest tests/unit/test_version.py
```

6. Build the package
// turbo
```bash
rm -rf dist && uv build
```

7. Publish to PyPI (requires manual credential entry)
```bash
uv publish --username __token__
```
