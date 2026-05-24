---
title: Pangan Pintar API
emoji: 🌾
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Pangan Pintar API

Pangan Pintar adalah sistem prediksi harga pangan mingguan untuk komoditas pokok di seluruh provinsi Indonesia. Sistem ini memanfaatkan model machine learning XGBoost yang dilatih menggunakan data historis PIHPS (Pusat Informasi Harga Pangan Strategis) untuk menghasilkan prediksi harga satu minggu ke depan.

API ini menyediakan akses programatis ke seluruh kemampuan prediksi Pangan Pintar, memungkinkan integrasi dengan dashboard, aplikasi mobile, maupun sistem monitoring harga pangan lainnya.

## Tech Stack

| Komponen | Teknologi |
|---|---|
| Web Framework | FastAPI 0.115.0 |
| ML Model | XGBoost 3.2.0 |
| Feature Engineering | scikit-learn 1.5.2, pandas 2.2.3 |
| Runtime | Python 3.13, Uvicorn |
| Deployment | Docker, HuggingFace Spaces |

## Endpoints

API menyediakan 5 endpoint berikut:

| Method | Path | Deskripsi |
|---|---|---|
| `GET` | `/` | Informasi dasar service dan link ke dokumentasi |
| `GET` | `/health` | Health check endpoint untuk monitoring dan orchestrator |
| `POST` | `/api/v1/predict` | Prediksi harga komoditas untuk satu minggu target |
| `GET` | `/api/v1/commodities` | Daftar komoditas yang didukung oleh model |
| `GET` | `/api/v1/provinces` | Daftar provinsi yang tersedia untuk prediksi |

## Cara Menggunakan

1. Buka halaman dokumentasi interaktif (Swagger UI) di endpoint `/docs` pada URL Space ini.
2. Gunakan endpoint `/api/v1/commodities` dan `/api/v1/provinces` untuk melihat daftar komoditas dan provinsi yang tersedia.
3. Kirim request prediksi ke `/api/v1/predict` dengan payload JSON berisi `commodity`, `province`, dan `target_week`.

Contoh request body untuk endpoint `/api/v1/predict`:

```json
{
  "commodity": "beras",
  "province": "Jawa Barat",
  "target_week": "2025-01-06"
}
```

## About This Project

Pangan Pintar dikembangkan sebagai capstone project Sprint Review 3 oleh Tim KDN dalam program Infinite Learning AI Developer Batch 10 (B10).

Project ini mencakup pipeline end-to-end mulai dari pengumpulan data historis harga pangan, feature engineering berbasis time-series, pelatihan model XGBoost per komoditas, hingga deployment API yang production-ready di HuggingFace Spaces.

### Komoditas yang Didukung

Sistem saat ini mendukung prediksi untuk 10 komoditas pangan strategis:

- Beras
- Bawang Merah
- Bawang Putih
- Cabai Merah
- Cabai Rawit
- Daging Ayam
- Daging Sapi
- Gula Pasir
- Minyak Goreng
- Telur Ayam

## Lisensi

Project ini dilisensikan di bawah [MIT License](LICENSE).
