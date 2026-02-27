"""File-based storage implementation."""

import json
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

# Try to import pyyaml
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

T = TypeVar("T", bound=BaseModel)


class FileStorage(Generic[T]):
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

        # Initialize or load metadata (for ID tracking)
        self._meta_file = self.entity_dir / "_meta.json"
        self._next_id = 1
        self._load_meta()

    def _load_meta(self) -> None:
        """Load metadata from file."""
        if self._meta_file.exists():
            try:
                with open(self._meta_file) as f:
                    data = json.load(f)
                    self._next_id = data.get("next_id", 1)
            except json.JSONDecodeError:
                pass

    def _save_meta(self) -> None:
        """Save metadata to file."""
        with open(self._meta_file, "w") as f:
            json.dump({"next_id": self._next_id}, f, indent=2)

    def get_next_id(self) -> int:
        """Get next available ID and increment."""
        current_id = self._next_id
        self._next_id += 1
        self._save_meta()
        return current_id

    def _get_file_path(self, entity_id: int, fmt: str | None = None) -> Path:
        """Get file path for an entity ID."""
        fmt = fmt or self.default_format
        return self.entity_dir / f"{entity_id}.{fmt}"

    def _find_entity_file(self, entity_id: int) -> Path | None:
        """Find the file for an entity ID, checking for ID prefix."""
        # 1. Look for exact ID match first (optimization)
        for ext in ["json", "yaml", "yml", "xml", "md"]:
            path = self.entity_dir / f"{entity_id}.{ext}"
            if path.exists():
                return path

        # 2. Look for friendly names: "{id}.anything.{ext}"
        prefix = f"{entity_id}."
        for item in self.entity_dir.iterdir():
            if item.is_file() and item.name.startswith(prefix):
                # Verify it's not just a partial number like "10.json" when looking for "1"
                # checking startswith "1." is sufficient because 10. starts with "10."
                return item

        return None

    def save(self, entity: T, entity_id: int, fmt: str | None = None) -> Path:
        """Save entity to file.

        Args:
            entity: The pydantic model instance
            entity_id: The ID of the entity
            fmt: The format to save as ('json', 'xml', 'md', 'yaml'). Defaults to storage default.
        """
        fmt = fmt or self.default_format

        # Try to find existing file first (handles friendly names and format changes)
        existing_file = self._find_entity_file(entity_id)

        if existing_file:
            path = existing_file
            # If format is explicitly requested and different, we might need to change extension
            # But usually we want to preserve the existing file's format/name
            if fmt:
                # If explicit format requested differs from existing, we swap
                if existing_file.suffix.lstrip(".") != fmt:
                    existing_file.unlink()
                    path = self._get_file_path(entity_id, fmt)
            else:
                # Infer format from existing file
                fmt = existing_file.suffix.lstrip(".")
        else:
            path = self._get_file_path(entity_id, fmt)
        # Exclude none for XML to avoid "None" strings
        exclude_none = fmt == "xml"
        data = entity.model_dump(mode="json", exclude_none=exclude_none)

        if fmt == "json":
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        elif fmt == "md":
            self._save_markdown(path, data)
        elif fmt == "xml":
            self._save_xml(path, data)
        elif fmt in ("yaml", "yml"):
            self._save_yaml(path, data)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

        return path

    def load(self, entity_id: int) -> T | None:
        """Load entity by ID."""
        path = self._find_entity_file(entity_id)
        if not path:
            return None

        fmt = path.suffix.lstrip(".")
        if fmt == "json":
            with open(path) as f:
                data = json.load(f)
        elif fmt == "md":
            data = self._load_markdown(path)
        elif fmt == "xml":
            data = self._load_xml(path)
        elif fmt in ("yaml", "yml"):
            data = self._load_yaml(path)
        else:
            return None

        return self.model_class.model_validate(data)

    def load_all(self) -> list[T]:
        """Load all entities."""
        entities = []
        for path in self.entity_dir.iterdir():
            if path.name.startswith("_") or not path.is_file():
                continue

            # Parse ID from filename: "1.json" -> 1, "1.item.json" -> 1
            entity_id = None

            # Check for simple digit stem ("1")
            if path.stem.isdigit():
                entity_id = int(path.stem)
            else:
                # Check for friendly name pattern "1.something"
                # Note: path.stem for "1.item.json" is "1.item"
                parts = path.name.split(".", 1)
                if len(parts) > 1 and parts[0].isdigit():
                    entity_id = int(parts[0])

            if entity_id is not None:
                entity = self.load(entity_id)
                if entity:
                    entities.append(entity)

        entities.sort(key=lambda x: getattr(x, "id", 0))
        return entities

    def delete(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        path = self._find_entity_file(entity_id)
        if path:
            path.unlink()
            return True
        return False

    def _save_yaml(self, path: Path, data: dict[str, Any]) -> None:
        """Save as YAML."""
        if yaml is None:
            raise ImportError(
                "PyYAML is required for YAML storage. "
                "Install it with: pip install py-invoices[files,yaml]"
            )

        with open(path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load from YAML."""
        if yaml is None:
            # Check if this error context is helpful; we found a .yaml file but can't read it
            raise ImportError(
                f"Found YAML file {path} but PyYAML is not installed. "
                "Install it with: pip install py-invoices[files,yaml]"
            )

        with open(path) as f:
            from typing import cast

            return cast(dict[str, Any], yaml.safe_load(f))

    def _save_markdown(self, path: Path, data: dict[str, Any]) -> None:
        """Save as Markdown with frontmatter."""
        content = "---\n"

        if yaml:
            content += yaml.safe_dump(data, sort_keys=False)
        else:
            # Fallback to JSON-in-YAML if pyyaml is missing
            content += json.dumps(data, indent=2)

        content += "\n---\n"

        with open(path, "w") as f:
            f.write(content)

    def _load_markdown(self, path: Path) -> dict[str, Any]:
        """Load from Markdown frontmatter."""
        with open(path) as f:
            content = f.read()

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                from typing import cast

                if yaml:
                    return cast(dict[str, Any], yaml.safe_load(frontmatter))
                else:
                    # Fallback: try JSON load
                    return cast(dict[str, Any], json.loads(frontmatter))

        raise ValueError(f"Invalid markdown format in {path}")

    def _save_xml(self, path: Path, data: dict[str, Any]) -> None:
        """Save as XML."""
        from xml.dom import minidom  # nosec B408
        from xml.etree.ElementTree import Element, SubElement, tostring  # nosec B405

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

        # It is safe because we generate 'root' from a controlled dictionary in memory
        xml_str = minidom.parseString(tostring(root)).toprettyxml(indent="  ")  # nosec B318

        with open(path, "w") as f:
            f.write(xml_str)

    def _load_xml(self, path: Path) -> dict[str, Any]:
        """Load from XML."""
        import defusedxml.ElementTree as ET  # noqa: N817

        tree = ET.parse(path)
        root = tree.getroot()

        from typing import Any

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

        from typing import cast

        data = cast(dict[str, Any], xml_to_dict(root))

        # Post-process to ensure list fields are lists
        for field_name, field_info in self.model_class.model_fields.items():
            if field_name in data:
                from typing import get_origin

                origin = get_origin(field_info.annotation)
                if origin is list and not isinstance(data[field_name], list):
                    data[field_name] = [data[field_name]]

                elif origin is dict and data[field_name] is None:
                    data[field_name] = {}

        return data
