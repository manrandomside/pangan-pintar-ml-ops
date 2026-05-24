"""Pydantic schemas for the price prediction endpoint.

This module defines the request/response contracts used by the FastAPI
endpoint that serves XGBoost-based weekly price predictions for the
PanganPintar project.
"""

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Daftar komoditas yang didukung. Harus sinkron dengan metadata.json
# di folder artifacts/ (key "commodities").
ALLOWED_COMMODITIES: list[str] = [
    "Bawang Merah",
    "Bawang Putih",
    "Beras",
    "Cabai Merah",
    "Cabai Rawit",
    "Daging Ayam",
    "Daging Sapi",
    "Gula Pasir",
    "Minyak Goreng",
    "Telur Ayam",
]

# Daftar provinsi yang didukung (34 provinsi). Harus sinkron dengan
# metadata.json (key "provinces").
ALLOWED_PROVINCES: list[str] = [
    "Aceh",
    "Bali",
    "Banten",
    "Bengkulu",
    "DI Yogyakarta",
    "DKI Jakarta",
    "Gorontalo",
    "Jambi",
    "Jawa Barat",
    "Jawa Tengah",
    "Jawa Timur",
    "Kalimantan Barat",
    "Kalimantan Selatan",
    "Kalimantan Tengah",
    "Kalimantan Timur",
    "Kalimantan Utara",
    "Kepulauan Bangka Belitung",
    "Kepulauan Riau",
    "Lampung",
    "Maluku",
    "Maluku Utara",
    "Nusa Tenggara Barat",
    "Nusa Tenggara Timur",
    "Papua",
    "Papua Barat",
    "Riau",
    "Sulawesi Barat",
    "Sulawesi Selatan",
    "Sulawesi Tengah",
    "Sulawesi Tenggara",
    "Sulawesi Utara",
    "Sumatera Barat",
    "Sumatera Selatan",
    "Sumatera Utara",
]


class PredictionRequest(BaseModel):
    """Request payload for a single weekly price prediction.

    Clients must supply a supported commodity, a supported province,
    and the target week (a calendar date, typically a Monday).
    """

    commodity: str = Field(
        ...,
        description=(
            "Commodity name to predict. Must be one of the 10 supported "
            "commodities listed in ALLOWED_COMMODITIES."
        ),
        examples=["Beras"],
    )
    province: str = Field(
        ...,
        description=(
            "Province name (Indonesian administrative province). Must be "
            "one of the 34 supported provinces listed in ALLOWED_PROVINCES."
        ),
        examples=["Aceh"],
    )
    target_week: date = Field(
        ...,
        description=(
            "Target week for the prediction, expressed as a date in "
            "YYYY-MM-DD format. Conventionally the Monday of the target week."
        ),
        examples=["2026-01-12"],
    )

    @field_validator("commodity")
    @classmethod
    def validate_commodity(cls, v: str) -> str:
        """Ensure the commodity is in the allowed list."""
        # Pesan error dibuat eksplisit supaya client tahu nilai yang valid
        if v not in ALLOWED_COMMODITIES:
            raise ValueError(
                f"Commodity '{v}' is not supported. "
                f"Allowed values: {ALLOWED_COMMODITIES}"
            )
        return v

    @field_validator("province")
    @classmethod
    def validate_province(cls, v: str) -> str:
        """Ensure the province is in the allowed list."""
        # Tampilkan daftar lengkap supaya mudah didebug dari sisi client
        if v not in ALLOWED_PROVINCES:
            raise ValueError(
                f"Province '{v}' is not supported. "
                f"Allowed values: {ALLOWED_PROVINCES}"
            )
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "commodity": "Beras",
                "province": "Aceh",
                "target_week": "2026-01-12",
            }
        }
    }


class PredictionResponse(BaseModel):
    """Response payload returned for a successful prediction request."""

    commodity: str = Field(
        ...,
        description="Echo of the requested commodity name.",
    )
    province: str = Field(
        ...,
        description="Echo of the requested province name.",
    )
    target_week: date = Field(
        ...,
        description="Echo of the requested target week (YYYY-MM-DD).",
    )
    predicted_price: float = Field(
        ...,
        description="Predicted commodity price for the target week, in Rupiah.",
        examples=[14250.50],
    )
    # Default literal supaya field selalu konsisten di response
    currency: Literal["IDR"] = Field(
        default="IDR",
        description="Currency code of predicted_price. Always 'IDR'.",
    )
    model: Literal["XGBoost"] = Field(
        default="XGBoost",
        description="Name of the model used to produce the prediction.",
    )
    predicted_at: datetime = Field(
        ...,
        description=(
            "Server timestamp (ISO 8601) indicating when the prediction "
            "was generated."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "commodity": "Beras",
                "province": "Aceh",
                "target_week": "2026-01-12",
                "predicted_price": 14250.50,
                "currency": "IDR",
                "model": "XGBoost",
                "predicted_at": "2026-05-24T14:30:00",
            }
        }
    }


class ErrorResponse(BaseModel):
    """Standardized error response returned by the prediction endpoints."""

    error: str = Field(
        ...,
        description=(
            "Short machine-readable error type, e.g. 'ValidationError' "
            "or 'ModelNotFound'."
        ),
        examples=["ValidationError"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error.",
        examples=["Commodity 'Foo' is not supported."],
    )
    # Optional supaya endpoint boleh tidak mengisinya bila tidak ada konteks tambahan
    details: Optional[dict] = Field(
        default=None,
        description=(
            "Optional structured details about the error "
            "(e.g. offending field, allowed values)."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "ValidationError",
                "message": "Commodity 'Foo' is not supported.",
                "details": {
                    "field": "commodity",
                    "allowed": ALLOWED_COMMODITIES,
                },
            }
        }
    }
