---
description: Release new version of a library
---

1. Review changes since the latest release
```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

2. Write changes to changelog file (`CHANGELOG.md`)

3. Identify major, minor, or patch changes
   - Major: Breaking changes
   - Minor: New features (backward compatible)
   - Patch: Bug fixes (backward compatible)

4. Bump version
   - For major version:
   ```bash
   uv version --bump major
   ```
   - For minor version:
   ```bash
   uv version --bump minor
   ```
   - For patch version:
   ```bash
   uv version --bump patch
   ```

5. Validate that `__version__` matches `pyproject.toml`
   - Check `py_invoices/__init__.py` or related init file.

6. Tag using git
   - Replace `v0.1.0` with the actual new version:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   ```

7. Push tags
```bash
git push --tags
```
