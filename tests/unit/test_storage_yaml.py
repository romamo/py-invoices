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
