---
description: Release new version of a library
---

1. Ensure working directory is clean
```bash
if [[ -n $(git status --porcelain) ]]; then
  echo "Error: Uncommitted changes detected:"
  git status --short
  echo "Please commit your changes before releasing."
  exit 1
fi
```

2. Review changes since the latest release
```bash
git log $(git describe --tags --abbrev=0)..HEAD --oneline
```

3. Write changes to changelog file (`CHANGELOG.md`)

4. Identify major, minor, or patch changes
   - Major: Breaking changes
   - Minor: New features (backward compatible)
   - Patch: Bug fixes (backward compatible)

5. Confirm and commit changes
```bash
git diff
read -p "Do you want to commit these changes? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git add CHANGELOG.md
    git commit -m "Update changelog"
else
    echo "Changes not committed. Exiting."
    exit 1
fi
```

6. Bump version
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

7. Verify strict version match
   ```bash
   uv run pytest tests/test_version.py
   ```

8. Tag using git
   - Replace `v0.1.0` with the actual new version:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   ```

9. Push tags
```bash
git push --tags
```

10. Create GitHub Release
```bash
gh release create <tag_name> --generate-notes
```

