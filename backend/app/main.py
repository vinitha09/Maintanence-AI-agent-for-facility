from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes.facility import router
from backend.app.db.connection import create_db_and_tables, engine
from backend.app.services.auth_security import validate_jwt_secret


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_jwt_secret()
        create_db_and_tables()
        yield
    finally:
        engine.dispose()

app = FastAPI(
    title="Digital AI Assistance",
    version="1.0.0",
    lifespan=lifespan
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def validate_mutation_origin(request, call_next):
    origin = request.headers.get("origin")
    if (
        request.method in {"POST", "PUT", "PATCH", "DELETE"}
        and origin is not None
        and origin not in allowed_origins
    ):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=403,
            content={"detail": "Request origin is not allowed."},
        )
    return await call_next(request)


app.include_router(router)
