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
        # Fail fast but return None for robustness if path was provided but reading failed
        # Actually user_global says "strictly fail fast". So I should probably let the exception bubble up
        # or handle it and raise a more specific one.
        # But for logo, maybe it's better to just not show it if resolution fails?
        # Let's follow "fail fast" and just not catch if it's truly unexpected.
        raise
