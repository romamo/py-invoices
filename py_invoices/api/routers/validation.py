import os
import tempfile
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from py_invoices.core.validator import UBLValidator, ValidationResult

router = APIRouter()


@router.post("/ubl", response_model=ValidationResult)
async def validate_ubl_file(file: UploadFile = File(...)) -> Any:
    """Validate a UBL XML file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # UBLValidator currently requires a file path.
    # We save to a temp file.

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = UBLValidator.validate_file(tmp_path)
        return result

    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
