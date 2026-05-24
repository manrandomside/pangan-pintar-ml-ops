"""Model loader service for the PanganPintar FastAPI app.

Responsible for loading all XGBoost commodity models and the
companion metadata.json into memory at startup, and for serving
them to the prediction endpoints.

A single module-level ``ModelLoader`` instance is exposed via
``get_model_loader()`` so the FastAPI dependency system can reuse
the same in-memory copies across all requests.
"""

import json
import logging
from pathlib import Path

import joblib
from xgboost import XGBRegressor


logger = logging.getLogger(__name__)


class ModelLoader:
    """Loads and caches XGBoost models plus metadata for the API.

    The loader is intentionally lazy: nothing is read from disk until
    ``load_all()`` is called (typically during FastAPI startup).
    """

    def __init__(self, artifacts_dir: Path) -> None:
        """Initialize the loader without performing any I/O.

        Args:
            artifacts_dir: Path to the folder containing ``metadata.json``
                and the ``xgb_*.pkl`` model files.
        """
        # Disimpan sebagai Path supaya semua operasi path konsisten
        self.artifacts_dir: Path = Path(artifacts_dir)
        self._models: dict[str, XGBRegressor] = {}
        self._metadata: dict = {}
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return True once ``load_all()`` has successfully completed."""
        return self._is_loaded

    @staticmethod
    def _commodity_to_slug(commodity: str) -> str:
        """Convert a commodity display name to its filename slug.

        Example: ``"Bawang Merah"`` -> ``"bawang_merah"``.
        """
        # Slug dipakai untuk menyusun nama file xgb_{slug}.pkl
        return commodity.lower().replace(" ", "_")

    def load_all(self) -> None:
        """Load metadata.json and every XGBoost model into memory.

        Raises:
            FileNotFoundError: If the artifacts directory, ``metadata.json``,
                or any expected model file is missing.
        """
        # Pastikan folder artifacts ada sebelum membaca apa pun
        if not self.artifacts_dir.exists():
            msg = (
                f"Artifacts directory not found: {self.artifacts_dir}. "
                "Pastikan folder 'artifacts/' tersedia di root project."
            )
            logger.error(msg)
            raise FileNotFoundError(msg)

        # 1. Load metadata.json terlebih dulu karena daftar commodities-nya
        #    dipakai untuk menentukan file model apa saja yang harus di-load.
        metadata_path = self.artifacts_dir / "metadata.json"
        if not metadata_path.exists():
            msg = f"metadata.json not found at: {metadata_path}"
            logger.error(msg)
            raise FileNotFoundError(msg)

        logger.info("Loading metadata from %s", metadata_path)
        with metadata_path.open("r", encoding="utf-8") as f:
            self._metadata = json.load(f)

        commodities: list[str] = self._metadata.get("commodities", [])
        if not commodities:
            logger.error("metadata.json has empty or missing 'commodities' key")
            raise ValueError(
                "metadata.json must contain a non-empty 'commodities' list"
            )

        # 2. Iterasi tiap commodity, susun path file model, lalu load via joblib
        for commodity in commodities:
            slug = self._commodity_to_slug(commodity)
            model_path = self.artifacts_dir / f"xgb_{slug}.pkl"

            if not model_path.exists():
                msg = (
                    f"Model file not found for commodity '{commodity}': "
                    f"{model_path}"
                )
                logger.error(msg)
                raise FileNotFoundError(msg)

            logger.info("Loading model for '%s' from %s", commodity, model_path)
            try:
                model = joblib.load(model_path)
            except Exception as e:
                # Re-raise dengan konteks supaya stack trace lebih informatif
                logger.error(
                    "Failed to load model for '%s' (%s): %s",
                    commodity,
                    type(e).__name__,
                    e,
                )
                raise

            # Disimpan dengan key nama commodity asli (case-sensitive, spasi),
            # konsisten dengan ALLOWED_COMMODITIES di schemas/prediction.py
            self._models[commodity] = model

        self._is_loaded = True
        logger.info(
            "ModelLoader ready: %d models loaded (%s)",
            len(self._models),
            ", ".join(self._models.keys()),
        )

    def get_model(self, commodity: str) -> XGBRegressor:
        """Return the XGBoost model for the given commodity.

        Args:
            commodity: Commodity display name, e.g. ``"Beras"``.

        Raises:
            KeyError: If the commodity is not present in the loaded models.
        """
        # Akses singkat tanpa default supaya KeyError eksplisit
        if commodity not in self._models:
            available = list(self._models.keys())
            raise KeyError(
                f"Model for commodity '{commodity}' not found. "
                f"Available: {available}"
            )
        return self._models[commodity]

    def get_metadata(self) -> dict:
        """Return the loaded metadata dictionary."""
        return self._metadata

    def get_commodities(self) -> list[str]:
        """Return the list of supported commodity names from metadata."""
        # Kembalikan list baru supaya caller tidak bisa memutasi internal state
        return list(self._metadata.get("commodities", []))

    def get_features(self) -> list[str]:
        """Return the ordered list of XGBoost feature names from metadata."""
        return list(self._metadata.get("xgb_features", []))


# Singleton instance: dibuat sekali saat modul di-import. Pemanggilan
# load_all() dilakukan di FastAPI startup event supaya I/O tidak terjadi
# saat import time.
model_loader: ModelLoader = ModelLoader(artifacts_dir=Path("./artifacts"))


def get_model_loader() -> ModelLoader:
    """Return the module-level ``ModelLoader`` singleton.

    Designed to be used as a FastAPI dependency:

        from fastapi import Depends
        from app.services.model_loader import get_model_loader, ModelLoader

        @app.get(...)
        def endpoint(loader: ModelLoader = Depends(get_model_loader)):
            ...
    """
    return model_loader
