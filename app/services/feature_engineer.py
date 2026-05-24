"""Feature engineering service for the PanganPintar prediction endpoint.

Given historical weekly prices for a single (commodity, province) pair and
the national-level history for that commodity, this service produces a
1-row DataFrame containing the 32 features that the XGBoost models expect,
in the exact order declared by ``metadata['xgb_features']``.

The class is intended to be cached at FastAPI startup (one instance per
process), since its lookup tables only depend on the immutable metadata.
"""

import logging
from datetime import date, datetime
from typing import Optional

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


# Jumlah baris history minimum yang harus disuplai caller. Karena lag_52
# membutuhkan 52 minggu ke belakang, di bawah angka ini feature engineering
# tidak bisa dilakukan.
MINIMUM_HISTORY_ROWS: int = 52

# Daftar nama region resmi yang dipakai untuk one-hot encoding. Urutan di
# sini hanya dipakai sebagai daftar; urutan kolom output ditentukan oleh
# metadata['xgb_features'].
REGION_NAMES: list[str] = [
    "Sumatera",
    "Jawa",
    "Bali_Nusra",
    "Kalimantan",
    "Sulawesi",
    "Maluku_Papua",
]


def _normalize_province_name(name: str) -> str:
    """Normalize province name spellings used inconsistently across metadata.

    The ``region_map`` in metadata.json uses abbreviated names such as
    ``"Kep. Bangka Belitung"`` and ``"Kep. Riau"``, while the canonical
    province list spells them out as ``"Kepulauan ..."``. This helper
    rewrites the short form to the canonical form so that the reverse
    lookup ``province_to_region`` is keyed consistently.
    """
    # Penanganan ringan: hanya ganti prefix "Kep." → "Kepulauan"
    return name.replace("Kep.", "Kepulauan")


