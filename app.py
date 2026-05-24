import sys
import os

# Force the project root into sys.path to resolve the 'src.' namespace correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.trueroas.api.routes.metrics import router as metrics_router
from src.trueroas.api.routes.auth import router as auth_router

app = FastAPI(title="TrueROAS Precision Analytics Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")

@app.get("/")
def health_check():
    return {"status": "online", "engine": "TrueROAS Polars-DuckDB Core V1"}