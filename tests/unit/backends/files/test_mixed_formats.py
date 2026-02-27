"""Tests for mixed format support in FileStorage."""

import json

import pytest
from pydantic import BaseModel

from py_invoices.backends.files.storage import FileStorage


class ItemModel(BaseModel):
    name: str
    value: int


@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / "data"


def test_mixed_formats_reading(storage_dir) -> None:
    """Test that storage can read any format regardless of default_format setting."""
    # Initialize with default_format="md"
    storage = FileStorage[ItemModel](storage_dir, "items", ItemModel, default_format="md")

    # Manually create files in different formats
    # 1. JSON
    json_file = storage_dir / "items" / "1.json"
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w") as f:
        json.dump({"name": "item_json", "value": 1}, f)

    # 2. XML
    # Simple XML structure manually
    xml_content = "<ItemModel><name>item_xml</name><value>2</value></ItemModel>"
    xml_file = storage_dir / "items" / "2.xml"
    with open(xml_file, "w") as f:
        f.write(xml_content)

    # 3. MD (created via storage save to ensure correct format, but verified as md)
    item_md = ItemModel(name="item_md", value=3)
    path_md = storage.save(item_md, 3)  # Should be .md by default
    assert path_md.suffix == ".md"

    # Test loading specific IDs
    loaded_json = storage.load(1)
    assert loaded_json is not None
    assert loaded_json.name == "item_json"
    assert "json" in str(storage._find_entity_file(1))

    loaded_xml = storage.load(2)
    assert loaded_xml is not None
    assert loaded_xml.name == "item_xml"

    loaded_md = storage.load(3)
    assert loaded_md is not None
    assert loaded_md.name == "item_md"

    # Test load_all
    all_items = storage.load_all()
    assert len(all_items) == 3
    names = {i.name for i in all_items}
    assert names == {"item_json", "item_xml", "item_md"}


def test_default_writing_format(storage_dir) -> None:
    """Test that file_format setting strictly controls writing format."""

    # Case 1: Default MD
    storage_md = FileStorage[ItemModel](storage_dir, "items_md", ItemModel, default_format="md")
    path1 = storage_md.save(ItemModel(name="test", value=1), 1)
    assert path1.suffix == ".md"

    # Case 2: Default JSON
    storage_json = FileStorage[ItemModel](
        storage_dir, "items_json", ItemModel, default_format="json"
    )
    path2 = storage_json.save(ItemModel(name="test", value=1), 1)
    assert path2.suffix == ".json"

    # Case 3: Override
    path3 = storage_md.save(ItemModel(name="test", value=2), 2, fmt="xml")
    assert path3.suffix == ".xml"
