"""
Script untuk inspect/explore isi artifacts ML PanganPintar.

Tujuan: memahami struktur metadata, scalers, dan XGBoost model
sebelum dipakai di endpoint prediksi FastAPI.

Cara pakai (dari root project):
    python scripts/inspect_artifacts.py
"""

import json
import pickle
import sys
from pathlib import Path


# Path artifacts dihitung relatif terhadap root project (parent dari folder scripts/)
ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
METADATA_PATH = ARTIFACTS_DIR / "metadata.json"
SCALERS_PATH = ARTIFACTS_DIR / "scalers.pkl"
SAMPLE_XGB_PATH = ARTIFACTS_DIR / "xgb_beras.pkl"
WEEKLY_PRICES_PATH = ARTIFACTS_DIR / "weekly_prices.csv"

# Jumlah pair (komoditas x provinsi) yang diharapkan: harus tepat 340
EXPECTED_PAIR_COUNT = 340

SECTION_WIDTH = 70


def print_header(title: str) -> None:
    """Cetak judul section dengan separator '=' yang rapi."""
    print()
    print("=" * SECTION_WIDTH)
    print(f" {title}")
    print("=" * SECTION_WIDTH)


def print_subheader(title: str) -> None:
    """Cetak sub-judul dengan separator '-'."""
    print()
    print("-" * SECTION_WIDTH)
    print(f" {title}")
    print("-" * SECTION_WIDTH)


def inspect_metadata() -> None:
    """Load metadata.json dan tampilkan ringkasan strukturnya."""
    print_header("1. METADATA.JSON")

    try:
        with METADATA_PATH.open("r", encoding="utf-8") as f:
            metadata = json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] File metadata tidak ditemukan: {METADATA_PATH}")
        return
    except json.JSONDecodeError as e:
        print(f"[ERROR] Gagal parse JSON: {e}")
        return

    # Tampilkan semua top-level keys agar terlihat struktur keseluruhan
    print_subheader("Top-level keys")
    for key in metadata.keys():
        print(f"  - {key}")

    # Ringkasan ukuran data
    print_subheader("Ringkasan jumlah")
    commodities = metadata.get("commodities", [])
    provinces = metadata.get("provinces", [])
    features = metadata.get("xgb_features", [])
    print(f"  Jumlah komoditas       : {len(commodities)}")
    print(f"  Jumlah provinsi        : {len(provinces)}")
    print(f"  Jumlah xgb_features    : {len(features)}")
    print(f"  Total kombinasi (C x P): {len(commodities) * len(provinces)}")

    print_subheader("Daftar komoditas")
    for c in commodities:
        print(f"  - {c}")

    print_subheader("Daftar provinsi (5 pertama)")
    for p in provinces[:5]:
        print(f"  - {p}")
    if len(provinces) > 5:
        print(f"  ... dan {len(provinces) - 5} lainnya")

    print_subheader("Daftar xgb_features")
    for feat in features:
        print(f"  - {feat}")

    # Tanggal-tanggal penting untuk inferensi
    print_subheader("Tanggal data")
    print(f"  train_end   : {metadata.get('train_end')}")
    print(f"  test_start  : {metadata.get('test_start')}")
    print(f"  test_end    : {metadata.get('test_end')}")
    print(f"  created_at  : {metadata.get('created_at')}")
    print(f"  lookback    : {metadata.get('lookback')}")

    print_subheader("Tanggal lebaran & idul adha")
    print(f"  lebaran_dates   : {metadata.get('lebaran_dates')}")
    print(f"  idul_adha_dates : {metadata.get('idul_adha_dates')}")


def inspect_scalers() -> None:
    """Load scalers.pkl dan tampilkan struktur dictionary scaler."""
    print_header("2. SCALERS.PKL")

    try:
        with SCALERS_PATH.open("rb") as f:
            scalers = pickle.load(f)
    except FileNotFoundError:
        print(f"[ERROR] File scalers tidak ditemukan: {SCALERS_PATH}")
        return
    except pickle.UnpicklingError as e:
        print(f"[ERROR] Gagal unpickle scalers: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Gagal load scalers ({type(e).__name__}): {e}")
        return

    print_subheader("Ringkasan")
    print(f"  Tipe objek    : {type(scalers).__name__}")
    print(f"  Total scaler  : {len(scalers)}")

    # Ambil semua key untuk diinspeksi
    keys = list(scalers.keys())
    print(f"  Tipe key      : {type(keys[0]).__name__}")

    print_subheader("5 sample key pertama")
    for k in keys[:5]:
        print(f"  - {k}")

    # Ambil 1 sample scaler untuk lihat atribut MinMaxScaler hasil fit
    print_subheader("Detail 1 sample scaler")
    sample_key = keys[0]
    sample_scaler = scalers[sample_key]
    print(f"  Key           : {sample_key}")
    print(f"  Tipe scaler   : {type(sample_scaler).__name__}")

    # Atribut MinMaxScaler yang penting untuk inverse_transform di endpoint
    for attr in ("data_min_", "data_max_", "scale_", "min_", "data_range_"):
        if hasattr(sample_scaler, attr):
            print(f"  {attr:14}: {getattr(sample_scaler, attr)}")

    # feature_range adalah parameter konstruktor, bukan hasil fit
    if hasattr(sample_scaler, "feature_range"):
        print(f"  feature_range : {sample_scaler.feature_range}")
    if hasattr(sample_scaler, "n_features_in_"):
        print(f"  n_features_in_: {sample_scaler.n_features_in_}")


