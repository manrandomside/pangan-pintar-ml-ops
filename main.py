"""Pangan Pintar API entry point.

FastAPI application bootstrap for the Pangan Pintar weekly food price
prediction service. Configuration is sourced from environment variables
loaded from the local .env file.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.predict import router as predict_router
from app.services.data_provider import get_data_provider
from app.services.feature_engineer import get_feature_engineer
from app.services.model_loader import get_model_loader
from app.services.prediction_service import init_prediction_service

# Memuat environment variables dari file .env sebelum membaca konfigurasi apapun
load_dotenv()

# Logging dikonfigurasi sedini mungkin supaya log dari startup event
# (load model, load CSV, dst) ikut tertangkap oleh handler default.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Konfigurasi aplikasi dibaca dari environment dengan fallback yang aman
APP_NAME: str = os.getenv("APP_NAME", "Pangan Pintar API")
APP_VERSION: str = os.getenv("APP_VERSION", "0.1.0")
DEBUG: bool = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes"}

# CORS origins disimpan sebagai comma-separated string di .env, dipecah jadi list
_raw_cors: str = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS: list[str] = [origin.strip() for origin in _raw_cors.split(",") if origin.strip()]

APP_DESCRIPTION: str = (
    "Weekly food commodity price prediction API for Indonesian provinces, "
    "powered by XGBoost regression models."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: load artifacts on startup, log on shutdown.

    Urutan startup penting:
        1. ModelLoader  - butuh metadata.json untuk menentukan model apa saja
        2. DataProvider - butuh weekly_prices.csv sebagai sumber history
        3. FeatureEngineer - butuh metadata dari ModelLoader untuk lookup tables
        4. PredictionService - butuh ketiga service di atas siap pakai
    Bila ada exception di salah satu langkah, FastAPI akan gagal start (fail-fast).
    """
    # ---- Startup ----
    logger.info("Loading XGBoost models...")
    model_loader = get_model_loader()
    model_loader.load_all()

    logger.info("Loading historical price data...")
    data_provider = get_data_provider()
    data_provider.load()

    logger.info("Initializing feature engineer...")
    feature_engineer = get_feature_engineer(metadata=model_loader.get_metadata())

    logger.info("Initializing prediction service...")
    init_prediction_service(
        model_loader=model_loader,
        data_provider=data_provider,
        feature_engineer=feature_engineer,
    )

    logger.info("Application startup complete. Ready to serve predictions.")
    yield

    # ---- Shutdown ----
    logger.info("Application shutting down.")


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    debug=DEBUG,
    lifespan=lifespan,
)

# CORS middleware mengizinkan request dari frontend pada origin yang dikonfigurasi
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register router prediksi (prefix /api/v1) setelah middleware terpasang
app.include_router(predict_router)


@app.get("/")
async def root() -> dict[str, Any]:
    """Return a welcome payload with service metadata and docs link."""
    return {
        "message": f"Welcome to {APP_NAME}",
        "version": APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a lightweight liveness probe for orchestrators and uptime checks."""
    return {
        "status": "healthy",
        "service": APP_NAME,
    }
