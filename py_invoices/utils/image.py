import base64
import mimetypes
import os


def file_to_base64_data_uri(file_path: str | None) -> str | None:
    """
    Convert an image file to a Base64 data URI.
    If file not found, returns the original path as is.
    """
    if not file_path:
        return None

    if not os.path.exists(file_path):
        return file_path

    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded_string}"
    except Exception:
        # Actually user_global says "strictly fail fast".
        # Let the exception bubble up for debugging.
        raise