def inspect_sample_model() -> None:
    """Load 1 sample XGBoost model dan tampilkan info feature-nya."""
    print_header("3. SAMPLE XGBOOST MODEL (xgb_beras.pkl)")

    try:
        with SAMPLE_XGB_PATH.open("rb") as f:
            model = pickle.load(f)
    except FileNotFoundError:
        print(f"[ERROR] File model tidak ditemukan: {SAMPLE_XGB_PATH}")
        return
    except pickle.UnpicklingError as e:
        print(f"[ERROR] Gagal unpickle model: {e}")
        return
    except Exception as e:
        print(f"[ERROR] Gagal load model ({type(e).__name__}): {e}")
        return

    print_subheader("Tipe model")
    print(f"  Type     : {type(model).__name__}")
    print(f"  Module   : {type(model).__module__}")

    print_subheader("Jumlah feature yang diharapkan")
    # XGBoost sklearn API menyimpan n_features_in_; booster pakai num_features()
    if hasattr(model, "n_features_in_"):
        print(f"  n_features_in_ : {model.n_features_in_}")
    elif hasattr(model, "num_features"):
        try:
            print(f"  num_features() : {model.num_features()}")
        except Exception as e:
            print(f"  [warning] gagal panggil num_features(): {e}")
    else:
        print("  [info] tidak ada atribut n_features_in_ atau num_features()")

    print_subheader("Sample feature names (jika tersedia)")
    feature_names = None
    # Coba beberapa atribut yang umum dipakai berbagai versi XGBoost
    if hasattr(model, "feature_names_in_"):
        feature_names = list(model.feature_names_in_)
    elif hasattr(model, "feature_names") and model.feature_names is not None:
        feature_names = list(model.feature_names)
    elif hasattr(model, "get_booster"):
        try:
            booster = model.get_booster()
            if booster.feature_names is not None:
                feature_names = list(booster.feature_names)
        except Exception as e:
            print(f"  [warning] gagal akses booster: {e}")

    if feature_names:
        print(f"  Total feature names : {len(feature_names)}")
        print("  10 pertama:")
        for name in feature_names[:10]:
            print(f"    - {name}")
        if len(feature_names) > 10:
            print(f"    ... dan {len(feature_names) - 10} lainnya")
    else:
        print("  [info] feature names tidak tersedia pada model ini")

    # Tambahkan info parameter penting kalau ada
    if hasattr(model, "get_params"):
        print_subheader("Beberapa parameter model")
        try:
            params = model.get_params()
            for key in ("n_estimators", "max_depth", "learning_rate", "objective"):
                if key in params:
                    print(f"  {key:16}: {params[key]}")
        except Exception as e:
            print(f"  [warning] gagal ambil params: {e}")


