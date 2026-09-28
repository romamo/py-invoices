import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from py_invoices import __version__
from py_invoices.api.routers import (
    audit,
    clients,
    companies,
    credit_notes,
    invoices,
    payment_notes,
    payments,
    products,
    validation,
)
from py_invoices.api.security import API_KEY_HEADER, require_api_key
from py_invoices.config import get_settings
from py_invoices.constants import APP_NAME

app = FastAPI(
    title=f"{APP_NAME} API",
    description=f"API for managing invoices and clients using {APP_NAME}.",
    version=__version__,
)

# The bundled web app is same-origin; other browser origins must be listed explicitly.
# Auth is a header, not a cookie, so credentials are never needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=[API_KEY_HEADER, "Content-Type"],
)

# Get absolute path to static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

protected = [Depends(require_api_key)]
routers = [
    (invoices.router, "/invoices", "invoices"),
    (clients.router, "/clients", "clients"),
    (credit_notes.router, "/credit-notes", "credit-notes"),
    (products.router, "/products", "products"),
    (companies.router, "/companies", "companies"),
    (payments.router, "/payments", "payments"),
    (payment_notes.router, "/payment-notes", "payment-notes"),
    (audit.router, "/audit", "audit"),
    (validation.router, "/validation", "validation"),
]
for router, prefix, tag in routers:
    app.include_router(router, prefix=prefix, tags=[tag], dependencies=protected)


@app.get("/")
def read_root() -> FileResponse:
    return FileResponse(os.path.join(static_dir, "index.html"))
