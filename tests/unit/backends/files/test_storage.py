"""Tests for FileStorage."""

from typing import Any

import pytest
from pydantic import BaseModel

from py_invoices.backends.files.storage import FileStorage


class ItemModel(BaseModel):
    name: str
    value: int
    tags: list[str] = []
    meta: dict[str, Any] = {}

    # Optional field to test None exclusion
    description: str | None = None


@pytest.fixture
def storage_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def storage(storage_dir):
    return FileStorage[ItemModel](storage_dir, "items", ItemModel)


def test_storage_initialization(storage_dir) -> None:
    FileStorage(storage_dir, "items", ItemModel)
    assert (storage_dir / "items").exists()
    # _meta.json is created lazily on first ID generation
    assert not (storage_dir / "items" / "_meta.json").exists()


def test_save_load_json(storage) -> None:
    item = ItemModel(name="test", value=123)
    item_id = storage.get_next_id()

    path = storage.save(item, item_id, fmt="json")
    assert path.exists()
    assert path.suffix == ".json"

    loaded = storage.load(item_id)
    assert loaded.name == item.name
    assert loaded.value == item.value


def test_save_load_xml(storage) -> None:
    item = ItemModel(name="test_xml", value=456, tags=["a", "b"])
    item_id = storage.get_next_id()

    path = storage.save(item, item_id, fmt="xml")
    assert path.exists()
    assert path.suffix == ".xml"

    loaded = storage.load(item_id)
    assert loaded.name == item.name
    assert loaded.value == item.value
    assert loaded.tags == ["a", "b"]


def test_save_load_md(storage) -> None:
    item = ItemModel(name="test_md", value=789)
    item_id = storage.get_next_id()

    path = storage.save(item, item_id, fmt="md")
    assert path.exists()
    assert path.suffix == ".md"

    loaded = storage.load(item_id)
    assert loaded.name == item.name
    assert loaded.value == item.value


def test_delete(storage) -> None:
    item = ItemModel(name="delete_me", value=0)
    item_id = storage.get_next_id()
    storage.save(item, item_id)

    assert storage.load(item_id) is not None
    assert storage.delete(item_id) is True
    assert storage.load(item_id) is None
    assert storage.delete(item_id) is False


def test_load_all(storage) -> None:
    items = [
        ItemModel(name="item1", value=1),
        ItemModel(name="item2", value=2),
        ItemModel(name="item3", value=3),
    ]

    for item in items:
        storage.save(item, storage.get_next_id())

    loaded = storage.load_all()
    assert len(loaded) == 3
    assert sorted([i.value for i in loaded]) == [1, 2, 3]


def test_xml_list_handling(storage) -> None:
    # Test single item list
    item1 = ItemModel(name="single", value=1, tags=["one"])
    id1 = storage.get_next_id()
    storage.save(item1, id1, fmt="xml")

    loaded1 = storage.load(id1)
    assert isinstance(loaded1.tags, list)
    assert loaded1.tags == ["one"]

    # Test multi item list
    item2 = ItemModel(name="multi", value=2, tags=["one", "two"])
    id2 = storage.get_next_id()
    storage.save(item2, id2, fmt="xml")

    loaded2 = storage.load(id2)
    assert isinstance(loaded2.tags, list)
    assert loaded2.tags == ["one", "two"]


def test_xml_none_value(storage) -> None:
    # Test None value exclusion in XML
    item = ItemModel(name="none_test", value=1, description=None)
    item_id = storage.get_next_id()

    path = storage.save(item, item_id, fmt="xml")

    # Verify file content doesn't contain Description with "None" string
    with open(path) as f:
        content = f.read()
        assert "None" not in content

    loaded = storage.load(item_id)
    assert loaded.description is None