def inspect_weekly_prices() -> None:
    """Load weekly_prices.csv dan verifikasi kelengkapan data harga mingguan."""
    print_header("4. WEEKLY_PRICES.CSV")

    # Import pandas di dalam fungsi supaya section 1-3 tetap bisa jalan
    # walau pandas belum terpasang di environment.
    try:
        import pandas as pd
    except ImportError:
        print("[ERROR] pandas tidak terpasang. Install dengan: pip install pandas")
        return

    if not WEEKLY_PRICES_PATH.exists():
        print(f"[ERROR] File CSV tidak ditemukan: {WEEKLY_PRICES_PATH}")
        return

    # Baca CSV; parse_dates supaya kolom week_start langsung jadi datetime
    try:
        df = pd.read_csv(WEEKLY_PRICES_PATH, parse_dates=["week_start"])
    except Exception as e:
        print(f"[ERROR] Gagal baca CSV ({type(e).__name__}): {e}")
        return

    print_subheader("Shape & total baris")
    print(f"  Path          : {WEEKLY_PRICES_PATH}")
    print(f"  Shape         : {df.shape}")
    print(f"  Total baris   : {len(df):,}")
    print(f"  Total kolom   : {df.shape[1]}")
    print(f"  Kolom         : {list(df.columns)}")

    # Range tanggal dan jumlah minggu unik untuk validasi cakupan waktu
    print_subheader("Date range (week_start)")
    min_date = df["week_start"].min()
    max_date = df["week_start"].max()
    unique_weeks = df["week_start"].nunique()
    print(f"  Min week_start  : {min_date.date() if pd.notna(min_date) else 'N/A'}")
    print(f"  Max week_start  : {max_date.date() if pd.notna(max_date) else 'N/A'}")
    print(f"  Total minggu unik: {unique_weeks}")

    # Jumlah komoditas & provinsi serta total pair yang ada di data
    print_subheader("Jumlah komoditas & provinsi")
    n_commodities = df["Commodity_Name"].nunique()
    n_provinces = df["Province_Name"].nunique()
    pair_df = df[["Commodity_Name", "Province_Name"]].drop_duplicates()
    n_pairs = len(pair_df)
    print(f"  Jumlah komoditas  : {n_commodities}")
    print(f"  Jumlah provinsi   : {n_provinces}")
    print(f"  Total pair (C x P): {n_pairs}")
    print(f"  Pair diharapkan   : {EXPECTED_PAIR_COUNT}")
    if n_pairs == EXPECTED_PAIR_COUNT:
        print(f"  Status pair       : OK (sesuai {EXPECTED_PAIR_COUNT})")
    else:
        print(
            f"  Status pair       : MISMATCH "
            f"(selisih {n_pairs - EXPECTED_PAIR_COUNT})"
        )

    # Per komoditas: hitung jumlah minggu di tiap provinsi, cek konsistensi
    print_subheader("Konsistensi jumlah minggu per komoditas")
    # Hitung jumlah minggu unik per (Commodity, Province), lalu agregasi per Commodity
    weeks_per_pair = (
        df.groupby(["Commodity_Name", "Province_Name"])["week_start"]
        .nunique()
        .reset_index(name="n_weeks")
    )
    summary = weeks_per_pair.groupby("Commodity_Name")["n_weeks"].agg(
        ["min", "max", "mean", "count"]
    )
    print(f"  {'Commodity':<25} {'min':>6} {'max':>6} {'mean':>8} {'n_prov':>7} {'konsisten':>10}")
    for commodity, row in summary.iterrows():
        # Konsisten bila min == max (semua provinsi punya jumlah minggu sama)
        konsisten = "YA" if row["min"] == row["max"] else "TIDAK"
        print(
            f"  {commodity:<25} {int(row['min']):>6} {int(row['max']):>6} "
            f"{row['mean']:>8.1f} {int(row['count']):>7} {konsisten:>10}"
        )

    # Cek missing values di tiap kolom; idealnya semua 0
    print_subheader("Missing values per kolom")
    missing = df.isna().sum()
    total_missing = int(missing.sum())
    for col, n_missing in missing.items():
        pct = (n_missing / len(df) * 100) if len(df) else 0.0
        print(f"  {col:<20}: {int(n_missing):>8,} ({pct:.2f}%)")
    print(f"  TOTAL missing       : {total_missing:,}")

    # Cek duplikat berdasarkan kunci natural (week_start, commodity, province)
    print_subheader("Duplikat (week_start, Commodity_Name, Province_Name)")
    dup_keys = ["week_start", "Commodity_Name", "Province_Name"]
    n_duplicates = int(df.duplicated(subset=dup_keys).sum())
    print(f"  Total baris duplikat : {n_duplicates}")
    if n_duplicates == 0:
        print("  Status               : OK (tidak ada duplikat)")
    else:
        print("  Status               : ADA DUPLIKAT (perlu cek ulang)")

    # Sample 5 baris pertama supaya tahu format isi data
    print_subheader("Sample 5 baris pertama")
    # to_string supaya tidak terpotong oleh display width default pandas
    print(df.head(5).to_string(index=False))


def main() -> int:
    print_header("INSPECT ARTIFACTS - PanganPintar ML")
    print(f"  Root project : {ROOT_DIR}")
    print(f"  Artifacts    : {ARTIFACTS_DIR}")

    if not ARTIFACTS_DIR.exists():
        print(f"\n[ERROR] Folder artifacts tidak ditemukan: {ARTIFACTS_DIR}")
        return 1

    inspect_metadata()
    inspect_scalers()
    inspect_sample_model()
    inspect_weekly_prices()

    print()
    print("=" * SECTION_WIDTH)
    print(" SELESAI")
    print("=" * SECTION_WIDTH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
