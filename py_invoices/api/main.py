from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from py_invoices.api.routers import invoices, clients

app = FastAPI(
    title="py-invoices API",
    description="API for managing invoices and clients using py-invoices.",
    version="1.0.0",
)

# Allow CORS for the Web App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, this should be specific
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Get absolute path to static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")

# Mount static directory
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(clients.router, prefix="/clients", tags=["clients"])

@app.get("/")
def read_root():
    return FileResponse(os.path.join(static_dir, "index.html"))
