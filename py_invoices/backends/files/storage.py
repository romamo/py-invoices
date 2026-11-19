"""File-based storage implementation."""

import json
import os
import threading
from pathlib import Path
from typing import Any, cast, get_origin

from pydantic import BaseModel
from pydantic_invoices.vo import Money

# Try to import pyyaml
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


SUPPORTED_FORMATS = ("json", "yaml", "yml", "xml", "md")
FRONTMATTER = "---\n"


def _money_aware_dump(entity: BaseModel, data: Any) -> Any:
    """Replace each Money in a JSON dump with {"amount", "currency"}; plain JSON drops currency."""
    if not isinstance(entity, BaseModel) or not isinstance(data, dict):
        return data
    for name in type(entity).model_fields:
        if name not in data:
            continue
        value = getattr(entity, name)
        if isinstance(value, Money):
            data[name] = {"amount": str(value.amount), "currency": value.currency}
        elif isinstance(value, BaseModel):
            data[name] = _money_aware_dump(value, data[name])
        elif isinstance(value, list) and isinstance(data[name], list):
            data[name] = [
                _money_aware_dump(item, dumped)
                for item, dumped in zip(value, data[name], strict=True)
            ]
    return data


def _restore_money(data: Any) -> Any:
    """Inverse of _money_aware_dump; plain amounts from older files stay as they are."""
    if isinstance(data, dict):
        if set(data) == {"amount", "currency"}:
            return Money(data["amount"], data["currency"])
        return {key: _restore_money(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_restore_money(item) for item in data]
    return data


YAML_INSTALL_HINT = "install the yaml extra: pip install 'py-invoices[yaml]'"


class YamlUnavailableError(ImportError):
    """A file needs PyYAML to be read or written, and PyYAML is not installed."""

    def __init__(self, path: Path) -> None:
        self.file = path
        super().__init__(
            f"{path} is stored as YAML, but PyYAML is not installed; {YAML_INSTALL_HINT}"
        )


def _frontmatter(path: Path) -> str:
    """The frontmatter of a Markdown record; text after the closing marker is ignored."""
    content = path.read_text(encoding="utf-8")
    end = content.find(f"\n{FRONTMATTER}", len(FRONTMATTER) - 1)
    if not content.startswith(FRONTMATTER) or end == -1:
        raise ValueError(f"Invalid markdown format in {path}")
    return content[len(FRONTMATTER) : end + 1]


def _is_json_frontmatter(frontmatter: str) -> bool:
    """Frontmatter written as JSON, as a store saves it when PyYAML is missing."""
    return frontmatter.lstrip().startswith("{")


class MisplacedRecordError(ValueError):
    """A file named for one ID holds a record with another ID."""

    def __init__(self, path: Path, record_id: int) -> None:
        self.path = path
        self.record_id = record_id
        super().__init__(
            f"{path} holds the record with id {record_id}, not the id in its file name; "
            "rename the file or fix its id"
        )


def _atomic_write(path: Path, content: str) -> None:
    """Write via a temporary file and rename, so a crash never leaves a truncated file."""
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def _record_id(entity: BaseModel) -> int | None:
    """The ID stored inside a record; None for models without one (or legacy entries)."""
    record_id = getattr(entity, "id", None)
    if record_id is not None and not isinstance(record_id, int):
        raise TypeError(f"Record id must be an int, got {record_id!r}")
    return record_id


class FileStorage[T: BaseModel]:
    """File storage handler for a specific entity type."""

    def __init__(
        self,
        root_dir: str | Path,
        entity_name: str,
        model_class: type[T],
        default_format: str = "json",
    ):
        """Initialize file storage.

        Args:
            root_dir: Root directory for all file storage
            entity_name: Name of the entity (used for subdirectory)
            model_class: Pydantic model class for the entity
            default_format: Default file format for saving ('json', 'xml', 'md', 'yaml')
        """
        self.root_dir = Path(root_dir)
        self.entity_dir = self.root_dir / entity_name
        self.model_class = model_class
        self.default_format = default_format

        # Create directory if it doesn't exist
        self.entity_dir.mkdir(parents=True, exist_ok=True)

        self._meta_file = self.entity_dir / "_meta.json"
        self._next_id = self._load_meta()
        self._id_lock = threading.Lock()

    def _load_meta(self) -> int:
        """Next ID from metadata; a corrupt metadata file is an error, never a reset."""
        if not self._meta_file.exists():
            return 1
        try:
            data = json.loads(self._meta_file.read_text())
            next_id = data["next_id"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(
                f"Corrupt ID metadata in {self._meta_file}; fix or delete it "
                "(IDs then continue after the highest stored entity)"
            ) from e
        if not isinstance(next_id, int) or next_id < 1:
            raise ValueError(f"Invalid next_id {next_id!r} in {self._meta_file}")
        return next_id

    def _save_meta(self) -> None:
        _atomic_write(self._meta_file, json.dumps({"next_id": self._next_id}, indent=2))

    def get_next_id(self) -> int:
        """Get next available ID and increment; never below an ID already on disk.

        Safe across threads of one process; separate processes must not share a directory.
        """
        with self._id_lock:
            highest = max(self._entity_files(), default=0)
            current_id = max(self._next_id, highest + 1)
            self._next_id = current_id + 1
            self._save_meta()
            return current_id

    def _get_file_path(self, entity_id: int, fmt: str | None = None) -> Path:
        """Get file path for an entity ID."""
        fmt = fmt or self.default_format
        return self.entity_dir / f"{entity_id}.{fmt}"

    def _entity_files(self) -> dict[int, Path]:
        """Map entity ID to its file ("1.json" or friendly "1.acme.md")."""
        files: dict[int, Path] = {}
        for path in self.entity_dir.iterdir():
            if path.name.startswith(("_", ".")) or not path.is_file():
                continue
            prefix = path.name.split(".", 1)[0]
            if not prefix.isdigit() or path.suffix.lstrip(".") not in SUPPORTED_FORMATS:
                continue
            entity_id = int(prefix)
            if entity_id in files:
                raise ValueError(
                    f"Two files for ID {entity_id} in {self.entity_dir}: "
                    f"{files[entity_id].name} and {path.name}"
                )
            files[entity_id] = path
        return files

    def _find_entity_file(self, entity_id: int) -> Path | None:
        """Find the file for an entity ID, including friendly names."""
        return self._entity_files().get(entity_id)

    def save(self, entity: T, entity_id: int, fmt: str | None = None) -> Path:
        """Save entity to file.

        An existing file keeps its name and format unless `fmt` is given explicitly,
        in which case it is rewritten in that format.

        Args:
            entity: The pydantic model instance
            entity_id: The ID of the entity
            fmt: The format to save as ('json', 'xml', 'md', 'yaml'). Defaults to the
                existing file's format, then to the storage default.
        """
        existing_file = self._find_entity_file(entity_id)
        if existing_file and (fmt is None or existing_file.suffix.lstrip(".") == fmt):
            path = existing_file
        else:
            path = self._get_file_path(entity_id, fmt)
        fmt = path.suffix.lstrip(".")
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {fmt}")

        # Exclude none for XML to avoid "None" strings
        data = _money_aware_dump(entity, entity.model_dump(mode="json", exclude_none=fmt == "xml"))
        if fmt == "json":
            _atomic_write(path, json.dumps(data, indent=2))
        elif fmt == "md":
            self._save_markdown(path, data)
        elif fmt == "xml":
            self._save_xml(path, data)
        else:
            self._save_yaml(path, data)

        if existing_file and existing_file != path:
            existing_file.unlink()
        return path

    def load(self, entity_id: int) -> T | None:
        """Load entity by ID.

        Raises:
            MisplacedRecordError: If the file for this ID holds a record with another ID;
                writing it back would overwrite that other record
        """
        path = self._find_entity_file(entity_id)
        if path is None:
            return None
        entity = self._load_path(path)
        record_id = _record_id(entity)
        if record_id is not None and record_id != entity_id:
            raise MisplacedRecordError(path, record_id)
        return entity

    def misplaced(self) -> list[tuple[Path, int]]:
        """Files whose record ID differs from the ID in the file name, with that record ID.

        Listing returns such a record under its own ID, but loading or updating it by
        that ID looks for the file named for it, so the store is inconsistent.
        """
        found = []
        for file_id, path in sorted(self._entity_files().items()):
            record_id = _record_id(self._load_path(path))
            if record_id is not None and record_id != file_id:
                found.append((path, record_id))
        return found

    def _load_path(self, path: Path) -> T:
        fmt = path.suffix.lstrip(".")
        if fmt == "json":
            data = json.loads(path.read_text())
        elif fmt == "md":
            data = self._load_markdown(path)
        elif fmt == "xml":
            data = self._load_xml(path)
        else:
            data = self._load_yaml(path)
        return self.model_class.model_validate(_restore_money(data))

    def load_all(self) -> list[T]:
        """Load all entities, ordered by ID."""
        return [self._load_path(path) for _, path in sorted(self._entity_files().items())]

    def delete(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        path = self._find_entity_file(entity_id)
        if path:
            path.unlink()
            return True
        return False

    def delete_all(self) -> None:
        """Delete every entity file and restart IDs at 1."""
        for path in self._entity_files().values():
            path.unlink()
        self._next_id = 1
        self._save_meta()

    def yaml_needed(self) -> Path | None:
        """The first file that cannot be read because PyYAML is missing; None when none.

        A `.yaml`/`.yml` file needs it, and so does Markdown whose frontmatter is not JSON.
        """
        if yaml is not None:
            return None
        for _, path in sorted(self._entity_files().items()):
            fmt = path.suffix.lstrip(".")
            if fmt in ("yaml", "yml"):
                return path
            if fmt == "md" and not _is_json_frontmatter(_frontmatter(path)):
                return path
        return None

    def _save_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """Save as YAML."""
        if yaml is None:
            raise YamlUnavailableError(path)

        _atomic_write(path, yaml.safe_dump(data, sort_keys=False))

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load from YAML."""
        if yaml is None:
            raise YamlUnavailableError(path)

        return cast(dict[str, Any], yaml.safe_load(path.read_text(encoding="utf-8")))

    def _save_markdown(self, path: Path, data: dict[str, Any]) -> None:
        """Save as Markdown with frontmatter (YAML, or JSON when PyYAML is missing)."""
        body = yaml.safe_dump(data, sort_keys=False) if yaml else json.dumps(data, indent=2)
        _atomic_write(path, f"{FRONTMATTER}{body.rstrip()}\n{FRONTMATTER}")

    def _load_markdown(self, path: Path) -> dict[str, Any]:
        """Load from Markdown frontmatter: YAML, or JSON as saved without PyYAML."""
        frontmatter = _frontmatter(path)
        if yaml is not None:
            data = yaml.safe_load(frontmatter)
        elif _is_json_frontmatter(frontmatter):
            data = json.loads(frontmatter)
        else:
            raise YamlUnavailableError(path)
        if not isinstance(data, dict):
            raise ValueError(f"Frontmatter in {path} is not a mapping")
        return data

    def _save_xml(self, path: Path, data: dict[str, Any]) -> None:
        """Save as XML."""
        # Only builds XML from our own data; parsing goes through defusedxml
        from xml.etree.ElementTree import Element, SubElement, indent, tostring  # nosec B405

        def dict_to_xml(parent: Element, d: dict[str, Any]) -> None:
            for key, value in d.items():
                if isinstance(value, dict):
                    child = SubElement(parent, key)
                    dict_to_xml(child, value)
                elif isinstance(value, list):
                    for item in value:
                        child = SubElement(parent, key)
                        if isinstance(item, dict):
                            dict_to_xml(child, item)
                        else:
                            child.text = str(item)
                else:
                    child = SubElement(parent, key)
                    child.text = str(value)

        root = Element(self.model_class.__name__)
        dict_to_xml(root, data)

        indent(root, space="  ")
        xml_str = tostring(root, encoding="unicode", xml_declaration=True) + "\n"

        _atomic_write(path, xml_str)

    def _load_xml(self, path: Path) -> dict[str, Any]:
        """Load from XML."""
        import defusedxml.ElementTree as ET  # noqa: N817

        tree = ET.parse(path)
        root = tree.getroot()

        def xml_to_dict(element: Any) -> Any:
            result: dict[str, Any] = {}
            for child in element:
                val = xml_to_dict(child) if len(child) > 0 else child.text
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(val)
                else:
                    result[child.tag] = val
            return result

        data = cast(dict[str, Any], xml_to_dict(root))

        # Post-process to ensure list fields are lists
        for field_name, field_info in self.model_class.model_fields.items():
            if field_name in data:
                origin = get_origin(field_info.annotation)
                if origin is list and not isinstance(data[field_name], list):
                    data[field_name] = [data[field_name]]

                elif origin is dict and data[field_name] is None:
                    data[field_name] = {}

        return data
