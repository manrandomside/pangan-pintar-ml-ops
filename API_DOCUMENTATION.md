# Pangan Pintar API — Documentation

Dokumen referensi lengkap untuk Pangan Pintar API. Dokumen ini menjelaskan semua endpoint, format request/response, error codes, dan validasi field.

**Versi:** 0.1.0
**Last updated:** Mei 2026
**Maintained by:** Tim KDN — SM Firman & ML Ops Kelin

---

## 1. Overview

Pangan Pintar API adalah REST API untuk memprediksi harga 10 komoditas pangan strategis per provinsi di Indonesia, per minggu. Model XGBoost dilatih pada data historis PIHPS 2022 sampai 2026 dengan walk-forward validation.

### Base URL

| Environment    | URL                                                |
| -------------- | -------------------------------------------------- |
| **Production** | `https://firmanfadilah-pangan-pintar-api.hf.space` |
| **Local dev**  | `http://localhost:8000`                            |

### Authentication

API ini saat ini **tidak memerlukan authentication**. Open API untuk demo capstone. Jika di masa depan butuh API key, akan ada update di dokumen ini.

### Response Format

Semua response dalam format **JSON** dengan header `Content-Type: application/json`.

### Rate Limiting

Saat ini tidak ada rate limiting eksplisit. HuggingFace Spaces (free tier) bisa handle puluhan request per detik untuk inference XGBoost. Untuk burst traffic tinggi (lebih dari 100 req/detik), pertimbangkan upgrade hardware tier.

---

## 2. Endpoints Overview

| Method | Path                  | Deskripsi                                     |
| ------ | --------------------- | --------------------------------------------- |
| GET    | `/`                   | Welcome message dan info versi                |
| GET    | `/health`             | Health check, status service                  |
| POST   | `/api/v1/predict`     | **Prediksi harga komoditas** (endpoint utama) |
| GET    | `/api/v1/commodities` | List 10 komoditas yang didukung               |
| GET    | `/api/v1/provinces`   | List 34 provinsi yang didukung                |
| GET    | `/docs`               | Swagger UI interaktif (Try it out)            |
| GET    | `/redoc`              | ReDoc UI (alternative documentation)          |
| GET    | `/openapi.json`       | OpenAPI specification (untuk codegen client)  |

---

## 3. Endpoint Details

### 3.1 GET `/`

Welcome endpoint, menampilkan info dasar service.

**Request:** tidak ada parameter.

**Response 200 OK:**

```json
{
  "message": "Welcome to Pangan Pintar API",
  "version": "0.1.0",
  "status": "running",
  "docs": "/docs"
}
```

**Use case:** ping awal untuk cek API hidup, atau redirect user ke `/docs`.

---

### 3.2 GET `/health`

Health check endpoint. Biasanya dipakai untuk monitoring tools (uptime checker, load balancer, dll).

**Request:** tidak ada parameter.

**Response 200 OK:**

```json
{
  "status": "healthy",
  "service": "Pangan Pintar API"
}
```

**Use case:** monitoring service uptime. Tools seperti UptimeRobot atau Pingdom bisa ping endpoint ini setiap 5 menit.

---

### 3.3 POST `/api/v1/predict` (Endpoint Utama)

Prediksi harga komoditas pangan untuk pair commodity + province + target_week tertentu.

#### Request

**Headers:**

```
Content-Type: application/json
```

**Body:**

```json
{
  "commodity": "Beras",
  "province": "Aceh",
  "target_week": "2026-01-12"
}
```

**Field Validation:**

| Field         | Type   | Required | Validation                                                                                                                          |
| ------------- | ------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `commodity`   | string | Yes      | Harus salah satu dari 10 komoditas (lihat `/api/v1/commodities`)                                                                    |
| `province`    | string | Yes      | Harus salah satu dari 34 provinsi (lihat `/api/v1/provinces`)                                                                       |
| `target_week` | string | Yes      | Format `YYYY-MM-DD`. Disarankan hari Senin (week start). Harus dalam range data: minimal 52 minggu setelah data history paling awal |

#### Response 200 OK

```json
{
  "commodity": "Beras",
  "province": "Aceh",
  "target_week": "2026-01-12",
  "predicted_price": 15121.15,
  "currency": "IDR",
  "model": "XGBoost",
  "predicted_at": "2026-05-25T03:19:03.611912"
}
```

**Field Response:**

| Field             | Type   | Deskripsi                                    |
| ----------------- | ------ | -------------------------------------------- |
| `commodity`       | string | Echo dari request                            |
| `province`        | string | Echo dari request                            |
| `target_week`     | string | Echo dari request (format YYYY-MM-DD)        |
| `predicted_price` | float  | Harga prediksi dalam IDR (Rupiah), 2 desimal |
| `currency`        | string | Selalu `"IDR"` saat ini                      |
| `model`           | string | Selalu `"XGBoost"` saat ini                  |
| `predicted_at`    | string | ISO 8601 timestamp saat prediksi dibuat      |

#### Sample CURL

```bash
curl -X POST https://firmanfadilah-pangan-pintar-api.hf.space/api/v1/predict \
  -H "Content-Type: application/json" \
  -d '{
    "commodity": "Beras",
    "province": "Aceh",
    "target_week": "2026-01-12"
  }'
```

