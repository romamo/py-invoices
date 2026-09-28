from fastapi import APIRouter, File, HTTPException, UploadFile

from py_invoices.core.validator import UBLValidator, ValidationResult

router = APIRouter()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/ubl", response_model=ValidationResult)
async def validate_ubl_file(file: UploadFile = File(...)) -> ValidationResult:
    """Validate an uploaded UBL XML file (at most 5 MB)."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File larger than 5 MB")
    return UBLValidator.validate_bytes(content, source=file.filename)
