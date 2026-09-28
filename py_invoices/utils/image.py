import base64
import mimetypes
from pathlib import Path

PASSTHROUGH_SCHEMES = ("http://", "https://", "data:")


def file_to_base64_data_uri(file_path: str | None) -> str | None:
    """Convert an image file to a Base64 data URI.

    URLs and data URIs are returned unchanged.

    Raises:
        FileNotFoundError: If a local path does not point to a file
    """
    if not file_path:
        return None
    if file_path.startswith(PASSTHROUGH_SCHEMES):
        return file_path

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Logo file not found: {file_path}")

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