---

### 3.4 GET `/api/v1/commodities`

Mendapatkan list 10 komoditas yang didukung. Berguna untuk populate dropdown di UI.

**Request:** tidak ada parameter.

**Response 200 OK:**

```json
{
  "commodities": [
    "Bawang Merah",
    "Bawang Putih",
    "Beras",
    "Cabai Merah",
    "Cabai Rawit",
    "Daging Ayam",
    "Daging Sapi",
    "Gula Pasir",
    "Minyak Goreng",
    "Telur Ayam"
  ]
}
```

---

### 3.5 GET `/api/v1/provinces`

Mendapatkan list 34 provinsi yang didukung.

**Request:** tidak ada parameter.

**Response 200 OK:**

```json
{
  "provinces": [
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
    "Sumatera Utara"
  ]
}
```

---

## 4. Error Codes

API menggunakan HTTP status codes standar. Body error mengikuti format berikut:

### 4.1 400 Bad Request — Validation Error

Terjadi kalau ada **business logic validation** yang gagal. Contoh: target_week tidak punya cukup history (kurang dari 52 minggu sebelum target).

**Body:**

```json
{
  "detail": {
    "error": "ValidationError",
    "message": "Target week 2023-01-01 is not predictable for (Beras, Aceh): need at least 52 weeks of history, only 1 available."
  }
}
```

**Common causes:**

- `target_week` terlalu awal (kurang dari 52 minggu setelah data start)
- `target_week` di luar range data historis

### 4.2 404 Not Found — Model Not Found

Terjadi kalau model untuk commodity tertentu tidak ditemukan (kasus rare, biasanya berarti deployment bug).

**Body:**

```json
{
  "detail": {
    "error": "ModelNotFound",
    "message": "Model for commodity 'XYZ' not found. Available: [...]"
  }
}
```

### 4.3 422 Unprocessable Entity — Schema Validation Error

Terjadi kalau request body tidak memenuhi schema Pydantic. Misalnya: commodity bukan dari 10 list, atau target_week formatnya salah.

**Body:**

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "commodity"],
      "msg": "Value error, Commodity 'Nasi Goreng' is not supported. Allowed values: ['Bawang Merah', 'Bawang Putih', ...]",
      "input": "Nasi Goreng"
    }
  ]
}
```

**Common causes:**

- `commodity` tidak ada di list 10 komoditas
- `province` tidak ada di list 34 provinsi
- `target_week` bukan format YYYY-MM-DD
- Required field kosong atau null

### 4.4 500 Internal Server Error

Terjadi kalau ada error tak terduga di server. Body:

```json
{
  "detail": {
    "error": "InternalError",
    "message": "An unexpected error occurred during prediction"
  }
}
```

**Common causes:**

- Bug di feature engineering
- Model file corrupted
- Out of memory (rare di HF Spaces basic)

Kalau dapat error ini berulang, cek logs di HuggingFace Space atau hubungi maintainer.

---

## 5. CORS Configuration

API ini sudah configured untuk allow CORS dari origin berikut (saat ini, Mei 2026):

- `http://localhost:3000` (Next.js dev)
- `http://localhost:5173` (Vite dev)
- `http://localhost:8080` (alternative port)
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

Kalau frontend deploy ke domain lain (Vercel, Netlify, custom domain), **hubungi maintainer untuk update CORS whitelist**. Jangan asumsi origin baru akan otomatis di-allow.

Method yang di-allow: `GET, POST, OPTIONS`
Headers yang di-allow: `content-type, accept, authorization`
Credentials: `allowed`

---

## 6. Data Coverage

### Range data historis

- **Mulai:** 2022-12-26 (Senin)
- **Akhir:** 2026-02-09 (Senin)
- **Total minggu:** 164 minggu unik
- **Total pair (komoditas x provinsi):** 340 pair

### Range target_week valid untuk prediksi

Karena model butuh minimum 52 minggu history, target_week valid mulai dari sekitar **2023-12-25** sampai **2026-02-16** (1 minggu setelah data terakhir).

Untuk prediksi melampaui 2026-02-16, perlu update data historis (lihat MAINTENANCE.md).

---

## 7. Versioning

API menggunakan **URL versioning**:

- `/api/v1/...` — versi current
- `/api/v2/...` — reserved untuk breaking changes di masa depan

Kalau ada breaking change (mengubah struktur response atau field), akan rilis di `/api/v2/` dan `/api/v1/` tetap support minimal 3 bulan untuk migration.

**Saat ini hanya v1.**

---

## 8. Useful Links

- **Swagger UI Interaktif:** https://firmanfadilah-pangan-pintar-api.hf.space/docs
- **GitHub Repo:** https://github.com/manrandomside/pangan-pintar-ml-ops
- **HuggingFace Space:** https://huggingface.co/spaces/firmanfadilah/pangan-pintar-api
- **Integration Guide untuk Frontend:** lihat `INTEGRATION_GUIDE.md`
- **Maintenance Guide untuk ML Ops:** lihat `MAINTENANCE.md`

---

## 9. Contact

Untuk pertanyaan, bug report, atau request feature:

- **Maintainer:** Firman Fadilah (Scrum Master + ML Ops Tim KDN)
- **Capstone Project:** Pangan Pintar — Infinite Learning AI Dev B10
