"""Data provider service for the PanganPintar FastAPI app.

Loads the historical weekly price CSV (artifacts/weekly_prices.csv) into
memory at startup and exposes vectorized query helpers used by the
prediction pipeline (history lookback, target-week validation, and
national-mean aggregation).

A single module-level ``DataProvider`` instance is exposed via
``get_data_provider()`` so the FastAPI dependency system can reuse the
same in-memory DataFrame across all requests.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd


logger = logging.getLogger(__name__)


# Lookback minimum yang dibutuhkan oleh feature engineering XGBoost
# (lag_52, rolling_mean_12, dst). Target week dianggap valid hanya jika
# tersedia minimal sejumlah ini minggu history sebelumnya.
MINIMUM_HISTORY_WEEKS: int = 52

# Kolom wajib di weekly_prices.csv. Diverifikasi saat load().
REQUIRED_COLUMNS: list[str] = [
    "week_start",
    "Commodity_Name",
    "Province_Name",
    "Price",
]


class DataProvider:
    """In-memory provider for historical weekly commodity prices.

    The provider is lazy: nothing is read from disk until ``load()`` is
    called (typically during FastAPI startup).
    """

    def __init__(self, csv_path: Path) -> None:
        """Initialize the provider without performing any I/O.

        Args:
            csv_path: Path to the ``weekly_prices.csv`` file.
        """
        # Disimpan sebagai Path supaya semua operasi path konsisten
        self.csv_path: Path = Path(csv_path)
        self._df: Optional[pd.DataFrame] = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        """Return True once ``load()`` has successfully completed."""
        return self._is_loaded

    def load(self) -> None:
        """Load the CSV into memory and sort it for downstream queries.

        Raises:
            FileNotFoundError: If ``csv_path`` does not exist.
            ValueError: If any of the required columns is missing.
        """
        if not self.csv_path.exists():
            msg = (
                f"Historical prices CSV not found: {self.csv_path}. "
                "Pastikan file 'artifacts/weekly_prices.csv' tersedia."
            )
            logger.error(msg)
            raise FileNotFoundError(msg)

        logger.info("Loading weekly prices from %s", self.csv_path)
        # parse_dates supaya kolom week_start langsung jadi datetime64 dan
        # bisa difilter via perbandingan dengan datetime.date
        df = pd.read_csv(self.csv_path, parse_dates=["week_start"])

        # Validasi kolom wajib supaya error muncul cepat saat startup,
        # bukan saat request masuk
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing_cols:
            msg = (
                f"weekly_prices.csv is missing required columns: {missing_cols}. "
                f"Found columns: {list(df.columns)}"
            )
            logger.error(msg)
            raise ValueError(msg)

        # Sort sekali di awal supaya semua method query tidak perlu sort ulang.
        # Urutan kolom sort dipilih agar .tail(n) langsung mengambil n minggu
        # terbaru per pair.
        df = df.sort_values(
            by=["Commodity_Name", "Province_Name", "week_start"],
            kind="mergesort",  # stable sort
        ).reset_index(drop=True)

        self._df = df
        self._is_loaded = True

        # Log ringkasan untuk verifikasi cepat di startup
        n_pairs = df[["Commodity_Name", "Province_Name"]].drop_duplicates().shape[0]
        logger.info(
            "DataProvider ready: shape=%s, date_range=[%s .. %s], pairs=%d",
            df.shape,
            df["week_start"].min().date(),
            df["week_start"].max().date(),
            n_pairs,
        )

    def _require_loaded(self) -> pd.DataFrame:
        """Internal guard: return the DataFrame or raise if not yet loaded."""
        if not self._is_loaded or self._df is None:
            raise RuntimeError(
                "DataProvider has not been loaded yet. Call load() first."
            )
        return self._df

    def get_history(
        self,
        commodity: str,
        province: str,
        before_week: date,
        n_weeks: int = 52,
    ) -> pd.DataFrame:
        """Return the last ``n_weeks`` rows strictly before ``before_week``.

        Args:
            commodity: Commodity name (must match values in the CSV).
            province: Province name (must match values in the CSV).
            before_week: Exclusive upper bound on ``week_start``.
            n_weeks: Number of trailing weeks to return.

        Raises:
            ValueError: If fewer than ``n_weeks`` rows are available for the
                given (commodity, province) before ``before_week``.
        """
        df = self._require_loaded()

        # Vectorized boolean mask; tidak ada Python-level loop di sini
        mask = (
            (df["Commodity_Name"] == commodity)
            & (df["Province_Name"] == province)
            & (df["week_start"] < pd.Timestamp(before_week))
        )
        # Karena df sudah ter-sort di load(), subset hasil filter pun ikut sorted.
        # .tail(n_weeks) ambil n minggu terbaru tepat sebelum before_week.
        history = df.loc[mask].tail(n_weeks)

        if len(history) < n_weeks:
            raise ValueError(
                f"Insufficient history for ({commodity}, {province}) "
                f"before {before_week}: needed {n_weeks} weeks, "
                f"only {len(history)} available."
            )

        # Reset index supaya caller dapat DataFrame yang rapi
        return history.reset_index(drop=True)

    def get_full_history(
        self,
        commodity: str,
        province: str,
    ) -> pd.DataFrame:
        """Return all rows for the given (commodity, province), sorted by week."""
        df = self._require_loaded()
        mask = (df["Commodity_Name"] == commodity) & (df["Province_Name"] == province)
        # Sudah sorted by week_start dari load(); cukup filter + reset_index
        return df.loc[mask].reset_index(drop=True)

    def get_available_weeks(
        self,
        commodity: str,
        province: str,
    ) -> tuple[date, date]:
        """Return (min_week, max_week) available for the given pair.

        Raises:
            ValueError: If the pair has no rows in the dataset.
        """
        df = self._require_loaded()
        mask = (df["Commodity_Name"] == commodity) & (df["Province_Name"] == province)
        weeks = df.loc[mask, "week_start"]

        if weeks.empty:
            raise ValueError(
                f"No data available for pair ({commodity}, {province})."
            )

        # .min()/.max() pada datetime64 mengembalikan Timestamp; konversi ke date
        return (weeks.min().date(), weeks.max().date())

    def validate_target_week(
        self,
        commodity: str,
        province: str,
        target_week: date,
    ) -> None:
        """Validate that ``target_week`` can be predicted for the given pair.

        A target week is valid when at least ``MINIMUM_HISTORY_WEEKS`` rows
        with ``week_start < target_week`` exist for the given (commodity,
        province) pair.

        Raises:
            ValueError: If insufficient history is available. The message
                includes the actual number of available weeks.
        """
        df = self._require_loaded()
        mask = (
            (df["Commodity_Name"] == commodity)
            & (df["Province_Name"] == province)
            & (df["week_start"] < pd.Timestamp(target_week))
        )
        # int() supaya tipe pesan error konsisten (bukan numpy.int64)
        available = int(mask.sum())

        if available < MINIMUM_HISTORY_WEEKS:
            raise ValueError(
                f"Target week {target_week} is not predictable for "
                f"({commodity}, {province}): need at least "
                f"{MINIMUM_HISTORY_WEEKS} weeks of history, "
                f"only {available} available."
            )

    def get_national_mean(
        self,
        commodity: str,
        before_week: date,
    ) -> float:
        """Return the national mean price for ``commodity`` at the latest
        ``week_start < before_week``.

        This computes the mean across all provinces at the single most
        recent week prior to ``before_week``. Used to derive the
        ``national_mean_lag1`` feature for the XGBoost models.

        Raises:
            ValueError: If no rows exist for ``commodity`` strictly before
                ``before_week``.
        """
        df = self._require_loaded()
        mask = (
            (df["Commodity_Name"] == commodity)
            & (df["week_start"] < pd.Timestamp(before_week))
        )
        subset = df.loc[mask, ["week_start", "Price"]]

        if subset.empty:
            raise ValueError(
                f"No historical data available for commodity '{commodity}' "
                f"before {before_week}."
            )

        # Ambil minggu terbaru sebelum before_week, lalu rata-rata di 34 provinsi.
        # .max() pada datetime64 -> Timestamp, dipakai langsung untuk masking.
        latest_week = subset["week_start"].max()
        latest_prices = subset.loc[subset["week_start"] == latest_week, "Price"]

        # float() supaya hasil bersih dari numpy.float64
        return float(latest_prices.mean())


# Singleton instance: dibuat sekali saat modul di-import. Pemanggilan load()
# dilakukan di FastAPI startup event supaya I/O tidak terjadi saat import time.
data_provider: DataProvider = DataProvider(
    csv_path=Path("./artifacts/weekly_prices.csv")
)


def get_data_provider() -> DataProvider:
    """Return the module-level ``DataProvider`` singleton.

    Designed to be used as a FastAPI dependency:

        from fastapi import Depends
        from app.services.data_provider import get_data_provider, DataProvider

        @app.get(...)
        def endpoint(provider: DataProvider = Depends(get_data_provider)):
            ...
    """
    return data_provider
