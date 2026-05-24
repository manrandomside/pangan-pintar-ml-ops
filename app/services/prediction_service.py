"""Prediction orchestration service for the PanganPintar FastAPI app.

Wires together the three lower-level services — ``ModelLoader``,
``DataProvider``, and ``FeatureEngineer`` — to execute the full
prediction pipeline for a single (commodity, province, target_week)
request:

    request -> validate -> fetch history -> build features
            -> load model -> predict -> response

Designed to live behind a FastAPI ``Depends(get_prediction_service)``
and to let lower-level exceptions propagate; the HTTP layer is
responsible for converting them to status codes.
"""

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from app.schemas.prediction import PredictionRequest, PredictionResponse
from app.services.data_provider import DataProvider
from app.services.feature_engineer import FeatureEngineer
from app.services.model_loader import ModelLoader


logger = logging.getLogger(__name__)


class PredictionService:
    """Orchestrates the end-to-end weekly price prediction pipeline."""

    def __init__(
        self,
        model_loader: ModelLoader,
        data_provider: DataProvider,
        feature_engineer: FeatureEngineer,
    ) -> None:
        """Wire in the three dependency services.

        Args:
            model_loader: Loaded XGBoost model registry.
            data_provider: In-memory historical price provider.
            feature_engineer: Feature builder configured with metadata.
        """
        self.model_loader: ModelLoader = model_loader
        self.data_provider: DataProvider = data_provider
        self.feature_engineer: FeatureEngineer = feature_engineer

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        """Run the full prediction pipeline for a single request.

        Steps:
            1. Validate that enough history exists before ``target_week``.
            2. Fetch the 52-week trailing history for the target pair.
            3. Fetch the full national history for the commodity.
            4. Engineer the 32 input features.
            5. Load the XGBoost model for the commodity.
            6. Predict and round to 2 decimal places.
            7. Build the response payload.

        Args:
            request: Validated ``PredictionRequest`` from the API layer.

        Returns:
            ``PredictionResponse`` containing the predicted price and
            request echo.

        Raises:
            ValueError: From ``validate_target_week`` / ``get_history``
                / ``build_features`` if input data is insufficient or
                inconsistent.
            KeyError: From ``ModelLoader.get_model`` if the commodity has
                no loaded model.
        """
        # Ambil field dari request sekali supaya log & body fungsi konsisten
        commodity = request.commodity
        province = request.province
        target_week = request.target_week

        logger.info(
            "Predicting %s di %s untuk %s",
            commodity,
            province,
            target_week,
        )

        # (b) Validasi cakupan waktu. Bila kurang dari MINIMUM_HISTORY_WEEKS,
        # ValueError dibiarkan propagate ke endpoint untuk dijadikan HTTP 400.
        self.data_provider.validate_target_week(commodity, province, target_week)

        # (c) Ambil 52 minggu trailing history untuk pair (commodity, province)
        history: pd.DataFrame = self.data_provider.get_history(
            commodity=commodity,
            province=province,
            before_week=target_week,
            n_weeks=52,
        )
        logger.info("History rows fetched: %d", len(history))

        # (d) Ambil seluruh history untuk commodity ini (lintas provinsi)
        # untuk dipakai menghitung national_mean_lag1 di feature engineer.
        # Akses langsung ke _df karena DataProvider belum mengekspos method
        # publik untuk slicing per-commodity tanpa filter provinsi.
        df_all = self.data_provider._df
        if df_all is None:
            # Guard tambahan: kalau provider belum di-load, log & raise.
            raise RuntimeError(
                "DataProvider has not been loaded; cannot access internal frame."
            )
        national: pd.DataFrame = df_all[df_all["Commodity_Name"] == commodity]

        # (e) Bangun 32 fitur dalam urutan yang sesuai metadata['xgb_features']
        features_df: pd.DataFrame = self.feature_engineer.build_features(
            history=history,
            target_week=target_week,
            province=province,
            national_history=national,
        )
        logger.info(
            "Features built: shape=%s, columns=%d",
            features_df.shape,
            features_df.shape[1],
        )

        # (f) Load model XGBoost untuk commodity yang diminta
        model = self.model_loader.get_model(commodity)

        # (g) Prediksi. model.predict() return numpy array; ambil elemen
        # pertama lalu konversi ke float Python supaya bersih dari numpy types.
        raw_prediction = model.predict(features_df)[0]
        predicted_price = float(round(float(raw_prediction), 2))

        logger.info("Prediction result: %s IDR", predicted_price)

        # (h) Susun response. predicted_at memakai server time saat prediksi.
        return PredictionResponse(
            commodity=commodity,
            province=province,
            target_week=target_week,
            predicted_price=predicted_price,
            currency="IDR",
            model="XGBoost",
            predicted_at=datetime.now(),
        )


# Module-level singleton. Diinisialisasi via init_prediction_service() saat
# FastAPI startup (setelah ketiga dependency services siap), lalu diambil
# via Depends(get_prediction_service) di endpoint.
_prediction_service: Optional[PredictionService] = None


def init_prediction_service(
    model_loader: ModelLoader,
    data_provider: DataProvider,
    feature_engineer: FeatureEngineer,
) -> PredictionService:
    """Initialize (or reinitialize) the module-level PredictionService.

    Intended to be called once during FastAPI startup, after
    ``ModelLoader.load_all()``, ``DataProvider.load()``, and
    ``get_feature_engineer(metadata)`` have all completed.

    Returns:
        The newly created singleton instance.
    """
    global _prediction_service
    _prediction_service = PredictionService(
        model_loader=model_loader,
        data_provider=data_provider,
        feature_engineer=feature_engineer,
    )
    logger.info("PredictionService initialized")
    return _prediction_service


def get_prediction_service() -> PredictionService:
    """Return the module-level ``PredictionService`` singleton.

    Designed to be used as a FastAPI dependency:

        from fastapi import Depends
        from app.services.prediction_service import (
            get_prediction_service,
            PredictionService,
        )

        @app.post(...)
        def endpoint(svc: PredictionService = Depends(get_prediction_service)):
            ...

    Raises:
        RuntimeError: If ``init_prediction_service()`` has not been called yet.
    """
    if _prediction_service is None:
        raise RuntimeError(
            "PredictionService has not been initialized. "
            "Call init_prediction_service(...) during FastAPI startup."
        )
    return _prediction_service
