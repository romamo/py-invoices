from pathlib import Path
import re
import sys
import pytest

# Use tomli for Python < 3.11
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

def test_version_consistency():
    # Paths
    root_dir = Path(__file__).parents[1]
    pyproject_path = root_dir / "pyproject.toml"
    init_path = root_dir / "py_invoices" / "__init__.py"
    lock_path = root_dir / "uv.lock"

    # 1. Get version from pyproject.toml
    with open(pyproject_path, "rb") as f:
        pyproject_data = tomllib.load(f)
        pyproject_version = pyproject_data["project"]["version"]

    # 2. Get version from __init__.py
    with open(init_path, "r") as f:
        init_content = f.read()
        match = re.search(r'__version__\s*=\s*"([^"]+)"', init_content)
        if not match:
            pytest.fail("Could not find __version__ in __init__.py")
        init_version = match.group(1)

    # 3. Get version from uv.lock
    with open(lock_path, "rb") as f:
        lock_data = tomllib.load(f)
        
    lock_version = None
    # uv.lock 'package' matches are a list of dicts
    for package in lock_data.get("package", []):
        if package.get("name") == "py-invoices":
            lock_version = package.get("version")
            break
            
    if not lock_version:
        pytest.fail("Could not find py-invoices version in uv.lock")

    # Assertions
    assert pyproject_version == init_version, \
        f"pyproject.toml version ({pyproject_version}) does not match __init__.py version ({init_version})"
        
    assert pyproject_version == lock_version, \
        f"pyproject.toml version ({pyproject_version}) does not match uv.lock version ({lock_version})"
