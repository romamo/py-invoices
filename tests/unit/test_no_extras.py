import pytest
from pathlib import Path
from pydantic import BaseModel
from typing import Optional
from unittest.mock import patch, MagicMock
import sys
import subprocess

from py_invoices.backends.files.storage import FileStorage

class MockModel(BaseModel):
    id: int
    name: str
    data: Optional[dict] = None

@pytest.fixture
def temp_storage(tmp_path):
    return FileStorage(tmp_path, "test_entity", MockModel)

def test_storage_no_pyyaml(temp_storage):
    """Test storage functions work without pyyaml (falling back where appropriate)."""
    # Simulate pyyaml missing
    with patch("py_invoices.backends.files.storage.yaml", None):
        # 1. Test JSON (should always work)
        entity_json = MockModel(id=1, name="test_json", data={"a": 1})
        path_json = temp_storage.save(entity_json, 1, fmt="json")
        loaded_json = temp_storage.load(1)
        assert loaded_json.name == "test_json"
        
        # 2. Test Markdown (should fallback to JSON frontmatter)
        entity_md = MockModel(id=2, name="test_md", data={"b": 2})
        path_md = temp_storage.save(entity_md, 2, fmt="md")
        
        with open(path_md, "r") as f:
            content = f.read()
            # Should NOT look like YAML "key: value"
            # Should look like JSON "{\n"
            assert "{" in content
            
        loaded_md = temp_storage.load(2)
        assert loaded_md.name == "test_md"
        
        # 3. Test YAML explicit (should raise ImportError)
        entity_yaml = MockModel(id=3, name="test_yaml", data={"c": 3})
        with pytest.raises(ImportError) as exc:
            temp_storage.save(entity_yaml, 3, fmt="yaml")
        assert "PyYAML is required" in str(exc.value)

def test_clean_import_no_extras():
    """Test that importing the package doesn't crash if optional deps are missing."""
    
    # We use a subprocess to create a clean-ish environment where we mask modules
    code = """
import sys
import unittest.mock

# Mask optional dependencies
sys.modules['rich'] = None
sys.modules['typer'] = None
sys.modules['weasyprint'] = None
sys.modules['pyyaml'] = None # yaml might be imported as yaml or pyyaml

# Also mask the `yaml` top level package
sys.modules['yaml'] = None

try:
    import py_invoices
    from py_invoices.backends.files import storage
    print("IMPORT_SUCCESS")
except ImportError as e:
    print(f"IMPORT_FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Subprocess failed: {result.stderr}"
    assert "IMPORT_SUCCESS" in result.stdout
