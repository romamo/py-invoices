import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(
    title="py-invoices API",
    description="API for managing invoices and clients using py-invoices.",
    version="1.0.0",
)

# Allow CORS for the Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, this should be specific
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get absolute path to static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(credit_notes.router, prefix="/credit-notes", tags=["credit-notes"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(companies.router, prefix="/companies", tags=["companies"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(payment_notes.router, prefix="/payment-notes", tags=["payment-notes"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
app.include_router(validation.router, prefix="/validation", tags=["validation"])


@app.get("/")
def read_root() -> FileResponse:
    return FileResponse(os.path.join(static_dir, "index.html"))

