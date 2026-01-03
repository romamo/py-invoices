"""File-based storage implementation."""

import json
import os
from pathlib import Path
from typing import Any, Generic, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class FileStorage(Generic[T]):
    """File storage handler for a specific entity type."""

    def __init__(
        self, 
        root_dir: str | Path, 
        entity_name: str, 
        model_class: Type[T],
        default_format: str = "json"
    ):
        """Initialize file storage.
        
        Args:
            root_dir: Root directory for all file storage
            entity_name: Name of the entity (used for subdirectory)
            model_class: Pydantic model class for the entity
            default_format: Default file format for saving ('json', 'xml', 'md')
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
                with open(self._meta_file, "r") as f:
                    data = json.load(f)
                    self._next_id = data.get("next_id", 1)
            except json.JSONDecodeError:
                # If corrupt, we might need recovery, but for now reset or fail? 
                # Choosing to ignore and rely on manual fix or existing max ID scanning 
                # could be safer, but let's stick to simple persistence for now.
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
        # Check existing files to maintain format if possible, or just default to requested
        # For retrieval we need to check all supported extensions
        return self.entity_dir / f"{entity_id}.{fmt}"
        
    def _find_entity_file(self, entity_id: int) -> Path | None:
        """Find the file for an entity ID, checking all supported formats."""
        for ext in ["json", "xml", "md"]:
            path = self.entity_dir / f"{entity_id}.{ext}"
            if path.exists():
                return path
        return None

    def save(self, entity: T, entity_id: int, fmt: str | None = None) -> Path:
        """Save entity to file.
        
        Args:
            entity: The pydantic model instance
            entity_id: The ID of the entity
            fmt: The format to save as ('json', 'xml', 'md'). Defaults to storage default.
        """
        fmt = fmt or self.default_format

        # Remove any existing file for this ID in other formats to avoid duplicates
        existing_file = self._find_entity_file(entity_id)
        if existing_file and existing_file.suffix.lstrip(".") != fmt:
            existing_file.unlink()

        path = self._get_file_path(entity_id, fmt)
        # Exclude none for XML to avoid "None" strings
        exclude_none = (fmt == "xml")
        data = entity.model_dump(mode="json", exclude_none=exclude_none)

        if fmt == "json":
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        elif fmt == "md":
            self._save_markdown(path, data)
        elif fmt == "xml":
            self._save_xml(path, data)
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
            with open(path, "r") as f:
                data = json.load(f)
        elif fmt == "md":
            data = self._load_markdown(path)
        elif fmt == "xml":
            data = self._load_xml(path)
        else:
            return None # Should not happen given _find_entity_file
            
        return self.model_class.model_validate(data)

    def load_all(self) -> list[T]:
        """Load all entities."""
        entities = []
        # List all files that match ID pattern
        for path in self.entity_dir.iterdir():
            if path.name.startswith("_") or not path.is_file():
                continue
            
            # Simple check if stem is integer
            if path.stem.isdigit():
                try:
                    # Reuse load logic which handles formats
                    entity = self.load(int(path.stem))
                    if entity:
                        entities.append(entity)
                except Exception:
                    # Log error or skip corrupt files
                    continue
        
        # Sort by ID for consistency
        # Assuming entities have 'id' field, but T is bound to BaseModel which doesn't guarantee 'id'.
        # However, for our repos, they mostly do. We can check or just return as is.
        # Let's try to sort if 'id' is present
        entities.sort(key=lambda x: getattr(x, "id", 0))
        return entities

    def delete(self, entity_id: int) -> bool:
        """Delete entity by ID."""
        path = self._find_entity_file(entity_id)
        if path:
            path.unlink()
            return True
        return False

    def _save_markdown(self, path: Path, data: dict[str, Any]) -> None:
        """Save as Markdown with frontmatter."""
        # Simple frontmatter implementation without external lib if possible, 
        # but to be robust we might want pyyaml or similar.
        # For now, let's just write YAML-like block + empty body or JSON in frontmatter.
        
        # Using json content in frontmatter is valid YAML (mostly) but let's try to be nicer.
        # Since we don't have pyyaml in core dependencies yet (only in optional),
        # we can't strictly rely on it unless we add it to 'files' extra.
        # For this pass, I will assume we can use basic string formatting or just JSON-in-YAML.
        
        import io
        
        content = "---\n"
        content += json.dumps(data, indent=2) # Valid YAML is a superset of JSON
        content += "\n---\n"
        
        with open(path, "w") as f:
            f.write(content)

    def _load_markdown(self, path: Path) -> dict[str, Any]:
        """Load from Markdown frontmatter."""
        with open(path, "r") as f:
            content = f.read()
            
        if content.startswith("---"):
            try:
                # Extract content between ---
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    return json.loads(frontmatter)
            except Exception:
                pass
        
        raise ValueError(f"Invalid markdown format in {path}")

    def _save_xml(self, path: Path, data: dict[str, Any]) -> None:
        """Save as XML."""
        # Simple flat XML or recursive?
        # Implementing a full dict->xml converter is non-trivial without external libs like dicttoxml
        # or stdlib xml.etree.ElementTree.
        # Let's use ElementTree for a basic structure: <Entity> <Field>Value</Field> ... </Entity>
        
        from xml.etree.ElementTree import Element, SubElement, tostring
        from xml.dom import minidom

        def dict_to_xml(parent, d):
            for key, value in d.items():
                if isinstance(value, dict):
                    child = SubElement(parent, key)
                    dict_to_xml(child, value)
                elif isinstance(value, list):
                    # For lists, we usually want repeated elements.
                    # This is ambiguous in dict-to-xml mapping without schema.
                    # Strategy: wrapped in parent key, or repeated key?
                    # Let's assume repeated key often preferred, or container.
                    # For now: <items><item>...</item></items> style is safer?
                    # Or just <key>value1</key> <key>value2</key>
                    
                    # Going with: Create a container 'key' and children 'item' (implicit) or rely on context
                    # Actually standard conversion often does:
                    # key: [v1, v2] -> <key>v1</key><key>v2</key>
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
        
        xml_str = minidom.parseString(tostring(root)).toprettyxml(indent="  ")
        
        with open(path, "w") as f:
            f.write(xml_str)

    def _load_xml(self, path: Path) -> dict[str, Any]:
        """Load from XML."""
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(path)
        root = tree.getroot()
        
        # XML to Dict is also ambiguous (lists vs single items).
        # We need to know the schema or assume lists for repeated tags.
        # Since we are validating against Pydantic model later, we can guess.
        
        def xml_to_dict(element):
            result = {}
            for child in element:
                # Naive implementation: if key exists, convert to list
                val = xml_to_dict(child) if len(child) > 0 else child.text
                
                # Type conversion (relying on Pydantic to fix string types later is usually fine)
                
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(val)
                else:
                    result[child.tag] = val
            return result
            
        data = xml_to_dict(root)
        
        # The naive xml_to_dict might fail for lists of complex objects if not strictly repeated.
        # Also attributes are ignored.
        # Pydantic validation will catch simple type errors, but structural mismatch is possible.
        # This is a basic implementation as requested.
        data = xml_to_dict(root)
        
        # Post-process to ensure list fields are lists
        # This handles the case where XML parser collapses 1-item list to a dict/atom
        for field_name, field_info in self.model_class.model_fields.items():
            if field_name in data:
                # Check if field type is list/sequence
                # This is a basic check; might need more robust typing inspection (get_origin, etc)
                # Pydantic fields often have annotation.
                from typing import get_origin
                
                origin = get_origin(field_info.annotation)
                if origin is list:
                     if not isinstance(data[field_name], list):
                         data[field_name] = [data[field_name]]
                         
                elif origin is dict:
                    # If XML tag was empty <meta />, xml_to_dict might return None or empty string
                    if data[field_name] is None:
                        data[field_name] = {}
        
        return data
