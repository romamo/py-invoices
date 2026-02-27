from unittest.mock import patch

import pytest
from pydantic import BaseModel

from py_invoices.backends.files.storage import FileStorage


class MockModel(BaseModel):
    id: int
    name: str
    data: dict | None = None


@pytest.fixture
def temp_storage(tmp_path):
    return FileStorage(tmp_path, "test_entity", MockModel)


def test_save_load_yaml_success(temp_storage, tmp_path) -> None:
    """Test saving and loading YAML when pyyaml is available."""
    import importlib.util
    if importlib.util.find_spec("yaml") is None:
        pytest.skip("pyyaml not installed")

    entity = MockModel(id=1, name="yaml_test", data={"k": "v"})

    # Save as YAML
    path = temp_storage.save(entity, 1, fmt="yaml")
    assert path.suffix == ".yaml"
    assert path.exists()

    # Check content
    with open(path) as f:
        content = f.read()
        assert "name: yaml_test" in content

    # Load
    loaded = temp_storage.load(1)
    assert loaded.name == entity.name
    assert loaded.data == entity.data


def test_missing_pyyaml_error(temp_storage) -> None:
    """Test error when pyyaml is missing on explicit yaml request."""
    with patch("py_invoices.backends.files.storage.yaml", None):
        entity = MockModel(id=2, name="no_yaml", data={})

        # Expect error on save
        with pytest.raises(ImportError) as exc:
            temp_storage.save(entity, 2, fmt="yaml")
        assert "PyYAML is required" in str(exc.value)


def test_load_yaml_missing_lib_error(temp_storage, tmp_path) -> None:
    """Test error when loading existing yaml file but lib is missing."""
    # Create a dummy yaml file manually
    yaml_path = temp_storage.entity_dir / "3.yaml"
    with open(yaml_path, "w") as f:
        f.write("id: 3\nname: manual_yaml\n")

    with patch("py_invoices.backends.files.storage.yaml", None):
        with pytest.raises(ImportError) as exc:
            temp_storage.load(3)
        assert "Found YAML file" in str(exc.value)


def test_markdown_yaml_integration(temp_storage) -> None:
    """Test Markdown using YAML frontmatter if available."""
    import importlib.util
    if importlib.util.find_spec("yaml") is None:
        pytest.skip("pyyaml not installed")

    entity = MockModel(id=4, name="md_yaml", data={"foo": "bar"})
    path = temp_storage.save(entity, 4, fmt="md")

    with open(path) as f:
        content = f.read()

    # Should use clean yaml style "foo: bar" instead of JSON '{"foo": "bar"}'
    assert "foo: bar" in content
    assert "{" not in content  # Heuristic check for YAML vs JSON


def test_markdown_fallback_json(temp_storage) -> None:
    """Test Markdown falls back to JSON-in-YAML if pyyaml is missing."""
    with patch("py_invoices.backends.files.storage.yaml", None):
        entity = MockModel(id=5, name="md_json", data={"foo": "bar"})
        path = temp_storage.save(entity, 5, fmt="md")

        with open(path) as f:
            content = f.read()

        # Should look like JSON
        assert '{\n  "id": 5' in content or '{\n  "id": 5,' in content  # JSON structure check

        # Load check
        loaded = temp_storage.load(5)
        assert loaded.name == "md_json"