class FeatureEngineer:
    """Builds the 32-feature input row required by the XGBoost models.

    A single instance can be shared across all requests; its state is
    derived entirely from the immutable ``metadata`` dict provided at
    construction time.
    """

    def __init__(self, metadata: dict) -> None:
        """Pre-compute lookup tables from metadata for fast feature building.

        Args:
            metadata: The loaded ``metadata.json`` dict. Must contain
                ``province_to_id``, ``region_map``, ``lebaran_dates``,
                ``idul_adha_dates``, and ``xgb_features``.
        """
        self.metadata: dict = metadata

        # 1. Mapping provinsi -> id (untuk feature province_id)
        self.province_to_id: dict[str, int] = dict(metadata["province_to_id"])

        # 2. region_map asli dari metadata (region -> list of provinces).
        #    Disimpan apa adanya untuk transparansi/debug.
        self.region_map: dict[str, list[str]] = {
            region: list(provinces)
            for region, provinces in metadata["region_map"].items()
        }

        # 3. Reverse lookup provinsi -> nama region. Karena metadata punya
        #    inkonsistensi nama ("Kep. Bangka Belitung" vs "Kepulauan
        #    Bangka Belitung"), kita normalisasi sebelum di-index.
        self.province_to_region: dict[str, str] = {}
        for region, provinces in self.region_map.items():
            for prov in provinces:
                canonical = _normalize_province_name(prov)
                self.province_to_region[canonical] = region

        # 4. Parse tanggal event sekali di awal supaya runtime tidak
        #    perlu parsing string berulang kali.
        self.lebaran_dates: list[date] = [
            datetime.strptime(d, "%Y-%m-%d").date()
            for d in metadata.get("lebaran_dates", [])
        ]
        self.idul_adha_dates: list[date] = [
            datetime.strptime(d, "%Y-%m-%d").date()
            for d in metadata.get("idul_adha_dates", [])
        ]

        # 5. Urutan kolom output. SUMBER KEBENARAN utama; kolom DataFrame
        #    hasil build_features() di-reorder sesuai list ini.
        self.feature_order: list[str] = list(metadata["xgb_features"])

        # 6. Daftar region untuk loop one-hot encoding
        self.region_names: list[str] = list(REGION_NAMES)

    def _weeks_to_event(
        self,
        target_week: date,
        event_dates: list[date],
    ) -> int:
        """Return number of full weeks from ``target_week`` to the next event.

        If no event date lies on or after ``target_week``, return 999 as a
        sentinel large value so the downstream model can still produce a
        prediction.
        """
        # Cari event paling awal yang >= target_week. event_dates urut
        # naik (sesuai metadata) tapi kita tetap lakukan filter eksplisit
        # supaya tahan terhadap urutan apa pun.
        upcoming = [d for d in event_dates if d >= target_week]
        if not upcoming:
            return 999

        nearest = min(upcoming)
        delta_days = (nearest - target_week).days
        # Floor division supaya hasil dalam satuan minggu penuh
        return int(delta_days // 7)

    def build_features(
        self,
        history: pd.DataFrame,
        target_week: date,
        province: str,
        national_history: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build the 32-feature input row for a single prediction.

        Args:
            history: At least ``MINIMUM_HISTORY_ROWS`` rows for the target
                (commodity, province), sorted chronologically ascending,
                with at minimum a ``Price`` column and a ``week_start`` column.
                All rows must satisfy ``week_start < target_week``.
            target_week: The week being predicted.
            province: Province name (must match keys in
                ``self.province_to_id`` and ``self.province_to_region``).
            national_history: Cross-province history for the same commodity
                (any provinces) used to compute the ``national_mean_lag1``
                feature. Must contain ``week_start`` and ``Price`` columns.

        Returns:
            A single-row DataFrame whose columns are exactly
            ``self.feature_order`` (32 columns) and dtype-compatible with
            the XGBoost models.

        Raises:
            ValueError: If ``history`` has fewer than ``MINIMUM_HISTORY_ROWS``
                rows, if ``province`` is unknown, or if ``national_history``
                contains no rows before ``target_week``.
        """
        # ---------------------------------------------------------------
        # Validasi input
        # ---------------------------------------------------------------
        if len(history) < MINIMUM_HISTORY_ROWS:
            raise ValueError(
                f"history must contain at least {MINIMUM_HISTORY_ROWS} rows, "
                f"got {len(history)}."
            )

        if province not in self.province_to_id:
            raise ValueError(
                f"Unknown province '{province}'. "
                f"Allowed: {list(self.province_to_id.keys())}"
            )

        if province not in self.province_to_region:
            raise ValueError(
                f"Province '{province}' is not mapped to any region. "
                "Periksa metadata['region_map']."
            )

        # ---------------------------------------------------------------
        # Ambil price series sebagai numpy array supaya .iloc / indexing
        # negatif tetap konsisten walaupun index DataFrame tidak rapi.
        # ---------------------------------------------------------------
        prices = history["Price"].to_numpy(dtype=float)

        # ---------------------------------------------------------------
        # (a) Lag features. history sorted ascending, jadi prices[-1] adalah
        # nilai paling terbaru (minggu tepat sebelum target_week).
        # ---------------------------------------------------------------
        lag_1 = float(prices[-1])
        lag_2 = float(prices[-2])
        lag_4 = float(prices[-4])
        lag_8 = float(prices[-8])
        lag_12 = float(prices[-12])
        lag_26 = float(prices[-26])
        lag_52 = float(prices[-52])

        # ---------------------------------------------------------------
        # (b) Rolling statistics (mean & std) untuk window 4 & 12 minggu
        # ---------------------------------------------------------------
        last_4 = prices[-4:]
        last_12 = prices[-12:]
        rolling_mean_4 = float(np.mean(last_4))
        rolling_mean_12 = float(np.mean(last_12))
        # ddof=1 (sample std) supaya konsisten dengan training pipeline notebook
        # yang memakai pandas .rolling(...).std() default (ddof=1, min_periods=2).
        rolling_std_4 = float(pd.Series(last_4).std(ddof=1))
        rolling_std_12 = float(pd.Series(last_12).std(ddof=1))

        # ---------------------------------------------------------------
        # (c) Difference & percent change features.
        # Guard pembagian dengan 0 untuk pct_change: kalau denominator
        # 0, kembalikan 0.0 supaya tidak menghasilkan inf/nan.
        # ---------------------------------------------------------------
        diff_1 = lag_1 - lag_2
        diff_4 = lag_1 - lag_4
        pct_change_1 = (lag_1 - lag_2) / lag_2 if lag_2 != 0 else 0.0
        pct_change_4 = (lag_1 - lag_4) / lag_4 if lag_4 != 0 else 0.0

        # ---------------------------------------------------------------
        # (d) Time features dari target_week
        # ---------------------------------------------------------------
        # isocalendar() return tuple (year, week, weekday); ambil index 1
        week_of_year = int(target_week.isocalendar()[1])
        month = int(target_week.month)
        quarter = int((target_week.month - 1) // 3 + 1)

        # ---------------------------------------------------------------
        # (e) Event features (Lebaran & Idul Adha)
        # ---------------------------------------------------------------
        weeks_to_lebaran = self._weeks_to_event(target_week, self.lebaran_dates)
        weeks_to_idul_adha = self._weeks_to_event(target_week, self.idul_adha_dates)
        # Window 4 minggu: anggap "menjelang event" kalau jarak <= 4 minggu
        is_lebaran_window = int(1 if weeks_to_lebaran <= 4 else 0)
        is_idul_adha_window = int(1 if weeks_to_idul_adha <= 4 else 0)
        # Notebook training menandai akhir tahun sebagai Desember ATAU Januari
        # (transisi tahun), bukan hanya Desember.
        is_year_end = int(1 if target_week.month in (12, 1) else 0)

        # ---------------------------------------------------------------
        # (f) National-level features. Ambil minggu terbaru di
        # national_history yang masih < target_week, lalu rata-rata
        # Price-nya di seluruh provinsi pada minggu itu.
        # ---------------------------------------------------------------
        nat = national_history.loc[
            national_history["week_start"] < pd.Timestamp(target_week),
            ["week_start", "Price"],
        ]
        if nat.empty:
            raise ValueError(
                f"national_history has no rows with week_start < {target_week}."
            )
        latest_week = nat["week_start"].max()
        national_mean_lag1 = float(
            nat.loc[nat["week_start"] == latest_week, "Price"].mean()
        )
        # Guard pembagian dengan 0 untuk relative_to_national
        relative_to_national = (
            lag_1 / national_mean_lag1 if national_mean_lag1 != 0 else 0.0
        )

        # ---------------------------------------------------------------
        # (g) Categorical features: province_id + one-hot 6 region
        # ---------------------------------------------------------------
        province_id = int(self.province_to_id[province])
        province_region = self.province_to_region[province]
        region_one_hot: dict[str, int] = {
            f"region_{name}": int(1 if province_region == name else 0)
            for name in self.region_names
        }

        # ---------------------------------------------------------------
        # Susun semua feature ke dalam dict. Nama key WAJIB persis sama
        # dengan entry di metadata['xgb_features'].
        # ---------------------------------------------------------------
        features: dict[str, float] = {
            "lag_1": lag_1,
            "lag_2": lag_2,
            "lag_4": lag_4,
            "lag_8": lag_8,
            "lag_12": lag_12,
            "lag_26": lag_26,
            "lag_52": lag_52,
            "rolling_mean_4": rolling_mean_4,
            "rolling_mean_12": rolling_mean_12,
            "rolling_std_4": rolling_std_4,
            "rolling_std_12": rolling_std_12,
            "diff_1": diff_1,
            "diff_4": diff_4,
            "pct_change_1": pct_change_1,
            "pct_change_4": pct_change_4,
            "week_of_year": week_of_year,
            "month": month,
            "quarter": quarter,
            "weeks_to_lebaran": weeks_to_lebaran,
            "weeks_to_idul_adha": weeks_to_idul_adha,
            "is_lebaran_window": is_lebaran_window,
            "is_idul_adha_window": is_idul_adha_window,
            "is_year_end": is_year_end,
            "national_mean_lag1": national_mean_lag1,
            "relative_to_national": relative_to_national,
            "province_id": province_id,
            **region_one_hot,
        }

        # Pembulatan ke 4 desimal untuk konsistensi numerik. Categorical
        # & integer feature tetap aman karena round(x, 4) pada int = int.
        features = {k: round(float(v), 4) for k, v in features.items()}

        # ---------------------------------------------------------------
        # Build DataFrame 1 baris, lalu reorder kolom sesuai feature_order.
        # Validasi terakhir: pastikan tidak ada kolom yang hilang/extra.
        # ---------------------------------------------------------------
        missing = [c for c in self.feature_order if c not in features]
        if missing:
            raise ValueError(
                f"Feature engineering produced an incomplete row. "
                f"Missing columns: {missing}"
            )

        df = pd.DataFrame([features], columns=self.feature_order)
        return df


# Penyimpanan singleton di module level. Tidak diinisialisasi di sini karena
# konstruktor butuh metadata yang baru tersedia setelah ModelLoader.load_all().
_feature_engineer: Optional[FeatureEngineer] = None


def get_feature_engineer(metadata: Optional[dict] = None) -> FeatureEngineer:
    """Return the process-wide ``FeatureEngineer`` singleton.

    The first call must pass ``metadata``; the instance is then cached and
    subsequent calls may omit the argument. Designed to be wired via the
    FastAPI startup event (where ``metadata`` is read from
    ``ModelLoader.get_metadata()``) and reused via ``Depends``.

    Raises:
        RuntimeError: If called without ``metadata`` before the singleton
            has been initialized.
    """
    global _feature_engineer

    if _feature_engineer is None:
        if metadata is None:
            raise RuntimeError(
                "FeatureEngineer has not been initialized yet. "
                "First call must supply metadata."
            )
        _feature_engineer = FeatureEngineer(metadata=metadata)
        logger.info(
            "FeatureEngineer initialized (%d features in output order)",
            len(_feature_engineer.feature_order),
        )

    return _feature_engineer
