"""In-memory storage backend."""

# Import plugin to trigger auto-registration
from .plugin import MemoryPlugin

__all__ = ["MemoryPlugin"]
