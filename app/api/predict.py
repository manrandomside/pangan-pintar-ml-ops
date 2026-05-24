"""Prediction API router for the PanganPintar FastAPI app.

Exposes:
    - POST /api/v1/predict      : single-week price prediction
    - GET  /api/v1/commodities  : list of supported commodities
    - GET  /api/v1/provinces    : list of supported provinces

The router delegates all business logic to ``PredictionService`` and
only handles HTTP concerns: request parsing, exception translation,
and structured error responses.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.prediction import (
    ErrorResponse,
    PredictionRequest,
    PredictionResponse,
)
from app.services.prediction_service import (
    PredictionService,
    get_prediction_service,
)


logger = logging.getLogger(__name__)


# Semua endpoint prediksi dikelompokkan di bawah /api/v1 dengan tag
# "Prediction" supaya rapi di Swagger UI.
router = APIRouter(prefix="/api/v1", tags=["Prediction"])


@router.post(
    "/predict",
    response_model=PredictionResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid request or insufficient history",
        },
        404: {
            "model": ErrorResponse,
            "description": "Commodity model not found",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
        },
    },
    summary="Predict weekly food commodity price",
    description=(
        "Predict the price of a specific food commodity in a specific "
        "Indonesian province for a target week, using XGBoost regression "
        "model trained on historical PIHPS data."
    ),
)
async def predict_price(
    request: PredictionRequest,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionResponse:
    """Predict the weekly price for a single (commodity, province, week).

    Translates service-layer exceptions into structured HTTP errors:

    - ``ValueError``  -> 400 ValidationError
    - ``KeyError``    -> 404 ModelNotFound
    - any other       -> 500 InternalError
    """
    logger.info(
        "Incoming prediction request: commodity=%s, province=%s, target_week=%s",
        request.commodity,
        request.province,
        request.target_week,
    )

    try:
        # Seluruh pipeline (validasi -> history -> features -> predict)
        # dijalankan di service layer.
        result = service.predict(request)
        return result

    except ValueError as e:
        # ValueError di-raise oleh DataProvider.validate_target_week,
        # get_history, atau FeatureEngineer.build_features bila input
        # tidak cukup / tidak konsisten.
        logger.warning("Validation error during prediction: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": str(e),
            },
        )

    except KeyError as e:
        # KeyError di-raise oleh ModelLoader.get_model bila model untuk
        # commodity tertentu tidak ter-load.
        logger.error("Model lookup failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "ModelNotFound",
                "message": str(e),
            },
        )

    except Exception as e:
        # logger.exception otomatis menyertakan stack trace lengkap;
        # pesan ke client sengaja generik supaya tidak membocorkan internal.
        logger.exception("Unexpected error during prediction: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalError",
                "message": "An unexpected error occurred during prediction",
            },
        )


@router.get(
    "/commodities",
    summary="Get list of supported commodities",
)
async def list_commodities(
    service: PredictionService = Depends(get_prediction_service),
) -> dict:
    """Return the list of commodity names supported by the API."""
    # Diambil dari metadata via ModelLoader supaya selalu sinkron dengan
    # model yang benar-benar ter-load di memori.
    return {"commodities": service.model_loader.get_commodities()}


@router.get(
    "/provinces",
    summary="Get list of supported provinces",
)
async def list_provinces(
    service: PredictionService = Depends(get_prediction_service),
) -> dict:
    """Return the list of province names supported by the API."""
    metadata = service.model_loader.get_metadata()
    return {"provinces": metadata["provinces"]}
